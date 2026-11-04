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
    Constructs a personalized Cyber Intelligence newsletter tailored to the subscriber's
    chosen appetite format:
      1. 'headlines'      : Instant Radar Skimmer (Headlines + Release Time + 1-Click to Newsfeed)
      2. 'briefs'         : Executive Briefings (Headlines + 2-3 Sentence Brief + Read More on Site)
      3. 'deep_dive'      : Technical Deep Dive & Remediation Playbook (Forensics, Mechanics, Runbook)
      4. 'reconstruction' : Attack Reconstruction Playbook (Educational Threat Simulation, Stages, Detection)
      5. 'cyber_thriller' : Narrative Cyber Thriller (Cinematic Storytelling, Accessible to Non-Experts)

    Returns:
      (subject: str, html_content: str, text_content: str, headers: Dict[str, str])
    """
    import html as html_lib
    import markdown
    from story_agent_dispatcher import APPETITE_CONFIG, get_cached_story, generate_builtin_appetite_story
    from threat_intel_engine import format_display_date
    from notify_mod import encode_tracking_token

    clean_base = (base_url or "").rstrip("/")
    token = subscriber.get("token") or "token"
    delivery = subscriber.get("delivery") or {}
    content_pref = subscriber.get("content") or {}

    raw_style = content_pref.get("primary_appetite") or delivery.get("format") or "briefs"
    style_map = {
        "headlines": "headlines",
        "quick_threat_wire": "headlines",
        "briefs": "briefs",
        "hybrid_brief": "briefs",
        "weekly_digest": "briefs",
        "executive_espresso": "briefs",
        "deep_dive": "deep_dive",
        "defense_playbook": "deep_dive",
        "reconstruction": "reconstruction",
        "cyber_thriller": "cyber_thriller",
        "snarky_hacker": "cyber_thriller",
    }
    target_style = style_map.get(raw_style, "briefs")

    items = manifest.get("items") or []
    pref_url = f"{clean_base}/newsletter/preferences?token={token}" if clean_base else f"/newsletter/preferences?token={token}"
    unsub_purge_url = f"{clean_base}/newsletter/unsubscribe?token={token}&purge=1" if clean_base else f"/newsletter/unsubscribe?token={token}&purge=1"
    visit_site_url = f"{clean_base}/newsletter" if clean_base else "/newsletter"
    terms_url = f"{clean_base}/terms-and-conditions" if clean_base else "/terms-and-conditions"

    def track_url(slot: str, path: str) -> str:
        tok = encode_tracking_token(slot, path, sub_token=token)
        return f"{clean_base}/newsletter/r/{tok}" if clean_base else f"/newsletter/r/{tok}"

    featured_item = items[0] if items else {}
    featured_title = featured_item.get("title") or "Critical Cyber Threat Intelligence"
    featured_date = featured_item.get("display_date") or format_display_date(featured_item.get("timestamp", 0), featured_item.get("date", ""))
    featured_id = featured_item.get("story_id") or "threat-advisory"
    featured_score = featured_item.get("score", 85)
    featured_level = featured_item.get("threat_level", "HIGH")
    featured_cves = ", ".join(featured_item.get("cves") or []) or "Active Vector"

    content_blocks = []
    text_parts = []

    # 1. Masthead Header
    masthead_meta = {
        "headlines": ("⚡ SIRAUGA THREAT RADAR · DIRECT WIRE", "#19e6ff", "Radar Headlines Skimmer"),
        "briefs": ("📋 SIRAUGA EXECUTIVE BRIEFINGS · ADVISORY FEED", "#b388ff", "Executive Briefing"),
        "deep_dive": ("🔬 SIRAUGA TECHNICAL INTELLIGENCE · FORENSICS & REMEDIATION", "#00ff88", "Technical Deep Dive & Remediation"),
        "reconstruction": ("⚔️ SIRAUGA DEFENSE SIMULATION · PURPLE-TEAM LAB", "#ffaa00", "Attack Reconstruction Playbook"),
        "cyber_thriller": ("🍿 SIRAUGA CYBER THRILLER · INSIDE THE BREACH", "#ff7878", "Cyber Thriller Narrative"),
    }
    masthead_title, masthead_color, appetite_label = masthead_meta.get(target_style, masthead_meta["briefs"])

    masthead_html = f"""
    <div style="border-bottom: 1px solid rgba(25, 230, 255, 0.25); padding-bottom: 16px; margin-bottom: 20px;">
        <div style="font-size: 11px; font-family: monospace; letter-spacing: 2px; color: {masthead_color}; text-transform: uppercase;">
            {masthead_title}
        </div>
        <div style="font-size: 12px; color: #888899; font-family: monospace; margin-top: 4px;">
            Release Stream · Latest Advisory: <strong style="color: #ffffff;">{featured_date}</strong>
        </div>
        <div style="margin-top: 12px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 8px 12px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                    <td style="font-size: 12px; color: #cccccc; font-family: monospace;">
                        Format Style: <strong style="color: {masthead_color};">{html_lib.escape(appetite_label)}</strong>
                    </td>
                    <td style="text-align: right; vertical-align: middle;">
                        <a href="{pref_url}" style="font-size: 11px; font-family: monospace; color: #19e6ff; text-decoration: none; border: 1px solid #19e6ff; padding: 4px 8px; border-radius: 4px; display: inline-block;">
                            ⚙️ Switch Style
                        </a>
                    </td>
                </tr>
            </table>
        </div>
    </div>
    """
    content_blocks.append(masthead_html)

    # Format 1: Just Headlines (Instant Radar Skimmer)
    if target_style == "headlines":
        subject = f"[⚡ Radar Headlines] {featured_title} · {featured_date}"
        text_parts.append(f"⚡ SIRAUGA THREAT RADAR · DIRECT WIRE\nReleased: {featured_date}\n\nHEADLINES WIRE:\n")

        headline_rows = []
        for it in items[:7]:
            it_id = it.get("story_id") or "item"
            it_title = html_lib.escape(it.get("title") or "Security Alert")
            it_date = it.get("display_date") or format_display_date(it.get("timestamp", 0), it.get("date", ""))
            it_lvl = html_lib.escape(it.get("threat_level") or "HIGH")
            it_score = it.get("score", 80)
            it_cves = html_lib.escape(", ".join(it.get("cves") or []) or "Zero-Day")
            it_url = track_url("headline", f"/newsletter/story/{it_id}?appetite=headlines")

            badge_color = "#ff7878" if it_score >= 90 else "#ffaa00"
            badge_bg = "rgba(255, 77, 77, 0.2)" if it_score >= 90 else "rgba(255, 170, 0, 0.2)"

            headline_rows.append(f"""
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(25, 230, 255, 0.2); border-left: 4px solid {badge_color}; border-radius: 6px; padding: 14px 16px; margin-bottom: 12px;">
                <div style="margin-bottom: 6px; font-family: monospace; font-size: 11px;">
                    <span style="background: {badge_bg}; color: {badge_color}; padding: 2px 6px; border-radius: 3px; font-weight: bold;">
                        {it_lvl} ({it_score}/100) · {it_cves}
                    </span>
                    <span style="color: #888899; margin-left: 8px;">{it_date}</span>
                </div>
                <div style="font-size: 16px; font-weight: 600; line-height: 1.4; margin-bottom: 10px;">
                    <a href="{it_url}" style="color: #ffffff; text-decoration: none;">
                        {it_title}
                    </a>
                </div>
                <div>
                    <a href="{it_url}" style="display: inline-block; background-color: #19e6ff; color: #000000; font-family: monospace; font-size: 12px; font-weight: bold; padding: 6px 14px; border-radius: 4px; text-decoration: none;">
                        ⚡ View on Newsfeed →
                    </a>
                </div>
            </div>
            """)
            text_parts.append(f"- [{it_lvl}] {it.get('title')}\n  Released: {it_date} | {it_cves}\n  Link: {it_url}\n")

        content_blocks.append(f"""
        <div style="margin-bottom: 24px;">
            <div style="font-size: 12px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">
                ⚡ Real-Time Radar Headlines (1-Click Direct Access)
            </div>
            <p style="color: #a0aec0; font-size: 13px; margin: 0 0 16px 0;">
                Direct threat radar with zero long scrolling. Click any bulletin to open the verified advisory immediately on the newsfeed.
            </p>
            {''.join(headline_rows)}
        </div>
        """)

    # Format 2: Headline Briefs (Executive Brief + Read More)
    elif target_style == "briefs":
        subject = f"[📋 Executive Brief] {featured_title} + {max(1, len(items)-1)} Advisories"
        text_parts.append(f"📋 SIRAUGA EXECUTIVE BRIEFINGS\nReleased: {featured_date}\n\n")

        brief_rows = []
        for it in items[:5]:
            it_id = it.get("story_id") or "item"
            it_title = html_lib.escape(it.get("title") or "Security Advisory")
            it_date = it.get("display_date") or format_display_date(it.get("timestamp", 0), it.get("date", ""))
            it_lvl = html_lib.escape(it.get("threat_level") or "HIGH")
            it_score = it.get("score", 80)
            it_summary = html_lib.escape(it.get("summary") or "Adversary threat campaign.")
            it_url = track_url("briefs", f"/newsletter/story/{it_id}?appetite=briefs")

            badge_color = "#ff7878" if it_score >= 90 else "#ffaa00"

            brief_rows.append(f"""
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid {badge_color}; border-radius: 8px; padding: 18px 20px; margin-bottom: 16px;">
                <div style="font-family: monospace; font-size: 11px; color: #888899; margin-bottom: 6px;">
                    <span style="color: {badge_color}; font-weight: bold;">[{it_lvl}]</span> · Released: <strong style="color: #ffffff;">{it_date}</strong>
                </div>
                <h3 style="color: #ffffff; font-size: 17px; margin: 0 0 8px 0; line-height: 1.4;">
                    <a href="{it_url}" style="color: #ffffff; text-decoration: none;">
                        {it_title}
                    </a>
                </h3>
                <p style="color: #c8d2e0; font-size: 13.5px; line-height: 1.6; margin: 0 0 12px 0;">
                    {it_summary}
                </p>
                <div>
                    <a href="{it_url}" style="display: inline-block; background: rgba(25, 230, 255, 0.15); border: 1px solid #19e6ff; color: #19e6ff; font-family: monospace; font-size: 12px; font-weight: bold; padding: 7px 16px; border-radius: 4px; text-decoration: none;">
                        📖 Read More on Site →
                    </a>
                </div>
            </div>
            """)
            text_parts.append(f"### {it.get('title')}\nReleased: {it_date}\n{it.get('summary')}\nRead More: {it_url}\n\n")

        content_blocks.append(f"""
        <div style="margin-bottom: 24px;">
            <div style="font-size: 12px; font-family: monospace; font-weight: bold; color: #b388ff; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">
                📋 Executive Threat Briefings
            </div>
            <p style="color: #a0aec0; font-size: 13px; margin: 0 0 16px 0;">
                Concise executive takeaways explaining threat exposure, blast radius, and decision questions.
            </p>
            {''.join(brief_rows)}
        </div>
        """)

    # Format 3: Technical Deep Dive & Remediation Playbook
    elif target_style == "deep_dive":
        subject = f"[🔬 Deep Dive & Remediation] {featured_title}"
        cached = get_cached_story(featured_id, "deep_dive")
        raw_story = (cached.get("markdown") if cached else "") or generate_builtin_appetite_story("deep_dive", featured_item)
        story_html = markdown.markdown(raw_story, extensions=['tables', 'fenced_code'])
        featured_cta = track_url("deep_dive", f"/newsletter/story/{featured_id}?appetite=deep_dive")

        text_parts.append(f"🔬 TECHNICAL DEEP DIVE & REMEDIATION PLAYBOOK\nReleased: {featured_date}\n\n{raw_story}\nFull Interactive Playbook: {featured_cta}\n")

        content_blocks.append(f"""
        <div style="background: rgba(0, 255, 136, 0.04); border: 1px solid rgba(0, 255, 136, 0.35); border-radius: 8px; padding: 22px; margin-bottom: 24px;">
            <div style="font-size: 11px; font-family: monospace; color: #00ff88; text-transform: uppercase; letter-spacing: 1.5px; font-weight: bold; margin-bottom: 6px;">
                🔬 Forensic Root-Cause Analysis & Blue-Team Runbook
            </div>
            <div style="font-size: 11px; font-family: monospace; color: #888899; margin-bottom: 12px;">
                Released: <strong style="color: #ffffff;">{featured_date}</strong> · Identifiers: {featured_cves}
            </div>
            <h2 style="color: #ffffff; font-size: 20px; margin: 0 0 14px 0; line-height: 1.3;">
                {html_lib.escape(featured_title)}
            </h2>
            <div style="font-size: 14px; color: #d0d7de; line-height: 1.6;" class="story-rendered-body">
                {story_html}
            </div>
            <div style="text-align: center; margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                <a href="{featured_cta}" style="display: inline-block; background-color: #00ff88; color: #000000; font-family: monospace; font-size: 13px; font-weight: bold; padding: 10px 22px; border-radius: 4px; text-decoration: none;">
                    🔬 Inspect Full Technical Dossier & Playbook on Site →
                </a>
            </div>
        </div>
        """)

    # Format 4: Attack Reconstruction Playbook (Educational Simulation)
    elif target_style == "reconstruction":
        subject = f"[⚔️ Threat Reconstruction Playbook] {featured_title}"
        cached = get_cached_story(featured_id, "reconstruction")
        raw_story = (cached.get("markdown") if cached else "") or generate_builtin_appetite_story("reconstruction", featured_item)
        story_html = markdown.markdown(raw_story, extensions=['tables', 'fenced_code'])
        featured_cta = track_url("reconstruction", f"/newsletter/story/{featured_id}?appetite=reconstruction")

        text_parts.append(f"⚔️ ATTACK RECONSTRUCTION & SIMULATION PLAYBOOK\nReleased: {featured_date}\n\n{raw_story}\nAccess Lab Reconstruction: {featured_cta}\n")

        content_blocks.append(f"""
        <div style="background: rgba(255, 170, 0, 0.04); border: 1px solid rgba(255, 170, 0, 0.35); border-radius: 8px; padding: 22px; margin-bottom: 24px;">
            <div style="font-size: 11px; font-family: monospace; color: #ffaa00; text-transform: uppercase; letter-spacing: 1.5px; font-weight: bold; margin-bottom: 6px;">
                ⚔️ Educational Threat Simulation & Reconstruction
            </div>
            <div style="font-size: 11px; font-family: monospace; color: #888899; margin-bottom: 12px;">
                Released: <strong style="color: #ffffff;">{featured_date}</strong> · Sandbox Scope: Authorized Labs
            </div>
            <h2 style="color: #ffffff; font-size: 20px; margin: 0 0 14px 0; line-height: 1.3;">
                {html_lib.escape(featured_title)}
            </h2>
            <div style="font-size: 14px; color: #d0d7de; line-height: 1.6;" class="story-rendered-body">
                {story_html}
            </div>
            <div style="text-align: center; margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                <a href="{featured_cta}" style="display: inline-block; background-color: #ffaa00; color: #000000; font-family: monospace; font-size: 13px; font-weight: bold; padding: 10px 22px; border-radius: 4px; text-decoration: none;">
                    ⚔️ Access Complete Lab Reconstruction & Defense Guide on Site →
                </a>
            </div>
        </div>
        """)

    # Format 5: Cyber Thriller (Narrative Story)
    else:  # cyber_thriller
        subject = f"[🍿 Cyber Thriller] {featured_title}"
        cached = get_cached_story(featured_id, "cyber_thriller")
        raw_story = (cached.get("markdown") if cached else "") or generate_builtin_appetite_story("cyber_thriller", featured_item)
        story_html = markdown.markdown(raw_story, extensions=['tables', 'fenced_code'])
        featured_cta = track_url("cyber_thriller", f"/newsletter/story/{featured_id}?appetite=cyber_thriller")

        text_parts.append(f"🍿 CYBER THRILLER (NARRATIVE)\nReleased: {featured_date}\n\n{raw_story}\nRead Full Story: {featured_cta}\n")

        content_blocks.append(f"""
        <div style="background: rgba(255, 120, 120, 0.04); border: 1px solid rgba(255, 120, 120, 0.35); border-radius: 8px; padding: 22px; margin-bottom: 24px;">
            <div style="font-size: 11px; font-family: monospace; color: #ff7878; text-transform: uppercase; letter-spacing: 1.5px; font-weight: bold; margin-bottom: 6px;">
                🍿 Inside the Breach · Cyber Thriller Narrative
            </div>
            <div style="font-size: 11px; font-family: monospace; color: #888899; margin-bottom: 12px;">
                Incident Released: <strong style="color: #ffffff;">{featured_date}</strong> · Non-Technical Reading Format
            </div>
            <h2 style="color: #ffffff; font-size: 20px; margin: 0 0 14px 0; line-height: 1.3;">
                {html_lib.escape(featured_title)}
            </h2>
            <div style="font-size: 14.5px; color: #d0d7de; line-height: 1.7;" class="story-rendered-body">
                {story_html}
            </div>
            <div style="text-align: center; margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
                <a href="{featured_cta}" style="display: inline-block; background-color: #ff7878; color: #000000; font-family: monospace; font-size: 13px; font-weight: bold; padding: 10px 22px; border-radius: 4px; text-decoration: none;">
                    🍿 Read the Full Cyber Thriller on Site →
                </a>
            </div>
        </div>
        """)

    # Footer: Activity requirement and RFC 8058 links (Zero download links in email)
    footer_html = f"""
    <div style="margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 20px;">
        <div style="background: rgba(25, 230, 255, 0.04); border: 1px solid rgba(25, 230, 255, 0.15); border-radius: 6px; padding: 12px 14px; margin-bottom: 18px; font-size: 11px; color: #a0aec0; line-height: 1.5;">
            <strong style="color: #19e6ff;">Active Subscription Requirement:</strong> We require subscribers to visit the site from time to time to keep their subscription active. If you do not visit the website from the emails you receive, your subscription record will be automatically purged.
            <div style="margin-top: 6px;">
                <a href="{visit_site_url}" style="color: #19e6ff; text-decoration: underline; font-weight: bold;">Visit Website to Keep Active →</a>
            </div>
        </div>
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 0 auto 16px auto;">
            <tr>
                <td align="center" bgcolor="#d32f2f" style="border-radius: 6px; background-color: #d32f2f; border: 1px solid #ff4d4d;">
                    <a href="{unsub_purge_url}" target="_blank" role="button" aria-label="1-Click Unsubscribe & Purge Data" style="display: inline-block; padding: 10px 24px; font-family: monospace, sans-serif; font-size: 12px; font-weight: bold; color: #ffffff; text-decoration: none; border-radius: 6px;">
                        🚫 1-Click Unsubscribe & Purge Data
                    </a>
                </td>
            </tr>
        </table>
        <div style="font-size: 11px; color: #666677; text-align: center; line-height: 1.6;">
            <p style="margin: 0 0 6px 0;">
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
    </div>
    """
    content_blocks.append(footer_html)

    text_parts.append(
        f"\n" + "=" * 60 +
        f"\nACTIVE SUBSCRIPTION REQUIREMENT:\n"
        f"We require subscribers to visit the site from time to time to keep their subscription active.\n"
        f"Visit Website to Confirm Active Status: {visit_site_url}\n"
        f"\n1-Click Unsubscribe & Purge Data: {unsub_purge_url}\n"
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
        .story-rendered-body h1, .story-rendered-body h2, .story-rendered-body h3 {{ color: #ffffff; margin-top: 14px; margin-bottom: 6px; }}
        .story-rendered-body p {{ margin: 0 0 10px 0; }}
        .story-rendered-body ul, .story-rendered-body ol {{ margin: 0 0 10px 20px; padding: 0; }}
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
                            {''.join(content_blocks)}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    clean_unsub_url = f"{clean_base}/newsletter/unsubscribe?token={token}"
    headers = {
        "List-Unsubscribe": f"<{clean_unsub_url}>",
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
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 0;">
                                        <tr>
                                            <td align="center" bgcolor="#00f3ff" style="border-radius: 4px; background-color: #00f3ff;">
                                                <a href="{pref_url}" target="_blank" role="button" aria-label="Manage Preferences & Confirm Settings" style="display: inline-block; background-color: #00f3ff; color: #000000; padding: 10px 22px; text-decoration: none; font-weight: bold; font-size: 13px; font-family: monospace, -apple-system, sans-serif; border-radius: 4px; border: 1px solid #00d2de;">
                                                    ⚙️ Manage Preferences & Confirm Settings →
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                </div>
                            </div>

                            <!-- Accidental Subscription Notice & Pretty Unsubscribe Button -->
                            <div style="margin: 0 0 20px 0; padding: 20px 16px; background-color: #1a0f12; border: 1px solid #772228; border-radius: 8px; text-align: center;">
                                <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #ff7878; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px;">
                                    ⚠️ ACCIDENTAL SUBSCRIPTION OR NOT YOU?
                                </div>
                                <h3 style="color: #ffffff; font-size: 16px; margin: 0 0 8px 0; font-weight: 700;">
                                    Was this not you?
                                </h3>
                                <p style="margin: 0 0 16px 0; font-size: 13px; color: #f1f5f9; line-height: 1.45; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                    If you did not subscribe, or if someone else entered your email, click the button below to cancel immediately and permanently purge all records from our registry:
                                </p>
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 0 auto;">
                                    <tr>
                                        <td align="center" bgcolor="#d32f2f" style="border-radius: 6px; background-color: #d32f2f; background: linear-gradient(135deg, #e53935 0%, #b71c1c 100%); border: 1px solid #ff4d4d; box-shadow: 0 4px 14px rgba(255, 77, 77, 0.4);">
                                            <a href="{unsub_url}" target="_blank" role="button" aria-label="1-Click Unsubscribe & Purge Data" style="display: inline-block; padding: 12px 28px; font-family: monospace, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: bold; color: #ffffff; text-decoration: none; letter-spacing: 0.5px; border-radius: 6px; -webkit-text-size-adjust: none;">
                                                🚫 1-Click Unsubscribe & Purge Data
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                <div style="margin-top: 12px; font-size: 11px; color: #ff9999; font-family: monospace;">
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

    clean_unsub_url = f"{clean_base}/newsletter/unsubscribe?token={token}"
    headers = {
        "List-Unsubscribe": f"<{clean_unsub_url}>",
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



