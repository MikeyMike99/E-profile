"""Admin-only subscriber registry and release, download and newsletter notifications.

Every route answers 404 to non-admin sessions so the feature's existence is not
disclosed. While NOTIFY_ADMIN_ONLY is true (the default when Config omits it),
download thank-you emails fire only for admin downloads, so no visitor is emailed
before the consent and confirmation flow ships.
"""

from __future__ import annotations

import html
import json
import re
import secrets
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for

from config import Config

config = Config()
notify_bp = Blueprint("notify", __name__)

CACHE_DIR = config.ROOT_DIR / "cache"
SUBSCRIBERS_FILE = CACHE_DIR / "subscribers.json"
NOTIFY_STATE_FILE = CACHE_DIR / "notify_state.json"
TOPICS = ("releases", "downloads", "newsletter")
VALID_FORMATS = ("hybrid_brief", "full_story_daily", "quick_threat_wire", "weekly_digest")
VALID_APPETITES = ("cyber_thriller", "deep_dive", "defense_playbook", "executive_espresso", "snarky_hacker")
VALID_TOPICS = ("zero_days", "ransomware", "cisa_kev", "supply_chain", "cloud_infra")
METRICS_FILE = config.ROOT_DIR / "traffic_metrics.json"

EMAIL_PATTERN = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")
RELEASE_ENDPOINTS = {"audio_suite.schedule_publish_now", "audio_suite.stage_update_release"}
DOWNLOAD_ENDPOINTS = {"audio_suite.downloads_view", "audio_suite.download_package"}

_store_lock = threading.Lock()
_metrics_lock = threading.Lock()


def _is_admin() -> bool:
    return bool(session.get("admin", False) or session.get("is_admin", False))


def _admin_only_mode() -> bool:
    return bool(getattr(config, "NOTIFY_ADMIN_ONLY", True))


def _require_admin() -> None:
    if not _is_admin():
        abort(404)


def _require_admin_json() -> dict:
    """Admin POSTs must be JSON: browsers cannot send cross-site JSON without a CORS preflight, which blocks CSRF."""
    _require_admin()
    if not request.is_json:
        abort(400)
    return request.get_json(silent=True) or {}


def _read_json(path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return data if isinstance(data, type(default)) else default


def _write_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(data, indent=2), encoding="utf-8")
    staging.replace(path)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_subscriber(entry: dict) -> dict:
    if not isinstance(entry, dict):
        return {}
    if not entry.get("subscriber_id"):
        entry["subscriber_id"] = f"sub_{secrets.token_hex(6)}"
    if not entry.get("token"):
        entry["token"] = secrets.token_urlsafe(24)
    if "status" not in entry:
        entry["status"] = "active"
    if "topics" not in entry or not isinstance(entry["topics"], list):
        entry["topics"] = ["newsletter"]

    delivery = entry.setdefault("delivery", {})
    if not isinstance(delivery, dict):
        delivery = {}
        entry["delivery"] = delivery
    if delivery.get("format") not in VALID_FORMATS:
        delivery["format"] = "hybrid_brief"
    delivery["cadence"] = "weekly" if delivery["format"] == "weekly_digest" else "daily"

    content = entry.setdefault("content", {})
    if not isinstance(content, dict):
        content = {}
        entry["content"] = content
    if content.get("primary_appetite") not in VALID_APPETITES:
        content["primary_appetite"] = "cyber_thriller"
    if not isinstance(content.get("topics"), list) or not content["topics"]:
        content["topics"] = ["zero_days", "cisa_kev"]
    else:
        content["topics"] = [t for t in content["topics"] if t in VALID_TOPICS] or ["zero_days", "cisa_kev"]

    engagement = entry.setdefault("engagement_modules", {})
    if not isinstance(engagement, dict):
        engagement = {}
        entry["engagement_modules"] = engagement
    for mod in ("alt_appetite_teaser", "audio_link", "zero_day_radar"):
        if mod not in engagement:
            engagement[mod] = True

    if not entry.get("created_at") and not entry.get("added_at"):
        entry["created_at"] = _now()
    elif not entry.get("created_at") and entry.get("added_at"):
        entry["created_at"] = entry["added_at"]

    if not entry.get("updated_at"):
        entry["updated_at"] = _now()

    if not entry.get("last_active_at"):
        entry["last_active_at"] = entry.get("updated_at") or entry.get("created_at") or _now()

    return entry


def load_subscribers() -> list:
    with _store_lock:
        raw_list = _read_json(SUBSCRIBERS_FILE, [])
        return [normalize_subscriber(s) for s in raw_list if isinstance(s, dict)]


def add_subscriber(email: str, topics) -> dict:
    address = (email or "").strip().lower()
    if len(address) > 254 or not EMAIL_PATTERN.match(address):
        raise ValueError("Enter a valid email address.")
    chosen = sorted({topic for topic in topics if topic in TOPICS})
    if not chosen:
        raise ValueError("Choose at least one topic.")
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("email") == address), None)
        if entry is None:
            entry = {"email": address, "token": secrets.token_urlsafe(24), "added_at": _now()}
            subscribers.append(entry)
        entry["topics"] = chosen
        entry["status"] = "active"
        entry["updated_at"] = _now()
        normalize_subscriber(entry)
        _write_json(SUBSCRIBERS_FILE, subscribers)
    return entry


def dispatch_welcome_email(subscriber: dict, base_url: str = None, sync: bool = None) -> None:
    """Dispatches the welcome confirmation email with an immediate 1-click unsubscribe option."""
    from email_engine import send_welcome_email
    import os

    resolved_base = base_url
    if not resolved_base:
        try:
            from flask import request
            resolved_base = request.host_url.rstrip("/")
        except Exception:
            resolved_base = getattr(config, "BASE_URL", "https://mikeymike.pythonanywhere.com").rstrip("/")

    is_pa = bool(os.environ.get("PYTHONANYWHERE_DOMAIN") or os.environ.get("PYTHONANYWHERE_SITE"))
    is_smtp = getattr(config, "MAIL_BACKEND", "").lower() == "smtp"
    if sync is None:
        sync = is_pa or is_smtp

    app = None
    try:
        from flask import current_app
        if current_app:
            app = current_app._get_current_object()
    except Exception:
        pass

    def deliver():
        ctx = app.app_context() if app else None
        if ctx:
            ctx.push()
        try:
            ok, msg, _ = send_welcome_email(subscriber, base_url=resolved_base)
            if not ok and app:
                app.logger.warning("Welcome email to %s failed: %s", subscriber.get("email"), msg)
        except Exception as exc:
            if app:
                app.logger.warning("Exception sending welcome email to %s: %s", subscriber.get("email"), exc)
        finally:
            if ctx:
                ctx.pop()

    if sync:
        deliver()
    else:
        threading.Thread(target=deliver, name=f"welcome-{subscriber.get('subscriber_id', 'sub')}", daemon=True).start()


def subscribe_newsletter(
    email: str,
    delivery_format: str = "hybrid_brief",
    primary_appetite: str = "cyber_thriller",
    topics: list = None,
    engagement_modules: dict = None,
    send_welcome: bool = False,
    base_url: str = None,
    sync_welcome: bool = None
) -> dict:
    address = (email or "").strip().lower()
    if len(address) > 254 or not EMAIL_PATTERN.match(address):
        raise ValueError("Enter a valid email address.")

    chosen_format = delivery_format if delivery_format in VALID_FORMATS else "hybrid_brief"
    chosen_appetite = primary_appetite if primary_appetite in VALID_APPETITES else "cyber_thriller"
    chosen_topics = [t for t in (topics or ["zero_days", "cisa_kev"]) if t in VALID_TOPICS] or ["zero_days", "cisa_kev"]

    default_engagement = {"alt_appetite_teaser": True, "audio_link": True, "zero_day_radar": True}
    if isinstance(engagement_modules, dict):
        for k in default_engagement:
            if k in engagement_modules:
                default_engagement[k] = bool(engagement_modules[k])

    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("email") == address), None)
        if entry is None:
            entry = {
                "subscriber_id": f"sub_{secrets.token_hex(6)}",
                "email": address,
                "token": secrets.token_urlsafe(24),
                "created_at": _now()
            }
            subscribers.append(entry)

        entry["status"] = "active"
        entry["last_active_at"] = _now()
        entry["delivery"] = {
            "format": chosen_format,
            "cadence": "weekly" if chosen_format == "weekly_digest" else "daily"
        }
        entry["content"] = {
            "primary_appetite": chosen_appetite,
            "topics": chosen_topics
        }
        entry["engagement_modules"] = default_engagement
        existing_topics = set(entry.get("topics") or [])
        existing_topics.add("newsletter")
        entry["topics"] = sorted(existing_topics)
        entry["updated_at"] = _now()
        normalize_subscriber(entry)
        _write_json(SUBSCRIBERS_FILE, subscribers)

    if send_welcome:
        dispatch_welcome_email(entry, base_url=base_url, sync=sync_welcome)

    return entry



def get_subscriber_by_token(token: str):
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    for sub in load_subscribers():
        if sub.get("token") == token:
            return sub
    return None


def get_subscriber_by_email(email: str):
    if not email or not isinstance(email, str):
        return None
    email = email.strip().lower()
    for sub in load_subscribers():
        if sub.get("email") == email:
            return sub
    return None


def update_subscriber_preferences(
    token: str,
    delivery_format: str = None,
    primary_appetite: str = None,
    topics: list = None,
    engagement_modules: dict = None,
    status: str = None
):
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("token") == token), None)
        if not entry:
            return None
        normalize_subscriber(entry)
        if delivery_format and delivery_format in VALID_FORMATS:
            entry["delivery"]["format"] = delivery_format
            entry["delivery"]["cadence"] = "weekly" if delivery_format == "weekly_digest" else "daily"
        if primary_appetite and primary_appetite in VALID_APPETITES:
            entry["content"]["primary_appetite"] = primary_appetite
        if topics is not None and isinstance(topics, list):
            valid_t = [t for t in topics if t in VALID_TOPICS]
            if valid_t:
                entry["content"]["topics"] = valid_t
        if engagement_modules is not None and isinstance(engagement_modules, dict):
            for k in ("alt_appetite_teaser", "audio_link", "zero_day_radar"):
                if k in engagement_modules:
                    entry["engagement_modules"][k] = bool(engagement_modules[k])
        if status in ("active", "unsubscribed"):
            entry["status"] = status
        entry["updated_at"] = _now()
        _write_json(SUBSCRIBERS_FILE, subscribers)
        return entry


def purge_subscriber_by_token(token: str) -> Optional[dict]:
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("token") == token), None)
        if not entry:
            return None
        subscribers = [s for s in subscribers if s.get("token") != token]
        _write_json(SUBSCRIBERS_FILE, subscribers)
        return entry


def unsubscribe_by_token(token: str, purge: bool = False) -> bool:
    if purge:
        purged = purge_subscriber_by_token(token)
        return bool(purged)
    updated = update_subscriber_preferences(token, status="unsubscribed")
    return bool(updated)


def record_newsletter_send(delivery_format: str, appetite: str) -> None:
    with _metrics_lock:
        data = _read_json(METRICS_FILE, {})
        nl = data.setdefault("newsletter", {})
        sends = nl.setdefault("sends", {"total": 0, "by_format": {}, "by_appetite": {}})
        sends["total"] = sends.get("total", 0) + 1
        
        by_fmt = sends.setdefault("by_format", {})
        by_fmt[delivery_format] = by_fmt.get(delivery_format, 0) + 1
        
        by_app = sends.setdefault("by_appetite", {})
        by_app[appetite] = by_app.get(appetite, 0) + 1
        
        _write_json(METRICS_FILE, data)


def record_newsletter_click(slot: str, target: str) -> None:
    with _metrics_lock:
        data = _read_json(METRICS_FILE, {})
        nl = data.setdefault("newsletter", {})
        clicks = nl.setdefault("clicks", {"total": 0, "by_slot": {}})
        clicks["total"] = clicks.get("total", 0) + 1
        
        by_slot = clicks.setdefault("by_slot", {})
        by_slot[slot] = by_slot.get(slot, 0) + 1
        
        _write_json(METRICS_FILE, data)


def encode_tracking_token(slot: str, target_url: str, sub_token: str = "") -> str:
    import base64
    payload_dict = {"s": slot, "u": target_url}
    if sub_token:
        payload_dict["t"] = sub_token
    payload = json.dumps(payload_dict, separators=(',', ':'))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_tracking_token(token_str: str):
    import base64
    if not token_str or not isinstance(token_str, str):
        return None
    try:
        padding = "=" * ((4 - len(token_str) % 4) % 4)
        raw = base64.urlsafe_b64decode((token_str + padding).encode("utf-8")).decode("utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and "s" in data and "u" in data:
            return data
    except Exception:
        return None
    return None


def touch_subscriber_activity(token_or_email: str) -> bool:
    """Updates last_active_at for a subscriber when they visit the site, click email links, or update preferences."""
    if not token_or_email or not isinstance(token_or_email, str):
        return False
    identifier = token_or_email.strip()
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next(
            (s for s in subscribers if s.get("token") == identifier or s.get("email", "").lower() == identifier.lower()),
            None
        )
        if not entry:
            return False
        entry["last_active_at"] = _now()
        entry["updated_at"] = _now()
        _write_json(SUBSCRIBERS_FILE, subscribers)
    return True


def purge_inactive_subscribers(inactivity_days: int = 30) -> list:
    """Purges subscribers who have not visited the website within the specified period."""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=inactivity_days)
    purged = []
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        active_remaining = []
        for s in subscribers:
            last_active = s.get("last_active_at") or s.get("created_at")
            is_active = True
            if last_active:
                try:
                    dt = datetime.strptime(last_active, "%Y-%m-%d %H:%M:%S")
                    if dt < cutoff:
                        is_active = False
                except ValueError:
                    pass
            if is_active:
                active_remaining.append(s)
            else:
                purged.append(s)
        if purged:
            _write_json(SUBSCRIBERS_FILE, active_remaining)
    return purged


def remove_subscriber(email: str) -> bool:
    address = (email or "").strip().lower()
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        remaining = [s for s in subscribers if s.get("email") != address]
        if len(remaining) == len(subscribers):
            return False
        _write_json(SUBSCRIBERS_FILE, remaining)
    return True


def recipients_for(topic: str) -> list:
    return [
        s["email"] for s in load_subscribers()
        if s.get("email") and s.get("status") == "active" and topic in s.get("topics", [])
    ]


def _dispatch(topic, subject, title, body_html, action_url=None, action_label=None) -> int:
    """Sends one individually addressed email per recipient, so subscribers never see each other's
    addresses, on a daemon thread so the triggering request never waits on SMTP."""
    from email_engine import build_email_template, send_email

    recipients = recipients_for(topic)
    if not recipients:
        return 0
    content = build_email_template(title, body_html, action_url, action_label)
    logger = current_app.logger

    def deliver():
        for address in recipients:
            ok, message, _ = send_email(to_address=address, subject=subject, html_content=content)
            if not ok:
                logger.warning("Notification to %s failed: %s", address, message)

    threading.Thread(target=deliver, name=f"notify-{topic}", daemon=True).start()
    return len(recipients)


def _send_release_email(releases) -> int:
    version = str(releases.get("version", "")).strip()
    title = str(releases.get("release_title") or f"Version {version}")
    parts = [f"<p>Version <strong>{html.escape(version)}</strong> is now available.</p>"]
    if releases.get("release_overview"):
        parts.append(f"<p>{html.escape(str(releases['release_overview']))}</p>")
    if releases.get("changelog"):
        parts.append(f"<p><strong>What's new:</strong> {html.escape(str(releases['changelog']))}</p>")
    return _dispatch(
        "releases",
        f"New release: {title}",
        html.escape(title),
        "".join(parts),
        url_for("audio_suite.downloads_view", _external=True),
        "Go to downloads",
    )


def notify_release(force: bool = False) -> dict:
    """Announces the active release exactly once per version.

    SCHEDULED releases go public by date with no event, so download page views call this too.
    The first call ever records an already-public version as a baseline instead of sending,
    so enabling the module never re-announces an old release. force=True sends a preview
    without recording, so the real announcement still fires when the release goes public.
    """
    from audio_suite_mod import get_releases_data, is_release_publicly_visible

    releases = get_releases_data()
    version = str(releases.get("version", "")).strip()
    if not version:
        return {"sent": 0, "message": "There is no active release version."}
    if force:
        sent = _send_release_email(releases)
        return {"sent": sent, "message": f"Sent a v{version} release notice to {sent} subscriber(s)."}

    visible = is_release_publicly_visible(releases)
    with _store_lock:
        if not NOTIFY_STATE_FILE.exists():
            _write_json(NOTIFY_STATE_FILE, {"announced_versions": [version] if visible else [], "updated_at": _now()})
            if visible:
                return {"sent": 0, "message": f"Recorded v{version} as already public. The next release will be announced."}
        if not visible:
            return {"sent": 0, "message": f"Version {version} is not public yet."}
        state = _read_json(NOTIFY_STATE_FILE, {})
        announced = state.setdefault("announced_versions", [])
        if version in announced:
            return {"sent": 0, "message": f"Version {version} was already announced."}
        announced.append(version)
        state["updated_at"] = _now()
        _write_json(NOTIFY_STATE_FILE, state)
    sent = _send_release_email(releases)
    return {"sent": sent, "message": f"Announced v{version} to {sent} subscriber(s)."}


def notify_download(package_id: str) -> int:
    from audio_suite_mod import get_releases_data

    releases = get_releases_data()
    package = releases.get("packages", {}).get(package_id, {})
    if package_id in ("git", "git_source"):
        name = package.get("title") or "JOSHY source code"
    else:
        name = package.get("title") or package_id
    version = str(releases.get("version", "")).strip()
    version_text = f" version {html.escape(version)}" if version else ""
    body = (
        f"<p>Thank you for downloading <strong>{html.escape(name)}</strong>{version_text}.</p>"
        "<p>Release notes and future updates are on the downloads page.</p>"
    )
    return _dispatch(
        "downloads",
        f"Thanks for downloading {name}",
        "Thank you for downloading",
        body,
        url_for("audio_suite.downloads_view", _external=True),
        "View release notes",
    )


def notify_newsletter(base_url: str = None) -> dict:
    """Dispatches personalized threat intelligence briefs to all active subscribers.
    
    Generates tailored multi-cadence emails with subscriber-selected appetites,
    safe alt-appetite curiosity teasers, audio CTA hooks, and zero-day radar cards.
    """
    from newsletter_mod import load_active_manifest
    from email_engine import build_personalized_newsletter_email, send_email

    manifest = load_active_manifest()
    items = manifest.get("items", [])
    if not items:
        return {"sent": 0, "message": "The active digest has no stories."}

    subscribers = [
        s for s in load_subscribers()
        if s.get("email") and s.get("status") == "active"
    ]
    if not subscribers:
        return {"sent": 0, "message": "No active newsletter subscribers found."}

    if not base_url:
        try:
            base_url = request.host_url.rstrip("/")
        except Exception:
            base_url = getattr(config, "BASE_URL", "http://127.0.0.1:5001")

    sent_count = 0
    errors = []

    for sub in subscribers:
        try:
            subject, html_body, text_body, headers = build_personalized_newsletter_email(
                subscriber=sub,
                manifest=manifest,
                base_url=base_url
            )
            ok, msg, _ = send_email(
                to_address=sub["email"],
                subject=subject,
                html_content=html_body,
                text_content=text_body,
                headers=headers
            )
            if ok:
                sent_count += 1
                record_newsletter_send(
                    sub.get("delivery", {}).get("format", "hybrid_brief"),
                    sub.get("content", {}).get("primary_appetite", "cyber_thriller")
                )
            else:
                errors.append(f"{sub['email']}: {msg}")
        except Exception as exc:
            errors.append(f"{sub['email']}: {str(exc)}")

    status_msg = f"Dispatched {sent_count} personalized threat briefs."
    if errors:
        status_msg += f" ({len(errors)} failed)"

    return {
        "sent": sent_count,
        "total_active": len(subscribers),
        "message": status_msg,
        "errors": errors
    }


def _download_succeeded(response) -> bool:
    if response.status_code == 200:
        return True
    if response.status_code in (301, 302, 303, 307, 308) and response.location:
        return urlparse(response.location).path != url_for("audio_suite.downloads_view")
    return False


@notify_bp.after_app_request
def observe_release_and_download_events(response):
    endpoint = request.endpoint or ""
    view_args = request.view_args or {}
    try:
        if endpoint in RELEASE_ENDPOINTS and response.status_code == 200:
            notify_release()
        elif endpoint in DOWNLOAD_ENDPOINTS or (endpoint == "dynamic_route" and view_args.get("path") == "downloads"):
            notify_release()
            if (
                endpoint == "audio_suite.download_package"
                and _download_succeeded(response)
                and (_is_admin() or not _admin_only_mode())
            ):
                notify_download(str(view_args.get("package_id", "")))
    except Exception as exc:
        current_app.logger.warning("Notification hook failed: %s", exc)
    return response


@notify_bp.route("/admin/notify")
def admin_notify_page():
    _require_admin()
    from audio_suite_mod import get_releases_data, is_release_publicly_visible
    from newsletter_mod import load_active_manifest

    releases = get_releases_data()
    with _store_lock:
        state = _read_json(NOTIFY_STATE_FILE, {})
    return render_template(
        "admin_notify.html",
        subscribers=load_subscribers(),
        topics=TOPICS,
        releases=releases,
        release_public=is_release_publicly_visible(releases),
        announced_versions=state.get("announced_versions", []),
        manifest=load_active_manifest(),
        admin_only=_admin_only_mode(),
    )


@notify_bp.route("/admin/notify/subscribers", methods=["POST"])
def admin_add_subscriber():
    data = _require_admin_json()
    topics = data.get("topics") or []
    if not isinstance(topics, list):
        topics = [topics]
    try:
        entry = add_subscriber(str(data.get("email", "")), [str(topic) for topic in topics])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True, "message": f"{entry['email']} subscribed to {', '.join(entry['topics'])}."})


@notify_bp.route("/admin/notify/subscribers/remove", methods=["POST"])
def admin_remove_subscriber():
    data = _require_admin_json()
    email = str(data.get("email", ""))
    if not remove_subscriber(email):
        return jsonify({"error": "That address is not subscribed."}), 404
    return jsonify({"success": True, "message": f"Removed {email.strip().lower()}."})


@notify_bp.route("/admin/notify/send/<kind>", methods=["POST"])
def admin_send_notification(kind: str):
    _require_admin_json()
    if kind == "release":
        result = notify_release(force=True)
    elif kind == "newsletter":
        result = notify_newsletter()
    else:
        abort(404)
    return jsonify({"success": True, **result})