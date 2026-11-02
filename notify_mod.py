"""Admin-only subscriber registry and release, download and newsletter notifications.

Every route answers 404 to non-admin sessions so the feature's existence is not
disclosed. While NOTIFY_ADMIN_ONLY is true (the default when Config omits it),
download thank-you emails fire only for admin downloads, so no visitor is emailed
before the consent and confirmation flow ships.
"""

import html
import json
import re
import secrets
import threading
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for

from config import Config

config = Config()
notify_bp = Blueprint("notify", __name__)

CACHE_DIR = config.ROOT_DIR / "cache"
SUBSCRIBERS_FILE = CACHE_DIR / "subscribers.json"
NOTIFY_STATE_FILE = CACHE_DIR / "notify_state.json"
TOPICS = ("releases", "downloads", "newsletter")
EMAIL_PATTERN = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")
RELEASE_ENDPOINTS = {"audio_suite.schedule_publish_now", "audio_suite.stage_update_release"}
DOWNLOAD_ENDPOINTS = {"audio_suite.downloads_view", "audio_suite.download_package"}

_store_lock = threading.Lock()


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


def load_subscribers() -> list:
    with _store_lock:
        return _read_json(SUBSCRIBERS_FILE, [])


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
        _write_json(SUBSCRIBERS_FILE, subscribers)
    return entry


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