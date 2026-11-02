"""Admin subscriber registry, security controls, double opt-in verification,
and release, download, and newsletter notifications.

Includes:
- Strict file permission enforcement (0o600).
- Sliding-window IP rate limiting on public subscription endpoints.
- Honeypot spam bot trapping.
- Disposable & temporary domain blocking.
- Cryptographic double opt-in verification tokens with 48h expiration.
- RFC 8058 One-Click List-Unsubscribe handling & non-reversible suppression hashing.
- PII masking helper for administrative dashboards.
"""

import html
import json
import os
import re
import secrets
import time
import hashlib
import hmac
import threading
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict, Any, List

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for

from config import Config

config = Config()
notify_bp = Blueprint("notify", __name__)

CACHE_DIR = config.ROOT_DIR / "cache"
SUBSCRIBERS_FILE = CACHE_DIR / "subscribers.json"
SUPPRESSION_FILE = CACHE_DIR / "suppression_list.json"
NOTIFY_STATE_FILE = CACHE_DIR / "notify_state.json"
TOPICS = ("releases", "downloads", "newsletter")
EMAIL_PATTERN = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")
RELEASE_ENDPOINTS = {"audio_suite.schedule_publish_now", "audio_suite.stage_update_release"}
DOWNLOAD_ENDPOINTS = {"audio_suite.downloads_view", "audio_suite.download_package"}

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "throwawaymail.com", "getairmail.com", "dispostable.com",
    "yopmail.com", "trashmail.com", "fakeinbox.com", "burnermail.io",
    "temp-mail.org", "guerrillamailblock.com"
}

_store_lock = threading.Lock()
_rate_limit_lock = threading.Lock()
_rate_limits: Dict[str, List[float]] = {}


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


def _check_rate_limit(ip: str, max_requests: int = 5, window_seconds: int = 600) -> bool:
    """Sliding-window IP rate limiter. Max 5 subscription requests per 10 minutes per IP."""
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limits.setdefault(ip, [])
        valid = [t for t in timestamps if now - t < window_seconds]
        if len(valid) >= max_requests:
            _rate_limits[ip] = valid
            return False
        valid.append(now)
        _rate_limits[ip] = valid
        return True


def is_disposable_domain(email: str) -> bool:
    if "@" not in email:
        return True
    domain = email.split("@")[-1].strip().lower()
    return domain in DISPOSABLE_DOMAINS


def _read_json(path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return data if isinstance(data, type(default)) else default


def _write_json(path, data) -> None:
    """Atomically writes JSON and sets strict 0o600 file permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(staging, 0o600)
    except OSError:
        pass
    staging.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _hash_email(address: str) -> str:
    """Returns a non-reversible HMAC-SHA256 blind hash of the email."""
    secret = (getattr(config, "SECRET_KEY", "EPROFILE_SALT") or "EPROFILE_SALT").encode("utf-8")
    return hmac.new(secret, address.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()


def is_suppressed(address: str) -> bool:
    h = _hash_email(address)
    with _store_lock:
        suppression = _read_json(SUPPRESSION_FILE, [])
        return h in suppression


def add_to_suppression(address: str) -> None:
    h = _hash_email(address)
    with _store_lock:
        suppression = _read_json(SUPPRESSION_FILE, [])
        if h not in suppression:
            suppression.append(h)
            _write_json(SUPPRESSION_FILE, suppression)


def remove_from_suppression(address: str) -> None:
    h = _hash_email(address)
    with _store_lock:
        suppression = _read_json(SUPPRESSION_FILE, [])
        if h in suppression:
            suppression = [x for x in suppression if x != h]
            _write_json(SUPPRESSION_FILE, suppression)


def mask_email(address: str) -> str:
    """Masks email for display: security@domain.com -> s***y@d***n.com"""
    if not address or "@" not in address:
        return "***"
    local, domain = address.split("@", 1)
    masked_local = (local[0] + "***" + local[-1]) if len(local) > 2 else (local[0] + "***")
    parts = domain.split(".")
    if len(parts) >= 2:
        main_d = parts[0]
        ext = ".".join(parts[1:])
        masked_d = (main_d[0] + "***" + main_d[-1]) if len(main_d) > 2 else (main_d[0] + "***")
        return f"{masked_local}@{masked_d}.{ext}"
    return f"{masked_local}@***"


def load_subscribers(mask: bool = False) -> list:
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
    if mask:
        masked = []
        for s in subscribers:
            item = dict(s)
            item["email_masked"] = mask_email(item.get("email", ""))
            masked.append(item)
        return masked
    return subscribers


def add_subscriber(email: str, topics, status: str = "pending", merge: bool = True) -> dict:
    address = (email or "").strip().lower()
    if len(address) > 254 or not EMAIL_PATTERN.match(address):
        raise ValueError("Enter a valid email address.")
    if is_disposable_domain(address):
        raise ValueError("Disposable or temporary email domains are not permitted.")
    chosen = sorted({topic for topic in topics if topic in TOPICS})
    if not chosen:
        raise ValueError("Choose at least one topic.")
    
    # Remove from suppression list if user explicitly re-subscribes
    remove_from_suppression(address)

    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("email") == address), None)
        if entry is None:
            entry = {
                "email": address,
                "token": secrets.token_urlsafe(32),
                "added_at": _now(),
                "topics": []
            }
            subscribers.append(entry)

        if merge and "topics" in entry:
            merged = set(entry.get("topics", [])) | set(chosen)
            entry["topics"] = sorted(merged)
        else:
            entry["topics"] = chosen

        # If already active, keep active; otherwise set status and 48-hour expiration
        if entry.get("status") != "active":
            entry["status"] = status
            entry["verify_expires_at"] = (datetime.now() + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")

        entry["updated_at"] = _now()
        _write_json(SUBSCRIBERS_FILE, subscribers)
    return entry


def verify_subscriber_token(token: str) -> Tuple[bool, str, Optional[dict]]:
    """Verifies a subscriber's token and marks them active."""
    if not token or len(token) < 16:
        return False, "Invalid verification link.", None
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("token") == token), None)
        if not entry:
            return False, "Verification token not found or already expired.", None

        if entry.get("status") == "pending":
            exp_str = entry.get("verify_expires_at")
            if exp_str:
                try:
                    exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                    if datetime.now() > exp_dt:
                        return False, "Verification link has expired. Please subscribe again.", None
                except Exception:
                    pass

        entry["status"] = "active"
        entry["verified_at"] = _now()
        entry["updated_at"] = _now()
        _write_json(SUBSCRIBERS_FILE, subscribers)
        return True, "Your subscription has been verified successfully!", entry


def unsubscribe_subscriber_token(token: str) -> Tuple[bool, str]:
    """Unsubscribes a user by token and adds their hash to the suppression list."""
    if not token or len(token) < 16:
        return False, "Invalid unsubscribe token."
    with _store_lock:
        subscribers = _read_json(SUBSCRIBERS_FILE, [])
        entry = next((s for s in subscribers if s.get("token") == token), None)
        if not entry:
            return False, "Subscription record not found or already unsubscribed."

        email = entry.get("email", "")
        if email:
            add_to_suppression(email)

        entry["status"] = "unsubscribed"
        entry["unsubscribed_at"] = _now()
        entry["updated_at"] = _now()
        _write_json(SUBSCRIBERS_FILE, subscribers)
        return True, "You have been successfully unsubscribed from all notifications."


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
        s for s in load_subscribers()
        if s.get("email") and s.get("status") == "active" and topic in s.get("topics", [])
    ]


def _dispatch(topic, subject, title, body_html, action_url=None, action_label=None) -> int:
    """Sends one individually addressed email per recipient with List-Unsubscribe headers
    and dedicated unsubscribe footer link, on a daemon thread."""
    from email_engine import build_email_template, send_email

    targets = recipients_for(topic)
    if not targets:
        return 0
    logger = current_app.logger

    def deliver():
        for sub in targets:
            address = sub["email"]
            token = sub.get("token", "")
            unsub_url = url_for("notify.public_unsubscribe", token=token, _external=True) if token else None
            content = build_email_template(
                title=title,
                body_html=body_html,
                action_url=action_url,
                action_label=action_label,
                unsubscribe_url=unsub_url,
                recipient_email=address
            )
            ok, message, _ = send_email(
                to_address=address,
                subject=subject,
                html_content=content,
                list_unsubscribe_url=unsub_url
            )
            if not ok:
                logger.warning("Notification to %s failed: %s", address, message)

    threading.Thread(target=deliver, name=f"notify-{topic}", daemon=True).start()
    return len(targets)


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


def notify_newsletter() -> dict:
    """Emails the active digest. Every story field is escaped because the manifest can be
    replaced through /api/newsletter/new-digest, which has no authentication."""
    from newsletter_mod import load_active_manifest

    manifest = load_active_manifest()
    items = manifest.get("items", [])
    if not items:
        return {"sent": 0, "message": "The active digest has no stories."}
    sections = []
    for item in items:
        story_id = str(item.get("story_id", "")).strip()
        title = html.escape(str(item.get("title") or story_id or "Untitled advisory"))
        if story_id:
            link = html.escape(url_for("newsletter.newsletter_story", story_id=story_id, _external=True))
            title = f'<a href="{link}" style="color: #00f3ff;">{title}</a>'
        section = f'<h3 style="color: #ffffff; margin-bottom: 4px;">{title}</h3>'
        if item.get("threat_level"):
            section += f"<p style=\"margin: 0;\"><strong>Threat level:</strong> {html.escape(str(item['threat_level']))}</p>"
        if item.get("summary"):
            section += f"<p>{html.escape(str(item['summary']))}</p>"
        sections.append(section)
    dispatched = html.escape(str(manifest.get("dispatched_at", "")))
    body = f"<p>{len(items)} advisories in this digest ({dispatched}).</p>" + "".join(sections)
    sent = _dispatch(
        "newsletter",
        "Cyber Threat Newsletter",
        "Cyber Threat Newsletter",
        body,
        url_for("newsletter.newsletter_index", _external=True),
        "Read on the website",
    )
    return {"sent": sent, "message": f"Sent the digest to {sent} newsletter subscriber(s)."}


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


# --- PUBLIC SUBSCRIPTION, VERIFICATION & UNSUBSCRIBE ROUTES ---

@notify_bp.route("/api/subscribe", methods=["POST"])
def public_subscribe():
    """Public subscription endpoint with rate limiting, anti-bot trap, and double opt-in."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if not _check_rate_limit(client_ip):
        return jsonify({
            "success": False,
            "error": "Too many requests. Please wait a few minutes before trying again."
        }), 429

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    email = str(data.get("email", "")).strip()

    # Honeypot spam defense
    if data.get("website"):
        return jsonify({"success": True, "message": "Thank you for subscribing!"})

    topics_raw = data.get("topics")
    if not topics_raw:
        topics = ["newsletter"]
    elif isinstance(topics_raw, str):
        topics = [t.strip().lower() for t in topics_raw.split(",") if t.strip()]
    elif isinstance(topics_raw, list):
        topics = [str(t).strip().lower() for t in topics_raw if str(t).strip()]
    else:
        topics = ["newsletter"]

    try:
        entry = add_subscriber(email, topics, status="pending", merge=True)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    # Dispatch double opt-in verification email
    try:
        from email_engine import build_email_template, send_email
        verify_url = url_for("notify.public_verify", token=entry["token"], _external=True)
        unsub_url = url_for("notify.public_unsubscribe", token=entry["token"], _external=True)
        topics_str = ", ".join(t.capitalize() for t in entry["topics"])
        
        body_html = f"""
        <p>Hello,</p>
        <p>You recently requested to subscribe to <strong>{html.escape(topics_str)}</strong> updates on the Michael Robberts E-Profile Platform.</p>
        <p>To confirm your subscription and start receiving notifications, please click the button below:</p>
        <div style="margin: 25px 0; text-align: center;">
            <a href="{verify_url}" style="background-color: #00f3ff; color: #000; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block;">
                Confirm My Subscription
            </a>
        </div>
        <p style="font-size: 12px; color: #888;">This link will expire in 48 hours. If you did not make this request, you can safely ignore this email.</p>
        """
        html_content = build_email_template(
            title="Confirm Your Subscription",
            body_html=body_html,
            unsubscribe_url=unsub_url,
            recipient_email=entry["email"]
        )
        threading.Thread(
            target=send_email,
            kwargs={
                "to_address": entry["email"],
                "subject": f"Please Confirm Your Subscription ({topics_str})",
                "html_content": html_content,
                "list_unsubscribe_url": unsub_url
            },
            daemon=True
        ).start()
    except Exception as exc:
        current_app.logger.warning("Failed to dispatch verification email: %s", exc)

    return jsonify({
        "success": True,
        "message": "Confirmation link dispatched! Please check your inbox to activate your subscription."
    })


@notify_bp.route("/api/subscribe/verify/<token>")
def public_verify(token: str):
    """Activates pending subscription upon link click."""
    ok, msg, entry = verify_subscriber_token(token)
    topics = entry.get("topics", []) if entry else []
    return render_template(
        "subscribe_status.html",
        title="Subscription Verified" if ok else "Verification Failed",
        message=msg,
        status="success" if ok else "error",
        action="verified" if ok else "error",
        topics=topics
    )


@notify_bp.route("/api/unsubscribe/<token>")
def public_unsubscribe(token: str):
    """One-click unsubscribe endpoint."""
    ok, msg = unsubscribe_subscriber_token(token)
    return render_template(
        "subscribe_status.html",
        title="Unsubscribed" if ok else "Unsubscribe Notice",
        message=msg,
        status="success" if ok else "error",
        action="unsubscribed" if ok else "error",
        topics=[]
    )


# --- ADMIN DASHBOARD & CONTROLS ---

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
        subscribers=load_subscribers(mask=True),
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
        # Admins add subscribers directly as active
        entry = add_subscriber(str(data.get("email", "")), [str(topic) for topic in topics], status="active")
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