"""
=============================================================================
   E-PROFILE HYBRID EMAIL ENGINE & MOCK MAIL SERVER
=============================================================================
Dual-mode email orchestration:
  1. 'local' Mode: Embedded, zero-dependency mock mailbox for testing/development.
     Captures all outbound emails locally to `cache/mailbox.json` and exposes
     them to the Admin Mailbox Viewer.
  2. 'smtp' Mode: Standard TLS/SMTP relay (Port 587) compatible with Gmail,
     Resend, SendGrid, Mailgun, and custom MTAs.

Enforces strict error resilience, thread safety, and HTML sanitization.
=============================================================================
"""

import os
import json
import uuid
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from config import Config

config = Config()
_mailbox_lock = threading.Lock()


def _ensure_cache_dir() -> Path:
    """Ensures that the cache directory exists."""
    target_dir = config.MAILBOX_FILE.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    return config.MAILBOX_FILE


def load_local_mailbox(limit: int = 100) -> List[Dict[str, Any]]:
    """Loads emails from the local JSON mailbox cache, newest first."""
    mailbox_path = _ensure_cache_dir()
    if not mailbox_path.exists():
        return []
    with _mailbox_lock:
        try:
            with open(mailbox_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
        except Exception:
            return []
    return []


def get_email_by_id(email_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single email record by its unique ID."""
    emails = load_local_mailbox(limit=500)
    for email in emails:
        if email.get("id") == email_id:
            return email
    return None


def clear_local_mailbox() -> bool:
    """Purges all records from the local mailbox cache."""
    mailbox_path = _ensure_cache_dir()
    with _mailbox_lock:
        try:
            with open(mailbox_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            return True
        except Exception:
            return False


def _append_to_local_mailbox(record: Dict[str, Any]) -> bool:
    """Appends an email record to the local mailbox cache."""
    mailbox_path = _ensure_cache_dir()
    with _mailbox_lock:
        try:
            current = []
            if mailbox_path.exists():
                try:
                    with open(mailbox_path, "r", encoding="utf-8") as f:
                        current = json.load(f)
                        if not isinstance(current, list):
                            current = []
                except Exception:
                    current = []
            current.insert(0, record)
            # Keep at most 200 emails in local cache
            current = current[:200]
            with open(mailbox_path, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
            return True
        except Exception:
            return False


def build_email_template(title: str, body_html: str, action_url: Optional[str] = None, action_label: Optional[str] = None) -> str:
    """Builds a responsive, accessible dark-themed HTML email adhering to E-Profile branding."""
    button_html = ""
    if action_url and action_label:
        button_html = f"""
        <div style="margin: 25px 0; text-align: center;">
            <a href="{action_url}" style="background-color: #00f3ff; color: #000; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block;">
                {action_label}
            </a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e0e0e0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0b; padding: 30px 15px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 600px; background-color: #121217; border: 1px solid rgba(0, 243, 255, 0.2); border-radius: 8px; padding: 30px;">
                    <tr>
                        <td style="border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 15px;">
                            <span style="font-size: 20px; font-weight: bold; color: #00f3ff; letter-spacing: 1px;">E-PROFILE SYSTEM</span>
                            <span style="float: right; font-size: 12px; color: #888;">Zero-Trust Hub</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top: 20px;">
                            <h2 style="color: #ffffff; margin-top: 0;">{title}</h2>
                            <div style="line-height: 1.6; font-size: 15px; color: #cccccc;">
                                {body_html}
                            </div>
                            {button_html}
                        </td>
                    </tr>
                    <tr>
                        <td style="border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 15px; font-size: 12px; color: #666; text-align: center;">
                            Automated notification dispatched from Michael Robberts E-Profile Platform.<br>
                            Access restricted under Role-Based Access Control (RBAC).
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def send_email(
    to_address: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    sender: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Dispatches an email through the configured backend ('local' or 'smtp').
    
    Returns:
        (success: bool, status_message: str, email_metadata: dict)
    """
    sender = sender or config.MAIL_DEFAULT_SENDER
    backend = config.MAIL_BACKEND.lower()
    email_id = str(uuid.uuid4())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Plaintext fallback from HTML if not supplied
    if not text_content:
        import re
        text_content = re.sub(r'<[^>]+>', ' ', html_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()

    record = {
        "id": email_id,
        "timestamp": now_str,
        "to": to_address,
        "from": sender,
        "subject": subject,
        "text": text_content,
        "html": html_content,
        "headers": headers or {},
        "backend": backend,
        "status": "QUEUED"
    }

    if backend == "local":
        record["status"] = "DELIVERED_LOCAL"
        record["details"] = "Captured in local mock mailbox (cache/mailbox.json)"
        _append_to_local_mailbox(record)
        return True, "Email successfully captured in local mailbox.", record

    elif backend == "smtp":
        try:
            # Fallback sender to authenticated username if sender is local mock or empty
            if ("eprofile.local" in (sender or "") or not sender) and config.MAIL_USERNAME:
                sender = config.MAIL_USERNAME.strip()

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_address

            if headers:
                for h_k, h_v in headers.items():
                    msg[h_k] = str(h_v)

            part1 = MIMEText(text_content, "plain", "utf-8")
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            server_host = config.MAIL_SERVER
            server_port = int(config.MAIL_PORT)
            use_tls = config.MAIL_USE_TLS
            username = config.MAIL_USERNAME.strip() if config.MAIL_USERNAME else ""
            
            # Google App Passwords have spaces when copied from Google security settings; clean them
            raw_password = config.MAIL_PASSWORD or ""
            if "gmail" in server_host.lower():
                password = raw_password.replace(" ", "").strip()
            else:
                password = raw_password.strip()

            if server_port == 465:
                server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
                server.ehlo()
            else:
                server = smtplib.SMTP(server_host, server_port, timeout=10)
                server.ehlo()
                if use_tls or server_port == 587 or "gmail" in server_host.lower():
                    server.starttls()
                    server.ehlo()

            if username and password:
                server.login(username, password)

            server.sendmail(sender, [to_address], msg.as_string())
            server.quit()

            record["status"] = "SENT_SMTP"
            record["details"] = f"Transmitted via {server_host}:{server_port}"
            _append_to_local_mailbox(record)
            return True, f"Email delivered via SMTP ({server_host}).", record

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP Authentication Failed (535): Username or App Password rejected by {config.MAIL_SERVER}. Check credentials."
            record["status"] = "FAILED"
            record["error"] = error_msg
            _append_to_local_mailbox(record)
            return False, error_msg, record
        except smtplib.SMTPSenderRefused as e:
            error_msg = f"Sender Refused: The sender address '{sender}' is rejected by SMTP server: {e.smtp_error}"
            record["status"] = "FAILED"
            record["error"] = error_msg
            _append_to_local_mailbox(record)
            return False, error_msg, record
        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"Recipient Refused: The destination address '{to_address}' was rejected. Ensure recipient exists."
            record["status"] = "FAILED"
            record["error"] = error_msg
            _append_to_local_mailbox(record)
            return False, error_msg, record
        except Exception as e:
            error_msg = f"SMTP Transmission Failed: {e}"
            record["status"] = "FAILED"
            record["error"] = error_msg
            _append_to_local_mailbox(record)
            return False, error_msg, record

    else:
        # Fallback for unrecognized backend
        record["status"] = "UNKNOWN_BACKEND"
        record["error"] = f"Unrecognized backend '{backend}'. Saved locally."
        _append_to_local_mailbox(record)
        return True, "Unrecognized backend; archived to local mailbox.", record


def test_smtp_connection() -> Tuple[bool, str]:
    """Tests the SMTP connection parameters defined in Config without sending an email."""
    if config.MAIL_BACKEND.lower() == "local":
        return True, "Email Engine is configured in 'local' mock mode. Real external connections are bypassed."

    try:
        port = int(config.MAIL_PORT)
        server_host = config.MAIL_SERVER
        username = config.MAIL_USERNAME.strip() if config.MAIL_USERNAME else ""
        raw_password = config.MAIL_PASSWORD or ""
        if "gmail" in server_host.lower():
            password = raw_password.replace(" ", "").strip()
        else:
            password = raw_password.strip()
        use_tls = config.MAIL_USE_TLS

        if port == 465:
            server = smtplib.SMTP_SSL(server_host, port, timeout=10)
            server.ehlo()
        else:
            server = smtplib.SMTP(server_host, port, timeout=10)
            server.ehlo()
            if use_tls or port == 587 or "gmail" in server_host.lower():
                server.starttls()
                server.ehlo()
        if username and password:
            server.login(username, password)
        server.quit()
        return True, f"Successfully connected to {server_host}:{port} and authenticated as '{username}'."
    except smtplib.SMTPAuthenticationError:
        return False, f"Authentication Failed (535): Invalid username or Google App Password. Ensure 2-Step Verification is enabled and use a 16-character App Password."
    except smtplib.SMTPConnectError as e:
        return False, f"Connection Failed: Could not connect to {config.MAIL_SERVER}:{config.MAIL_PORT}. Network or port issue."
    except Exception as e:
        return False, f"Connection failed: {e}"


def update_env_file(key_values: Dict[str, str]) -> bool:
    """Updates key-value pairs in .env file while preserving other existing lines."""
    env_path = config.ROOT_DIR / ".env"
    existing_lines = []
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()
        except Exception:
            existing_lines = []

    updated_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in key_values:
                new_lines.append(f"{k}={key_values[k]}\n")
                updated_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in key_values.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
    except Exception:
        return False


def apply_gateway_settings(
    backend: str,
    server_host: str,
    server_port: int,
    use_tls: bool,
    username: str,
    password: str,
    default_sender: str
) -> Tuple[bool, str]:
    """Applies new gateway settings both in-memory and persistently in .env."""
    username = (username or "").strip()
    raw_password = password or ""
    if "gmail" in server_host.lower():
        clean_password = raw_password.replace(" ", "").strip()
    else:
        clean_password = raw_password.strip()

    # Automatically set default sender to username if user is using SMTP and default sender is mock/empty
    if backend == "smtp" and username:
        if not default_sender or "eprofile.local" in default_sender:
            default_sender = username

    key_values = {
        "MAIL_BACKEND": backend,
        "MAIL_SERVER": server_host.strip(),
        "MAIL_PORT": str(server_port),
        "MAIL_USE_TLS": "True" if use_tls else "False",
        "MAIL_USERNAME": username,
        "MAIL_PASSWORD": clean_password,
        "MAIL_DEFAULT_SENDER": default_sender.strip(),
    }

    # 1. Update .env file
    file_saved = update_env_file(key_values)

    # 2. Update runtime environment variables
    for k, v in key_values.items():
        os.environ[k] = v

    # 3. Update runtime Config
    config.MAIL_BACKEND = backend
    config.MAIL_SERVER = server_host.strip()
    config.MAIL_PORT = int(server_port)
    config.MAIL_USE_TLS = use_tls
    config.MAIL_USERNAME = username
    config.MAIL_PASSWORD = clean_password
    config.MAIL_DEFAULT_SENDER = default_sender.strip()

    Config.MAIL_BACKEND = backend
    Config.MAIL_SERVER = server_host.strip()
    Config.MAIL_PORT = int(server_port)
    Config.MAIL_USE_TLS = use_tls
    Config.MAIL_USERNAME = username
    Config.MAIL_PASSWORD = clean_password
    Config.MAIL_DEFAULT_SENDER = default_sender.strip()

    if not file_saved:
        return False, "Failed to persist credentials to .env (applied in-memory only)."

    return True, "Email gateway credentials successfully updated and active!"


def apply_google_service_json(raw_json: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Validates and saves a Google service account or client secret JSON to disk."""
    try:
        parsed = json.loads(raw_json.strip())
        if not isinstance(parsed, dict):
            return False, "Invalid JSON structure: Expected a JSON object.", {}
    except Exception as e:
        return False, f"Invalid JSON syntax: {e}", {}

    target_path = config.ROOT_DIR / ".google_credentials.json"
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)
        os.chmod(target_path, 0o600)
    except Exception as e:
        return False, f"Failed to write Google JSON credentials: {e}", {}

    client_email = parsed.get("client_email") or parsed.get("web", {}).get("client_id") or "Google Credentials"
    project_id = parsed.get("project_id", "Default Project")

    update_env_file({"GOOGLE_APPLICATION_CREDENTIALS": str(target_path)})
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(target_path)

    metadata = {
        "path": str(target_path),
        "client_email": client_email,
        "project_id": project_id,
        "type": parsed.get("type", "oauth2/service_account")
    }

    return True, f"Google credentials JSON saved successfully for project '{project_id}'.", metadata


def build_personalized_newsletter_email(
    subscriber: Dict[str, Any],
    manifest: Dict[str, Any],
    base_url: str = ""
) -> Tuple[str, str, str, Dict[str, str]]:
    """
    Constructs a block-based, slot-resolved personalized Cyber Intelligence newsletter.
    
    Slots:
      Slot 1: Masthead Header (Brand, date, subscriber format/appetite greeting, 1-click pref link)
      Slot 2: Headlines Brief (Rendered for 'hybrid_brief' and 'weekly_digest')
      Slot 3: Featured Story (Rendered in subscriber's chosen appetite for 'full_story_daily' and 'hybrid_brief')
      Slot 4: Quick Threat Wire (Rendered for 'quick_threat_wire')
      Slot 5: Safe Engagement Hook: Alt-Appetite Teaser (Curiosity card with alternate perspective preview)
      Slot 6: Safe Engagement Hook: Audio Edition CTA (Hands-free listening on Accessible Audio Suite)
      Slot 7: Safe Engagement Hook: Bonus Zero-Day & KEV Radar (Emerging CVE table)
      Slot 8: RFC 8058 Footer (One-click unsubscribe & preference links)
      
    Returns:
      (subject: str, html_content: str, text_content: str, headers: Dict[str, str])
    """
    import html as html_lib
    import markdown
    from story_agent_dispatcher import APPETITE_CONFIG, get_cached_story, generate_builtin_appetite_story
    from notify_mod import encode_tracking_token

    clean_base = (base_url or "").rstrip("/")
    token = subscriber.get("token") or "token"
    delivery = subscriber.get("delivery") or {}
    content_pref = subscriber.get("content") or {}
    engagement = subscriber.get("engagement_modules") or {}

    delivery_format = delivery.get("format") or "hybrid_brief"
    primary_appetite = content_pref.get("primary_appetite") or "cyber_thriller"
    enable_alt_teaser = bool(engagement.get("alt_appetite_teaser", True))
    enable_audio = bool(engagement.get("audio_link", True))
    enable_radar = bool(engagement.get("zero_day_radar", True))

    items = manifest.get("items") or []
    dispatched_at = manifest.get("dispatched_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pref_url = f"{clean_base}/newsletter/preferences?token={token}" if clean_base else f"/newsletter/preferences?token={token}"
    unsub_url = f"{clean_base}/newsletter/unsubscribe?token={token}" if clean_base else f"/newsletter/unsubscribe?token={token}"
    unsub_purge_url = f"{clean_base}/newsletter/unsubscribe?token={token}&purge=1" if clean_base else f"/newsletter/unsubscribe?token={token}&purge=1"

    def track_url(slot: str, path: str) -> str:
        tok = encode_tracking_token(slot, path, sub_token=token)
        return f"{clean_base}/newsletter/r/{tok}" if clean_base else f"/newsletter/r/{tok}"

    featured_item = items[0] if items else {}
    featured_title = featured_item.get("title") or "Emerging Cyber Threats"
    featured_level = featured_item.get("threat_level") or "HIGH"
    featured_story_id = featured_item.get("story_id") or "threat-advisory"

    if delivery_format == "full_story_daily":
        subject = f"[Dossier] {featured_title} · Threat Level {featured_level}"
    elif delivery_format == "hybrid_brief":
        remaining_count = max(1, len(items) - 1)
        subject = f"[Cyber Intel Brief] {featured_title} + {remaining_count} Advisories"
    elif delivery_format == "quick_threat_wire":
        subject = f"[Threat Wire] {len(items)} Rapid Vulnerability Bulletins"
    elif delivery_format == "weekly_digest":
        subject = f"[Weekly Digest] Cyber Threat Debrief: {len(items)} Key Disclosures"
    else:
        subject = f"Cyber Threat Intelligence Brief: {featured_title}"

    format_labels = {
        "hybrid_brief": "Hybrid Brief (Headlines + Featured Dossier)",
        "full_story_daily": "Daily Full Story (Incident Dossier)",
        "quick_threat_wire": "Quick Threat Wire (1-Min Bulletins)",
        "weekly_digest": "Weekly Threat Debrief"
    }
    format_label = format_labels.get(delivery_format, delivery_format.replace("_", " ").title())
    app_cfg = APPETITE_CONFIG.get(primary_appetite, {
        "title": primary_appetite.replace("_", " ").title(),
        "badge_color": "#19e6ff"
    })
    appetite_label = app_cfg.get("title")
    appetite_color = app_cfg.get("badge_color", "#19e6ff")

    slots_html = []
    text_parts = []

    # Slot 1: Masthead Header
    slot1_html = f"""
    <div style="border-bottom: 1px solid rgba(25, 230, 255, 0.25); padding-bottom: 18px; margin-bottom: 22px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr>
                <td>
                    <div style="font-size: 11px; font-family: monospace; letter-spacing: 2px; color: #19e6ff; text-transform: uppercase;">
                        🛡️ SIRAUGA INTEL · ZERO-TRUST FEED
                    </div>
                    <h1 style="color: #ffffff; font-size: 22px; margin: 6px 0 4px 0; font-weight: 700;">
                        Cyber Threat Intelligence Dispatch
                    </h1>
                    <div style="font-size: 12px; color: #888899; font-family: monospace;">
                        Dispatched: {html_lib.escape(str(dispatched_at))} · Security Tier: Verified
                    </div>
                </td>
            </tr>
        </table>
        <div style="margin-top: 14px; background: rgba(25, 230, 255, 0.06); border: 1px solid rgba(25, 230, 255, 0.2); border-radius: 6px; padding: 10px 14px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                    <td style="font-size: 12px; color: #cccccc; font-family: monospace;">
                        Delivery: <strong style="color: #ffffff;">{html_lib.escape(format_label)}</strong><br>
                        Appetite: <strong style="color: {appetite_color};">{html_lib.escape(appetite_label)}</strong>
                    </td>
                    <td style="text-align: right; vertical-align: middle;">
                        <a href="{pref_url}" style="font-size: 11px; font-family: monospace; color: #19e6ff; text-decoration: none; border: 1px solid #19e6ff; padding: 4px 8px; border-radius: 4px; display: inline-block;">
                            ⚙️ Preferences
                        </a>
                    </td>
                </tr>
            </table>
        </div>
    </div>
    """
    slots_html.append(slot1_html)
    text_parts.append(f"CYBER THREAT INTELLIGENCE DISPATCH\nDispatched: {dispatched_at}\nDelivery: {format_label} | Appetite: {appetite_label}\nPreferences: {pref_url}\n" + "=" * 60)

    # Slot 2: Headlines Brief (for hybrid_brief and weekly_digest)
    if delivery_format in ("hybrid_brief", "weekly_digest"):
        headline_items = items[1:5] if delivery_format == "hybrid_brief" else items[:7]
        if not headline_items and delivery_format == "hybrid_brief" and items:
            headline_items = items[:1]

        headline_rows = []
        for it in headline_items:
            it_id = it.get("story_id") or "item"
            it_title = html_lib.escape(it.get("title") or "Security Advisory")
            it_score = it.get("score", 75)
            it_lvl = html_lib.escape(it.get("threat_level") or "HIGH")
            it_cves = ", ".join(it.get("cves") or []) or "Zero-Day"
            it_summary = html_lib.escape(it.get("summary") or "")
            it_url = track_url("headlines", f"/newsletter/story/{it_id}")
            
            badge_bg = "rgba(255, 77, 77, 0.2)" if it_score >= 90 else "rgba(255, 170, 0, 0.2)"
            badge_color = "#ff7878" if it_score >= 90 else "#ffaa00"

            headline_rows.append(f"""
            <div style="background: rgba(255, 255, 255, 0.02); border-left: 3px solid {badge_color}; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 12px 14px; margin-bottom: 12px;">
                <div style="font-size: 11px; font-family: monospace; margin-bottom: 4px;">
                    <span style="background: {badge_bg}; color: {badge_color}; padding: 2px 6px; border-radius: 3px; font-weight: bold;">
                        {it_lvl} ({it_score}/100)
                    </span>
                    <span style="color: #888899; margin-left: 6px;">{it_cves}</span>
                </div>
                <div style="font-size: 15px; font-weight: 600; margin-bottom: 4px;">
                    <a href="{it_url}" style="color: #19e6ff; text-decoration: none;">
                        {it_title} →
                    </a>
                </div>
                <div style="font-size: 13px; color: #aaaaaa; line-height: 1.4;">
                    {it_summary}
                </div>
            </div>
            """)
            text_parts.append(f"\n- [{it_lvl}] {it.get('title')}\n  CVEs: {it_cves}\n  Link: {it_url}\n  Summary: {it.get('summary')}")

        slot2_html = f"""
        <div style="margin-bottom: 24px;">
            <div style="font-size: 13px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px;">
                ⚡ Advisory Headlines Brief
            </div>
            {''.join(headline_rows) if headline_rows else '<div style="color: #888;">No additional headlines in this digest.</div>'}
        </div>
        """
        slots_html.append(slot2_html)

    # Slot 3: Featured Story (for full_story_daily and hybrid_brief)
    if delivery_format in ("full_story_daily", "hybrid_brief") and featured_item:
        cached = get_cached_story(featured_story_id, primary_appetite)
        if cached and cached.get("markdown"):
            story_md = cached["markdown"]
        else:
            story_md = generate_builtin_appetite_story(primary_appetite, featured_item)

        story_html_rendered = markdown.markdown(story_md, extensions=['tables', 'fenced_code'])
        featured_cta = track_url("featured_story", f"/newsletter/story/{featured_story_id}?appetite={primary_appetite}")

        slot3_html = f"""
        <div style="background: #151922; border: 1px solid rgba(25, 230, 255, 0.35); border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <div style="font-size: 11px; font-family: monospace; text-transform: uppercase; letter-spacing: 1.5px; color: {appetite_color}; margin-bottom: 6px; font-weight: bold;">
                🔥 Featured Dossier · {html_lib.escape(appetite_label)}
            </div>
            <h2 style="color: #ffffff; font-size: 20px; margin: 0 0 12px 0;">
                {html_lib.escape(featured_title)}
            </h2>
            <div style="font-size: 14px; color: #d0d7de; line-height: 1.6; margin-bottom: 18px;" class="story-rendered-body">
                {story_html_rendered}
            </div>
            <div style="text-align: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                <a href="{featured_cta}" style="background-color: #19e6ff; color: #000000; font-family: monospace; font-size: 13px; font-weight: bold; padding: 10px 22px; border-radius: 4px; text-decoration: none; display: inline-block;">
                    🛡️ Read Full Threat Dossier & Interactive Playbook →
                </a>
            </div>
        </div>
        """
        slots_html.append(slot3_html)
        text_parts.append(f"\nFEATURED DOSSIER: {featured_title}\n{story_md}\nFull Interactive Playbook: {featured_cta}")

    # Slot 4: Quick Threat Wire (for quick_threat_wire)
    if delivery_format == "quick_threat_wire":
        wire_rows = []
        for it in items:
            it_id = it.get("story_id") or "item"
            it_title = html_lib.escape(it.get("title") or "Security Alert")
            it_lvl = html_lib.escape(it.get("threat_level") or "HIGH")
            it_cves = ", ".join(it.get("cves") or []) or "Zero-Day"
            it_rem = html_lib.escape(it.get("remediation") or "Patch perimeter assets.")
            it_url = track_url("headlines", f"/newsletter/story/{it_id}")

            wire_rows.append(f"""
            <div style="font-family: monospace; font-size: 12px; background: rgba(5, 7, 10, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; padding: 10px 12px; margin-bottom: 8px;">
                <span style="color: #ffaa00; font-weight: bold;">[{it_lvl}]</span>
                <a href="{it_url}" style="color: #19e6ff; text-decoration: none; font-weight: bold;">{it_title}</a>
                <div style="color: #888899; margin-top: 4px;">CVEs: {it_cves} · Action: {it_rem}</div>
            </div>
            """)
            text_parts.append(f"[{it_lvl}] {it.get('title')} | CVE: {it_cves} | Action: {it.get('remediation')} | Link: {it_url}")

        slot4_html = f"""
        <div style="margin-bottom: 24px;">
            <div style="font-size: 13px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px;">
                ⚡ Rapid Threat Wire (1-Min Bulletins)
            </div>
            {''.join(wire_rows)}
        </div>
        """
        slots_html.append(slot4_html)

    # Slot 5: Engagement Hook: Alt-Appetite Teaser
    if enable_alt_teaser and delivery_format in ("hybrid_brief", "full_story_daily") and featured_item:
        all_apps = ["snarky_hacker", "executive_espresso", "deep_dive", "cyber_thriller", "defense_playbook"]
        alt_candidates = [a for a in all_apps if a != primary_appetite]
        alt_app = alt_candidates[0] if alt_candidates else "snarky_hacker"
        alt_cfg = APPETITE_CONFIG.get(alt_app, {})
        alt_title = alt_cfg.get("title", alt_app.replace("_", " ").title())
        alt_badge_color = alt_cfg.get("badge_color", "#ffaa00")

        alt_cached = get_cached_story(featured_story_id, alt_app)
        if alt_cached and alt_cached.get("markdown"):
            alt_md = alt_cached["markdown"]
        else:
            alt_md = generate_builtin_appetite_story(alt_app, featured_item)

        clean_lines = [l.strip() for l in alt_md.splitlines() if l.strip() and not l.strip().startswith("#")]
        teaser_snippet = " ".join(clean_lines[:2])[:240]
        if not teaser_snippet:
            teaser_snippet = f"Curious how defenders unpack {featured_title}? Explore this incident from another perspective."

        alt_cta = track_url("alt_teaser", f"/newsletter/story/{featured_story_id}?appetite={alt_app}")

        slot5_html = f"""
        <div style="background: rgba(255, 170, 0, 0.05); border: 1px dashed rgba(255, 170, 0, 0.4); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
            <div style="margin-bottom: 8px;">
                <span style="font-size: 11px; font-family: monospace; font-weight: bold; color: {alt_badge_color}; text-transform: uppercase;">
                    🎭 Alternate Perspective Preview · {html_lib.escape(alt_title)}
                </span>
                <span style="font-size: 11px; color: #888899; font-family: monospace; float: right;">Curiosity Hook</span>
            </div>
            <p style="font-size: 13px; color: #e6edf3; font-style: italic; margin: 0 0 12px 0; line-height: 1.5;">
                "{html_lib.escape(teaser_snippet)}..."
            </p>
            <div style="text-align: right;">
                <a href="{alt_cta}" style="color: #ffaa00; font-family: monospace; font-size: 12px; font-weight: bold; text-decoration: none;">
                    ⚡ Read the {html_lib.escape(alt_title)} Breakdown on Web Portal →
                </a>
            </div>
        </div>
        """
        slots_html.append(slot5_html)
        text_parts.append(f"\nALTERNATE PERSPECTIVE PREVIEW ({alt_title}):\n\"{teaser_snippet}...\"\nRead on Portal: {alt_cta}")

    # Slot 6: Engagement Hook: Audio Edition CTA
    if enable_audio:
        audio_cta = track_url("audio", "/audio")
        slot6_html = f"""
        <div style="background: rgba(0, 255, 136, 0.05); border: 1px solid rgba(0, 255, 136, 0.3); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                    <td style="vertical-align: middle;">
                        <div style="font-size: 11px; font-family: monospace; color: #00ff88; font-weight: bold; text-transform: uppercase; margin-bottom: 4px;">
                            🎧 Accessible Audio Suite · Hands-Free Briefing
                        </div>
                        <div style="font-size: 13px; color: #cccccc; line-height: 1.4;">
                            Commuting or prefer listening? Stream hands-free voice threat briefings directly in your browser or screen reader.
                        </div>
                    </td>
                    <td style="text-align: right; vertical-align: middle; padding-left: 15px; white-space: nowrap;">
                        <a href="{audio_cta}" style="background: rgba(0, 255, 136, 0.15); border: 1px solid #00ff88; color: #00ff88; font-family: monospace; font-size: 12px; font-weight: bold; padding: 8px 14px; border-radius: 4px; text-decoration: none; display: inline-block;">
                            ▶️ Stream Audio
                        </a>
                    </td>
                </tr>
            </table>
        </div>
        """
        slots_html.append(slot6_html)
        text_parts.append(f"\nAUDIO SUITE (Hands-free listening): {audio_cta}")

    # Slot 7: Engagement Hook: Bonus Zero-Day Radar
    if enable_radar:
        radar_items = [it for it in items if it.get("cves") or it.get("score", 0) >= 80][:3]
        if not radar_items:
            radar_items = items[:2]

        radar_cta = track_url("zero_day_radar", "/newsletter")
        radar_rows = []
        for r_it in radar_items:
            cve_str = ", ".join(r_it.get("cves") or []) or "Zero-Day"
            r_title = html_lib.escape(r_it.get("title", "")[:45])
            r_score = r_it.get("score", 80)
            radar_rows.append(f"""
            <tr>
                <td style="padding: 6px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); font-family: monospace; font-size: 12px; color: #19e6ff;">
                    {html_lib.escape(cve_str)}
                </td>
                <td style="padding: 6px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); font-size: 12px; color: #ffffff;">
                    {r_title}
                </td>
                <td style="padding: 6px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); font-family: monospace; font-size: 12px; color: #ff7878; text-align: right;">
                    {r_score}/100
                </td>
            </tr>
            """)

        slot7_html = f"""
        <div style="background: rgba(25, 230, 255, 0.03); border: 1px solid rgba(25, 230, 255, 0.2); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 10px;">
                <tr>
                    <td>
                        <span style="font-size: 11px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase;">
                            🔍 Bonus Zero-Day & KEV Radar
                        </span>
                    </td>
                    <td style="text-align: right;">
                        <a href="{radar_cta}" style="font-size: 11px; font-family: monospace; color: #19e6ff; text-decoration: none;">
                            Explore Radar →
                        </a>
                    </td>
                </tr>
            </table>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 6px;">
                <thead>
                    <tr style="text-align: left; font-size: 11px; font-family: monospace; color: #888899; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                        <th style="padding: 4px 8px;">CVE IDENTIFIER</th>
                        <th style="padding: 4px 8px;">AFFECTED COMPONENT</th>
                        <th style="padding: 4px 8px; text-align: right;">SEVERITY</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(radar_rows)}
                </tbody>
            </table>
        </div>
        """
        slots_html.append(slot7_html)
        text_parts.append(f"\nBONUS ZERO-DAY RADAR: {radar_cta}")

    # Slot 7b: E-Profile Development & Engineering News (Advertising & Releases)
    dev_projects_url = track_url("dev_releases", "/projects")
    audio_suite_url = track_url("audio_release", "/audio")
    slot_dev_news_html = f"""
    <div style="background: rgba(0, 243, 255, 0.04); border: 1px solid rgba(0, 243, 255, 0.22); border-radius: 8px; padding: 18px; margin-bottom: 24px;">
        <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #00f3ff; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px;">
            🚀 E-Profile Development & Engineering News
        </div>
        <h3 style="color: #ffffff; font-size: 15px; margin: 0 0 6px 0; font-weight: 600;">
            What's Happening in E-Profile Development & New Releases
        </h3>
        <p style="font-size: 13px; color: #c8d2e0; line-height: 1.5; margin: 0 0 10px 0;">
            We actively advertise and report ongoing software releases and architectural advancements in our dispatches. Recent milestones include zero-restart live staging, screen reader voice synthesis in the <strong>Accessible Audio Suite</strong>, and zero-database local flat-file privacy enhancements.
        </p>
        <div style="font-size: 12px; color: #8899aa; line-height: 1.4; margin-bottom: 12px;">
            📢 <strong>Policy & Governance Updates:</strong> Terms of service and privacy protocols are continuously updated to guarantee complete data minimization and subscriber sovereignty.
        </div>
        <table role="presentation" cellspacing="0" cellpadding="0">
            <tr>
                <td style="padding-right: 14px;">
                    <a href="{dev_projects_url}" style="color: #00f3ff; font-family: monospace; font-size: 12px; font-weight: bold; text-decoration: underline;">
                        Explore Engineering Projects & Roadmap →
                    </a>
                </td>
                <td>
                    <a href="{audio_suite_url}" style="color: #00ff88; font-family: monospace; font-size: 12px; font-weight: bold; text-decoration: underline;">
                        Audio Suite Releases →
                    </a>
                </td>
            </tr>
        </table>
    </div>
    """
    slots_html.append(slot_dev_news_html)
    text_parts.append(
        f"\nE-PROFILE DEVELOPMENT & RELEASES:\n"
        f"Ongoing updates on new software releases, Accessible Audio Suite, and policy changes.\n"
        f"Projects: {dev_projects_url}\nAudio Suite: {audio_suite_url}"
    )

    # Slot 7c: Author & Engineering Credibility (Credly & LinkedIn Verification)
    linkedin_url = "https://www.linkedin.com/in/michael-robberts-40b68a180"
    credly_profile_url = "https://www.credly.com/users/michael-robberts.d08637aa"
    credly_badge_url = "https://www.credly.com/badges/95063855-9875-40cd-9d3f-13bc9ad1448e"
    credly_badge_id = "95063855-9875-40cd-9d3f-13bc9ad1448e"

    slot_cred_html = f"""
    <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 18px; margin-bottom: 24px;">
        <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">
            🎖️ Author Credibility & Verified Qualifications
        </div>
        <div style="color: #ffffff; font-size: 15px; font-weight: 700; margin-bottom: 4px;">
            Michael Robberts
        </div>
        <div style="font-size: 12px; color: #888899; font-family: monospace; margin-bottom: 12px;">
            Cybersecurity Researcher & Systems Developer · IBM, CompTIA, Cisco Certified
        </div>
        <table role="presentation" cellspacing="0" cellpadding="0" style="margin-bottom: 14px;">
            <tr>
                <td style="padding-right: 10px;">
                    <a href="{linkedin_url}" style="display: inline-block; background: #0a66c2; color: #ffffff; text-decoration: none; font-size: 11px; font-family: monospace; font-weight: bold; padding: 6px 12px; border-radius: 4px;">
                        💼 LinkedIn Profile →
                    </a>
                </td>
                <td>
                    <a href="{credly_profile_url}" style="display: inline-block; background: #ff6b00; color: #ffffff; text-decoration: none; font-size: 11px; font-family: monospace; font-weight: bold; padding: 6px 12px; border-radius: 4px;">
                        🏅 Credly Verified Transcript →
                    </a>
                </td>
            </tr>
        </table>

        <!-- Verified Credly Badge Embed & Card -->
        <div style="background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 107, 0, 0.35); border-radius: 6px; padding: 14px; text-align: center;">
            <div style="font-size: 11px; font-family: monospace; color: #ffaa00; margin-bottom: 6px; font-weight: bold;">
                VERIFIED CREDLY DIGITAL BADGE · IBM DATA SCIENCE
            </div>
            <div style="font-size: 14px; color: #ffffff; font-weight: 600; margin-bottom: 4px;">
                Python for Data Science
            </div>
            <div style="font-size: 11px; color: #888899; font-family: monospace; margin-bottom: 10px;">
                Issued by IBM · Verification ID: {credly_badge_id}
            </div>
            <!-- Credly Live Badge Embed -->
            <div style="margin: 10px auto;">
                <div data-iframe-width="150" data-iframe-height="270" data-share-badge-id="{credly_badge_id}" data-share-badge-host="https://www.credly.com"></div>
                <script type="text/javascript" async src="//cdn.credly.com/assets/utilities/embed.js"></script>
            </div>
            <div style="margin-top: 8px;">
                <a href="{credly_badge_url}" style="color: #ffaa00; font-family: monospace; font-size: 11px; text-decoration: underline;">
                    Verify Badge Directly on Credly.com →
                </a>
            </div>
        </div>
    </div>
    """
    slots_html.append(slot_cred_html)
    text_parts.append(
        f"\nAUTHOR CREDIBILITY & VERIFIED CERTIFICATIONS:\n"
        f"Author: Michael Robberts (Cybersecurity Researcher & Developer)\n"
        f"LinkedIn Profile: {linkedin_url}\n"
        f"Credly Transcript: {credly_profile_url}\n"
        f"IBM Python for Data Science (Badge ID: {credly_badge_id}): {credly_badge_url}"
    )

    # Slot 8: Subscription Activity Requirement & 1-Click Unsubscribe Purge
    visit_site_url = track_url("active_keepalive", "/newsletter")
    terms_url = f"{clean_base}/terms" if clean_base else "/terms"

    slot8_html = f"""
    <!-- Subscription Activity Requirement Card -->
    <div style="margin: 24px 0 16px 0; padding: 14px 16px; background: rgba(255, 170, 0, 0.07); border: 1px solid rgba(255, 170, 0, 0.28); border-radius: 6px;">
        <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #ffaa00; text-transform: uppercase; margin-bottom: 4px;">
            ⏱️ Subscription Activity Requirement
        </div>
        <p style="margin: 0 0 8px 0; font-size: 12px; color: #d0d8e8; line-height: 1.45;">
            To ensure our local registry remains clean and intentional, we require subscribers to visit the site from time to time to keep their subscription active. If you do not visit the website from the emails you receive, we will consider that you did not subscribe to the service, and your records will be automatically purged.
        </p>
        <div style="text-align: right;">
            <a href="{visit_site_url}" style="color: #ffaa00; font-family: monospace; font-size: 12px; font-weight: bold; text-decoration: underline;">
                🌐 Visit E-Profile to Keep Subscription Active →
            </a>
        </div>
    </div>

    <!-- Accidental Subscription Notice & Pretty Unsubscribe Button -->
    <div style="margin: 0 0 20px 0; padding: 20px 16px; background-color: rgba(255, 77, 77, 0.08); border: 1px solid rgba(255, 77, 77, 0.3); border-radius: 8px; text-align: center;">
        <p style="margin: 0 0 12px 0; font-size: 13px; color: #ffffff; font-weight: 600; line-height: 1.4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            If you have not subscribed to this newsletter, please just hit that pretty button below to relieve your inbox.
        </p>
        <a href="{unsub_purge_url}" style="display: inline-block; background: linear-gradient(135deg, #e53935 0%, #d32f2f 100%); color: #ffffff; text-decoration: none; padding: 12px 28px; font-size: 13px; font-family: monospace, -apple-system, sans-serif; font-weight: bold; border-radius: 6px; border: 1px solid #ff4d4d; box-shadow: 0 4px 14px rgba(255, 77, 77, 0.4); letter-spacing: 0.5px;">
            🚫 1-Click Unsubscribe & Purge Data
        </a>
        <div style="margin-top: 10px; font-size: 10px; color: #ff9999; font-family: monospace;">
            Immediately and completely purges your email address and records from our local registry.
        </div>
    </div>

    <div style="border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 20px; font-size: 11px; color: #666677; text-align: center; line-height: 1.6;">
        <p style="margin: 0 0 8px 0;">
            You are receiving this intelligence brief because you subscribed at <strong>Michael Robberts E-Profile</strong>.
        </p>
        <p style="margin: 0 0 12px 0;">
            <a href="{pref_url}" style="color: #19e6ff; text-decoration: underline; margin-right: 10px;">⚙️ Manage Preferences</a>
            ·
            <a href="{terms_url}" style="color: #888899; text-decoration: underline; margin: 0 10px;">📄 Terms & Conditions</a>
            ·
            <a href="{unsub_purge_url}" style="color: #ff7878; text-decoration: underline; margin-left: 10px;">🚫 One-Click Purge</a>
        </p>
        <div style="font-size: 10px; color: #555566; font-family: monospace;">
            RFC 8058 Compliant · Zero-Database Local Storage Architecture
        </div>
    </div>
    """
    slots_html.append(slot8_html)
    text_parts.append(
        f"\n" + "=" * 60 +
        f"\nSUBSCRIPTION ACTIVITY REQUIREMENT:\n"
        f"We require subscribers to visit the site from time to time to keep their subscription active.\n"
        f"If you do not visit the website from the emails you receive, we will consider that you did not subscribe to the service, and your records will be purged.\n"
        f"Visit Website to Confirm Active Status: {visit_site_url}\n"
        f"\nACCIDENTAL SUBSCRIPTION? RELIEVE YOUR INBOX:\n"
        f"If you have not subscribed to this newsletter, please just hit that pretty button below to relieve your inbox.\n"
        f"1-Click Unsubscribe & Purge Data: {unsub_purge_url}\n"
        f"Manage Preferences: {pref_url}\n"
        f"Terms and Conditions: {terms_url}\n"
    )

    master_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_lib.escape(subject)}</title>
    <style>
        .story-rendered-body h1, .story-rendered-body h2, .story-rendered-body h3 {{ color: #ffffff; margin-top: 16px; margin-bottom: 8px; }}
        .story-rendered-body p {{ margin: 0 0 12px 0; }}
        .story-rendered-body ul, .story-rendered-body ol {{ margin: 0 0 12px 20px; padding: 0; }}
        .story-rendered-body li {{ margin-bottom: 4px; }}
        .story-rendered-body code {{ background: rgba(255, 255, 255, 0.1); color: #19e6ff; padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 12px; }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e0e0e0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0b; padding: 25px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 640px; background-color: #10141d; border: 1px solid rgba(25, 230, 255, 0.25); border-radius: 8px; padding: 24px; text-align: left;">
                    <tr>
                        <td>
                            {''.join(slots_html)}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    headers = {
        "List-Unsubscribe": f"<{unsub_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
    }

    plain_text = "\n".join(text_parts)
    return subject, master_html, plain_text, headers


def build_welcome_subscription_email(
    subscriber: Dict[str, Any],
    base_url: str = ""
) -> Tuple[str, str, str, Dict[str, str]]:
    """
    Constructs a responsive dark-themed welcome and subscription confirmation email.
    
    Informs the recipient of their subscription to Cyber Threat Intelligence, asks if
    they intended to subscribe, provides immediate access to their personal Preference Center,
    and features a prominent, immediate 1-Click Unsubscribe & Purge button to relieve their
    inbox immediately if it was not them.
    
    Returns:
      (subject: str, html_content: str, text_content: str, headers: Dict[str, str])
    """
    import html as html_lib

    clean_base = (base_url or "").rstrip("/")
    if not clean_base:
        clean_base = getattr(config, "BASE_URL", "https://mikeymike.pythonanywhere.com").rstrip("/")

    email = subscriber.get("email", "")
    token = subscriber.get("token") or "token"
    delivery = subscriber.get("delivery") or {}
    content_pref = subscriber.get("content") or {}
    
    chosen_format = delivery.get("format", "hybrid_brief")
    chosen_appetite = content_pref.get("primary_appetite", "cyber_thriller")
    
    format_label = chosen_format.replace("_", " ").title()
    appetite_label = chosen_appetite.replace("_", " ").title()

    unsub_url = f"{clean_base}/newsletter/unsubscribe?token={token}&purge=1"
    pref_url = f"{clean_base}/newsletter/preferences?token={token}"
    portal_url = f"{clean_base}/newsletter"
    terms_url = f"{clean_base}/terms"

    subject = "Welcome to Cyber Threat Intelligence – Did you subscribe?"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_lib.escape(subject)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e0e0e0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0b; padding: 25px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 640px; background-color: #10141d; border: 1px solid rgba(25, 230, 255, 0.25); border-radius: 8px; padding: 24px; text-align: left;">
                    <!-- Masthead -->
                    <tr>
                        <td style="border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 16px;">
                            <span style="font-size: 18px; font-weight: bold; color: #00f3ff; letter-spacing: 1.5px; font-family: monospace;">
                                E-PROFILE INTELLIGENCE SYSTEM
                            </span>
                            <span style="float: right; font-size: 11px; font-family: monospace; color: #00ff88; background: rgba(0, 255, 136, 0.1); border: 1px solid rgba(0, 255, 136, 0.3); padding: 3px 8px; border-radius: 4px;">
                                ACTIVE VERIFICATION
                            </span>
                        </td>
                    </tr>

                    <!-- Welcome Heading -->
                    <tr>
                        <td style="padding-top: 20px;">
                            <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">
                                📬 SUBSCRIPTION CONFIRMATION & WELCOME
                            </div>
                            <h2 style="color: #ffffff; font-size: 22px; margin: 0 0 14px 0; font-weight: 700;">
                                Welcome to Cyber Threat Intelligence!
                            </h2>
                            <p style="font-size: 15px; color: #d0d8e8; line-height: 1.6; margin: 0 0 20px 0;">
                                We received a subscription request for <strong style="color: #19e6ff;">{html_lib.escape(email)}</strong> to receive Cyber Threat Intelligence feeds, zero-day telemetry, and vulnerability advisories from Michael Robberts E-Profile.
                            </p>

                            <!-- Did you subscribe? Card -->
                            <div style="background: rgba(0, 243, 255, 0.04); border: 1px solid rgba(0, 243, 255, 0.25); border-radius: 8px; padding: 18px; margin-bottom: 20px;">
                                <h3 style="color: #00f3ff; font-size: 16px; margin: 0 0 8px 0;">
                                    ✅ Did you subscribe?
                                </h3>
                                <p style="font-size: 13px; color: #cbd5e1; line-height: 1.5; margin: 0 0 12px 0;">
                                    If this was you, you're all set! You will receive tailored intelligence updates according to your selected format (<strong>{html_lib.escape(format_label)}</strong>) and primary appetite (<strong>{html_lib.escape(appetite_label)}</strong>).
                                </p>
                                <p style="font-size: 13px; color: #94a3b8; line-height: 1.5; margin: 0 0 14px 0;">
                                    You can fine-tune your threat topics, delivery frequency, or audio briefing preferences at any time in your private Preference Center:
                                </p>
                                <div>
                                    <a href="{pref_url}" style="background-color: #00f3ff; color: #000000; padding: 10px 20px; text-decoration: none; font-weight: bold; font-size: 13px; font-family: monospace; border-radius: 4px; display: inline-block;">
                                        ⚙️ Manage Preferences & Confirm Settings →
                                    </a>
                                </div>
                            </div>

                            <!-- Accidental Subscription Notice & Pretty Unsubscribe Button -->
                            <div style="margin: 0 0 20px 0; padding: 20px 16px; background-color: rgba(255, 77, 77, 0.08); border: 1px solid rgba(255, 77, 77, 0.35); border-radius: 8px; text-align: center;">
                                <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #ff7878; text-transform: uppercase; margin-bottom: 6px;">
                                    ⚠️ ACCIDENTAL SUBSCRIPTION OR NOT YOU?
                                </div>
                                <h3 style="color: #ffffff; font-size: 16px; margin: 0 0 8px 0;">
                                    Was this not you?
                                </h3>
                                <p style="margin: 0 0 14px 0; font-size: 13px; color: #f1f5f9; line-height: 1.45; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                    If you did not subscribe, or if someone else entered your email, click the button below to cancel immediately and permanently purge all records from our registry:
                                </p>
                                <a href="{unsub_url}" style="display: inline-block; background: linear-gradient(135deg, #e53935 0%, #d32f2f 100%); color: #ffffff; text-decoration: none; padding: 12px 28px; font-size: 13px; font-family: monospace, -apple-system, sans-serif; font-weight: bold; border-radius: 6px; border: 1px solid #ff4d4d; box-shadow: 0 4px 14px rgba(255, 77, 77, 0.4); letter-spacing: 0.5px;">
                                    🚫 1-Click Unsubscribe & Purge Data
                                </a>
                                <div style="margin-top: 10px; font-size: 11px; color: #ff9999; font-family: monospace;">
                                    Immediately and completely purges your email address from our local registry.
                                </div>
                            </div>

                            <!-- Subscription Activity Requirement Card -->
                            <div style="margin: 0 0 20px 0; padding: 14px 16px; background: rgba(255, 170, 0, 0.07); border: 1px solid rgba(255, 170, 0, 0.28); border-radius: 6px;">
                                <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #ffaa00; text-transform: uppercase; margin-bottom: 4px;">
                                    ⏱️ Subscription Activity Requirement
                                </div>
                                <p style="margin: 0 0 8px 0; font-size: 12px; color: #d0d8e8; line-height: 1.45;">
                                    To ensure our local registry remains clean and intentional, we require subscribers to visit the site from time to time to keep their subscription active. If you do not visit the website from the emails you receive, we will consider that you did not subscribe to the service, and your records will be automatically purged.
                                </p>
                                <div style="text-align: right;">
                                    <a href="{portal_url}" style="color: #ffaa00; font-family: monospace; font-size: 12px; font-weight: bold; text-decoration: underline;">
                                        🌐 Visit Live Threat Feed →
                                    </a>
                                </div>
                            </div>

                            <!-- Footer -->
                            <div style="border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 16px; font-size: 11px; color: #64748b; text-align: center; line-height: 1.6;">
                                <p style="margin: 0 0 6px 0;">
                                    Michael Robberts E-Profile Platform · Automated Notification Dispatched via Secure SMTP
                                </p>
                                <p style="margin: 0 0 8px 0;">
                                    <a href="{pref_url}" style="color: #19e6ff; text-decoration: underline; margin-right: 10px;">⚙️ Manage Preferences</a>
                                    ·
                                    <a href="{terms_url}" style="color: #94a3b8; text-decoration: underline; margin: 0 10px;">📄 Terms & Conditions</a>
                                    ·
                                    <a href="{unsub_url}" style="color: #ff7878; text-decoration: underline; margin-left: 10px;">🚫 One-Click Purge</a>
                                </p>
                                <div style="font-size: 10px; color: #475569; font-family: monospace;">
                                    RFC 8058 Compliant · Zero-Database Local Storage Architecture
                                </div>
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    plain_text = f"""============================================================
CYBER THREAT INTELLIGENCE · SUBSCRIPTION CONFIRMATION
============================================================

Hello,

We received a subscription request for {email} to receive Cyber Threat Intelligence feeds and advisories from Michael Robberts E-Profile.

------------------------------------------------------------
DID YOU SUBSCRIBE?
------------------------------------------------------------
If this was you, you're all set! You will receive tailored threat intelligence dispatches according to your selected format ({format_label}) and primary appetite ({appetite_label}).

Manage Preferences & Confirm Settings:
{pref_url}

------------------------------------------------------------
WAS THIS NOT YOU?
------------------------------------------------------------
If you did not subscribe, or if someone else entered your email, click the link below to cancel immediately and permanently purge your email from our records:

1-Click Unsubscribe & Purge Data:
{unsub_url}

------------------------------------------------------------
SUBSCRIPTION ACTIVITY REQUIREMENT:
------------------------------------------------------------
We require subscribers to visit the site from time to time to keep their subscription active.
If you do not visit the website from the emails you receive, we will consider that you did not subscribe to the service, and your records will be automatically purged.

Visit Live Threat Feed:
{portal_url}

------------------------------------------------------------
Terms and Conditions: {terms_url}
RFC 8058 Compliant · Zero-Database Local Storage Architecture
"""

    headers = {
        "List-Unsubscribe": f"<{unsub_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
    }

    return subject, html_content, plain_text, headers


def send_welcome_email(
    subscriber: Dict[str, Any],
    base_url: str = ""
) -> Tuple[bool, str, Dict[str, Any]]:
    """Builds and delivers a welcome confirmation email to a new subscriber.
    
    Returns:
        (success: bool, status_message: str, email_metadata: dict)
    """
    subject, html_content, text_content, headers = build_welcome_subscription_email(subscriber, base_url=base_url)
    return send_email(
        to_address=subscriber["email"],
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        headers=headers
    )



