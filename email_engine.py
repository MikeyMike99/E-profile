"""
=============================================================================
   E-PROFILE HYBRID EMAIL ENGINE & MOCK MAIL SERVER
=============================================================================
Dual-mode email orchestration:
  1. 'local' Mode: Embedded, zero-dependency mock mailbox for testing/development.
     Captures all outbound emails locally to `cache/mailbox.json` and exposes
     them to the Admin Mailbox Viewer.
  2. 'smtp' Mode: Standard TLS/SMTP relay (Port 587 / 465) compatible with Gmail,
     Resend, SendGrid, Mailgun, and custom MTAs.

Enforces strict error resilience, thread safety, delivery honesty, and HTML sanitization.
=============================================================================
"""

import os
import json
import uuid
import smtplib
import threading
import html as html_lib
import re
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


# ---------------------------------------------------------------------------
# Delivery Core & Honesty Rules
# ---------------------------------------------------------------------------

SMTP_MISSING_CREDENTIALS_ERROR = (
    "SMTP delivery failed: Missing MAIL_USERNAME or MAIL_PASSWORD in configuration. No email sent."
)


def _smtp_credentials() -> Tuple[str, str]:
    """Returns (username, password) from Config, stripping Google App Password spaces."""
    username = (config.MAIL_USERNAME or "").strip()
    raw_password = config.MAIL_PASSWORD or ""
    if "gmail" in (config.MAIL_SERVER or "").lower():
        password = raw_password.replace(" ", "").strip()
    else:
        password = raw_password.strip()
    return username, password


def _open_smtp_connection(username: str, password: str) -> smtplib.SMTP:
    """Opens and authenticates an SMTP connection (SSL on 465, STARTTLS otherwise)."""
    server_host = config.MAIL_SERVER
    server_port = int(config.MAIL_PORT)
    if server_port == 465:
        server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
        server.ehlo()
    else:
        server = smtplib.SMTP(server_host, server_port, timeout=10)
        server.ehlo()
        if config.MAIL_USE_TLS or server_port == 587 or "gmail" in server_host.lower():
            server.starttls()
            server.ehlo()
    try:
        server.login(username, password)
    except Exception:
        server.close()
        raise
    return server


def _record_failure(record: Dict[str, Any], error_msg: str) -> Tuple[bool, str, Dict[str, Any]]:
    record["status"] = "FAILED"
    record["error"] = error_msg
    _append_to_local_mailbox(record)
    return False, error_msg, record


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
        record["details"] = "Captured in local mock mailbox (cache/mailbox.json). External delivery bypassed."
        _append_to_local_mailbox(record)
        return True, "Email captured in local mailbox (NOT sent over the internet).", record

    if backend == "smtp":
        username, password = _smtp_credentials()
        if not username or not password:
            return _record_failure(record, SMTP_MISSING_CREDENTIALS_ERROR)

        # Fallback sender to authenticated username if sender is local mock or empty
        if not sender or "eprofile.local" in sender:
            sender = username
            record["from"] = sender

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_address
        for h_k, h_v in (headers or {}).items():
            msg[h_k] = str(h_v)
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        server_host = config.MAIL_SERVER
        server_port = int(config.MAIL_PORT)
        try:
            server = _open_smtp_connection(username, password)
            try:
                server.sendmail(sender, [to_address], msg.as_string())
            finally:
                try:
                    server.quit()
                except Exception:
                    server.close()
        except smtplib.SMTPAuthenticationError:
            return _record_failure(record, f"SMTP Authentication Failed (535): Username or App Password rejected by {server_host}. Check credentials.")
        except smtplib.SMTPSenderRefused as e:
            return _record_failure(record, f"Sender Refused: The sender address '{sender}' is rejected by SMTP server: {e.smtp_error}")
        except smtplib.SMTPRecipientsRefused:
            return _record_failure(record, f"Recipient Refused: The destination address '{to_address}' was rejected. Ensure recipient exists.")
        except Exception as e:
            return _record_failure(record, f"SMTP Transmission Failed: {e}")

        record["status"] = "SENT_SMTP"
        record["details"] = f"Transmitted via {server_host}:{server_port}"
        _append_to_local_mailbox(record)
        return True, f"Email delivered via SMTP ({server_host}).", record

    # Fallback for unrecognized backend
    record["status"] = "UNKNOWN_BACKEND"
    record["error"] = f"Unrecognized backend '{backend}'. Saved locally."
    _append_to_local_mailbox(record)
    return True, "Unrecognized backend; archived to local mailbox.", record


def test_smtp_connection() -> Tuple[bool, str]:
    """Tests the SMTP connection parameters defined in Config without sending an email."""
    if config.MAIL_BACKEND.lower() == "local":
        return True, "Email Engine is configured in 'local' mock mode. Real external connections are bypassed."

    username, password = _smtp_credentials()
    if not username or not password:
        return False, "Missing MAIL_USERNAME or MAIL_PASSWORD in configuration. Cannot authenticate."

    try:
        server = _open_smtp_connection(username, password)
        server.quit()
        return True, f"Successfully connected to {config.MAIL_SERVER}:{config.MAIL_PORT} and authenticated as '{username}'."
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication Failed (535): Invalid username or Google App Password. Ensure 2-Step Verification is enabled and use a 16-character App Password."
    except smtplib.SMTPConnectError:
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
            else:
                new_lines.append(line)
        else:
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


# ---------------------------------------------------------------------------
# Personalized newsletter: every appetite style is a TEASER that drives the
# reader to the full story on the site. No full story dumps in email.
# ---------------------------------------------------------------------------

_APPETITE_STYLE_MAP = {
    "headlines": "headlines", "quick_threat_wire": "headlines",
    "briefs": "briefs", "hybrid_brief": "briefs", "weekly_digest": "briefs", "executive_espresso": "briefs",
    "deep_dive": "deep_dive", "defense_playbook": "deep_dive",
    "reconstruction": "reconstruction",
    "cyber_thriller": "cyber_thriller", "snarky_hacker": "cyber_thriller",
}

# style -> (emoji, label, accent color, CTA label)
_STYLE_META = {
    "headlines": ("⚡", "Radar Headlines", "#19e6ff", "⚡ Open on Newsfeed →"),
    "briefs": ("📋", "Executive Brief", "#b388ff", "📖 Read More on Site →"),
    "deep_dive": ("🔬", "Deep Dive", "#00ff88", "🔬 Inspect Full Deep Dive on Site →"),
    "reconstruction": ("⚔️", "Attack Reconstruction", "#ffaa00", "⚔️ Access Complete Lab Simulation on Site →"),
    "cyber_thriller": ("🍿", "Cyber Thriller", "#ff7878", "🍿 Continue Story on Site →"),
}

_ALT_STYLE = {
    "headlines": "briefs",
    "briefs": "cyber_thriller",
    "deep_dive": "cyber_thriller",
    "reconstruction": "cyber_thriller",
    "cyber_thriller": "deep_dive",
}

_ALT_HOOKS = {
    "briefs": "Short on time? The same advisory distilled into a three-sentence executive brief.",
    "deep_dive": "The headline tells you what broke. The deep dive tells you why it was breakable.",
    "cyber_thriller": "What did this look like from inside the SOC at 3 AM? Read it as a cyber thriller.",
}

_LAYOUT_LABELS = {
    "hybrid_brief": "Hybrid Brief (Headlines + Featured Dossier)",
    "quick_threat_wire": "Rapid Threat Wire (1-Min Bulletins)",
    "weekly_digest": "Weekly Threat Debrief",
    "full_story_daily": "Daily Featured Dossier",
}

LINKEDIN_URL = "https://www.linkedin.com/in/michael-robberts-40b68a180"
CREDLY_URL = "https://www.credly.com/users/michael-robberts.d08637aa"
CREDLY_BADGE_ID = "95063855-9875-40cd-9d3f-13bc9ad1448e"
INBOX_RELIEF_NOTICE = (
    "If you have not subscribed to this newsletter, please just hit that pretty button below to relieve your inbox."
)


def _first_sentences(text: str, count: int) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if p.strip()]
    return " ".join(parts[:count])


def _story_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    from threat_intel_engine import format_display_date
    return {
        "id": item.get("story_id") or "threat-advisory",
        "title": item.get("title") or "Critical Cyber Threat Intelligence",
        "date": item.get("display_date") or format_display_date(item.get("timestamp", 0), item.get("date", "")),
        "level": str(item.get("threat_level") or "HIGH"),
        "score": item.get("score", 80),
        "cves": item.get("cves") or [],
        "summary": item.get("summary") or "",
        "remediation": item.get("remediation") or "",
        "source": item.get("source") or "threat telemetry",
    }


def _cta(url: str, label: str, color: str) -> str:
    return (
        f'<a href="{url}" style="display: inline-block; background-color: {color}; color: #000000; '
        f'font-family: monospace; font-size: 12px; font-weight: bold; padding: 8px 18px; '
        f'border-radius: 4px; text-decoration: none;">{label}</a>'
    )


def _section(color: str, kicker: str, inner_html: str) -> str:
    return f"""
    <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.1); border-left: 4px solid {color}; border-radius: 8px; padding: 18px 20px; margin-bottom: 20px;">
        <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: {color}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">{kicker}</div>
        {inner_html}
    </div>"""


def _paragraph(text: str) -> str:
    return f'<p style="margin: 0 0 10px 0; color: #c8d2e0; font-size: 14px; line-height: 1.6;">{text}</p>'


def _headline_bulletin(f: Dict[str, Any], url: str) -> Tuple[str, str]:
    """One rapid bulletin: release date, threat level, and a 1-click newsfeed button."""
    color = "#ff7878" if f["score"] >= 90 else "#ffaa00"
    cves = ", ".join(f["cves"]) or "No CVE assigned"
    block = f"""
    <div style="border-left: 3px solid {color}; padding: 8px 0 8px 12px; margin-bottom: 12px;">
        <div style="font-family: monospace; font-size: 11px; color: #888899; margin-bottom: 4px;">
            <strong style="color: {color};">{html_lib.escape(f['level'])} · {f['score']}/100</strong> · Released {html_lib.escape(f['date'])} · {html_lib.escape(cves)}
        </div>
        <div style="font-size: 15px; font-weight: 600; line-height: 1.4; margin-bottom: 8px;">
            <a href="{url}" style="color: #ffffff; text-decoration: none;">{html_lib.escape(f['title'])}</a>
        </div>
        {_cta(url, _STYLE_META['headlines'][3], '#19e6ff')}
    </div>"""
    text = f"- [{f['level']}] {f['title']}\n  Released: {f['date']} | {cves}\n  Open on Newsfeed: {url}\n"
    return block, text


def _featured_teaser(style: str, f: Dict[str, Any], url: str) -> Tuple[str, str]:
    """Renders the featured story as a short teaser in the subscriber's appetite style."""
    if style == "headlines":
        return _headline_bulletin(f, url)

    lead = _first_sentences(f["summary"], 1)
    cve = f["cves"][0] if f["cves"] else "No CVE assigned yet"

    if style == "briefs":
        brief = _first_sentences(f["summary"], 2) or "A new advisory has been published for this threat."
        if f["remediation"]:
            brief += f" Recommended action: {_first_sentences(f['remediation'], 1)}"
        paragraphs = [brief]
    elif style == "deep_dive":
        paragraphs = [
            "The patch closes the door. The real question is why the door was there at all.",
            f"Key identifier: {cve}",
            lead or "A new exploitable weakness has been confirmed.",
            "The full deep dive traces the root cause, the exploit primitive, and a prioritized blue-team runbook.",
        ]
    elif style == "reconstruction":
        paragraphs = [
            "Simulated lab timeline (educational reconstruction, not a real incident log):",
            f"02:14 — The initial alert fired: {lead or f['title']}",
            f"02:31 — The team pinned the entry point to {cve}.",
            "02:47 — Then a second process spawned that nobody on the team recognized…",
        ]
    else:  # cyber_thriller
        paragraphs = [
            f"The SOC floor was quiet at 03:07 — until a single line from {f['source']} scrolled across the night-shift console: “{f['title']}.”",
            "The analyst read it twice, then pulled the logs. The timestamps didn't add up. Someone had been inside for hours.",
            "Reaching for the phone to wake the incident commander, the analyst froze. On the screen, a new session had just opened — one nobody on the team had started —",
        ]

    _, _, color, cta_label = _STYLE_META[style]
    block = f"""
    <div style="font-family: monospace; font-size: 11px; color: #888899; margin-bottom: 6px;">
        <strong style="color: {color};">{html_lib.escape(f['level'])}</strong> · Released {html_lib.escape(f['date'])}
    </div>
    <h2 style="color: #ffffff; font-size: 19px; margin: 0 0 12px 0; line-height: 1.3;">{html_lib.escape(f['title'])}</h2>
    {''.join(_paragraph(html_lib.escape(p)) for p in paragraphs)}
    <div style="margin-top: 14px;">{_cta(url, cta_label, color)}</div>"""
    text = (
        f"{f['title']}\nReleased: {f['date']} | {f['level']}\n\n"
        + "\n".join(paragraphs)
        + f"\n\n{cta_label.rstrip(' →')}: {url}\n"
    )
    return block, text


def build_devcore_engineering_news_section(base_url: str = "", token: str = "") -> Tuple[str, str]:
    """Generates the DevCore & E-Profile Engineering News section for all email templates."""
    clean_base = (base_url or "").rstrip("/")
    if token:
        try:
            from notify_mod import encode_tracking_token
            dev_url = f"{clean_base}/newsletter/r/{encode_tracking_token('dev_releases', '/projects', sub_token=token)}"
            docs_url = f"{clean_base}/newsletter/r/{encode_tracking_token('devcore_docs', '/docs', sub_token=token)}"
        except Exception:
            dev_url = f"{clean_base}/projects"
            docs_url = f"{clean_base}/docs"
    else:
        dev_url = f"{clean_base}/projects"
        docs_url = f"{clean_base}/docs"

    html = _section(
        "#00ff88",
        "🛡️ DEVCORE · E-Profile Development & Engineering News",
        "<h3 style=\"color: #ffffff; font-size: 15px; margin: 0 0 8px 0;\">What's Happening in E-Profile Development & New Releases</h3>"
        + _paragraph("DevCore Autonomous AI Agent and Siraugga zero-trust framework engineering developments: Zero-downtime hot-patching, accessible WebSocket streaming, POPIA-compliant offline PII scrubbing, and Super Admin JIT elevation.")
        + """<div style="margin: 10px 0; font-size: 12px; font-family: monospace; color: #a0aec0;">
            <div style="margin-bottom: 4px;">⚡ <strong style="color: #19e6ff;">DevCore v2.4:</strong> Zero-downtime hot-patch sequence and AST memory syncing.</div>
            <div style="margin-bottom: 4px;">🔐 <strong style="color: #00ff88;">Siraugga Security:</strong> KMS keychain, mantrap defense, and encrypted session rollover.</div>
            <div>🎧 <strong style="color: #b388ff;">Accessible Audio Suite:</strong> High-contrast NVDA coordinate audio engine and TTS feeds.</div>
        </div>"""
        + '<div style="margin-top: 12px;">'
        + _cta(dev_url, "🛠️ Explore DevCore Releases →", "#00ff88")
        + " &nbsp; "
        + _cta(docs_url, "📚 Architecture Docs & Devlogs →", "#19e6ff")
        + '</div>',
    )
    text = (
        f"E-PROFILE DEVELOPMENT & RELEASES:\n"
        f"DEVCORE PLATFORM & ENGINEERING INTEL:\n"
        f"What's Happening in E-Profile Development & New Releases\n"
        f"- DevCore v2.4: Zero-downtime hot-patch sequence and AST memory syncing\n"
        f"- Siraugga Security: KMS keychain, mantrap defense, and encrypted session rollover\n"
        f"- Accessible Audio Suite: High-contrast NVDA coordinate audio engine\n"
        f"DevCore Releases: {dev_url}\nArchitecture Docs: {docs_url}\n"
    )
    return html, text


def build_personalized_newsletter_email(
    subscriber: Dict[str, Any],
    manifest: Dict[str, Any],
    base_url: str = ""
) -> Tuple[str, str, str, Dict[str, str]]:
    """
    Constructs a personalized Cyber Intelligence newsletter. Every appetite style is a
    short teaser that links to the full story on the site:
      1. 'headlines'      : 3-5 rapid bulletins (release date, threat level, 1-click newsfeed)
      2. 'briefs'         : 2-3 sentence executive brief + Read More on Site
      3. 'deep_dive'      : Root-cause provocation + key CVE + 2-line teaser
      4. 'reconstruction' : Cliffhanger simulated timeline + lab simulation link
      5. 'cyber_thriller' : Cold open cut off mid-scene + Continue Story on Site

    The delivery format picks the layout ('quick_threat_wire' = bulletins only,
    'hybrid_brief'/'weekly_digest' = featured dossier + headlines brief).

    Returns:
      (subject: str, html_content: str, text_content: str, headers: Dict[str, str])
    """
    from notify_mod import encode_tracking_token

    clean_base = (base_url or "").rstrip("/")
    token = subscriber.get("token") or "token"
    delivery = subscriber.get("delivery") or {}
    content_pref = subscriber.get("content") or {}
    modules = subscriber.get("engagement_modules") or {}

    layout = delivery.get("format") or "hybrid_brief"
    style = _APPETITE_STYLE_MAP.get(content_pref.get("primary_appetite") or layout, "briefs")
    emoji, style_label, style_color, _ = _STYLE_META[style]
    layout_label = _LAYOUT_LABELS.get(layout, "Featured Dossier")

    items = manifest.get("items") or []
    featured = _story_fields(items[0] if items else {})

    pref_url = f"{clean_base}/newsletter/preferences?token={token}"
    unsub_purge_url = f"{clean_base}/newsletter/unsubscribe?token={token}&purge=1"
    visit_site_url = f"{clean_base}/newsletter"
    terms_url = f"{clean_base}/terms-and-conditions"

    def track_url(slot: str, path: str) -> str:
        return f"{clean_base}/newsletter/r/{encode_tracking_token(slot, path, sub_token=token)}"

    def story_url(slot: str, f: Dict[str, Any], appetite: str) -> str:
        return track_url(slot, f"/newsletter/story/{f['id']}?appetite={appetite}")

    blocks: List[str] = []
    text_parts: List[str] = []

    # Masthead
    blocks.append(f"""
    <div style="border-bottom: 1px solid rgba(25, 230, 255, 0.25); padding-bottom: 16px; margin-bottom: 20px;">
        <div style="font-size: 11px; font-family: monospace; letter-spacing: 2px; color: #19e6ff; text-transform: uppercase;">
            Cyber Threat Intelligence Dispatch
        </div>
        <div style="font-size: 12px; color: #888899; font-family: monospace; margin-top: 4px;">
            {layout_label} · <strong style="color: {style_color};">{emoji} {style_label}</strong> · Latest release: <strong style="color: #ffffff;">{html_lib.escape(featured['date'])}</strong>
        </div>
        <div style="margin-top: 10px;">
            <a href="{pref_url}" style="font-size: 11px; font-family: monospace; color: #19e6ff; text-decoration: none; border: 1px solid #19e6ff; padding: 4px 8px; border-radius: 4px; display: inline-block;">⚙️ Switch Style</a>
        </div>
    </div>""")
    text_parts.append(f"CYBER THREAT INTELLIGENCE DISPATCH\n{layout_label} · {emoji} {style_label}\nLatest release: {featured['date']}\n")

    if layout == "quick_threat_wire":
        bulletins = [_story_fields(it) for it in items[:5]]
        subject = f"[Threat Wire] {len(bulletins)} Rapid Vulnerability Bulletins"
        rows = [_headline_bulletin(f, story_url("headline", f, "headlines")) for f in bulletins]
        blocks.append(_section("#19e6ff", "⚡ Rapid Threat Wire (1-Min Bulletins)", "".join(h for h, _ in rows)))
        text_parts.append("RAPID THREAT WIRE:\n" + "\n".join(t for _, t in rows))
    else:
        featured_html, featured_text = _featured_teaser(style, featured, story_url(style, featured, style))
        blocks.append(_section(style_color, f"Featured Dossier · {emoji} {style_label}", featured_html))
        text_parts.append(f"FEATURED DOSSIER · {style_label.upper()}\n{featured_text}")

        headline_items = []
        if layout in ("hybrid_brief", "weekly_digest"):
            headline_items = [_story_fields(it) for it in items[1:5]]
        if headline_items:
            rows = [_headline_bulletin(f, story_url("headline", f, "headlines")) for f in headline_items]
            blocks.append(_section("#19e6ff", "⚡ Advisory Headlines Brief", "".join(h for h, _ in rows)))
            text_parts.append("ADVISORY HEADLINES BRIEF:\n" + "\n".join(t for _, t in rows))

        if layout == "hybrid_brief":
            subject = f"[Cyber Intel Brief] {featured['title']}"
            if headline_items:
                subject += f" + {len(headline_items)} Advisories"
        else:
            subject = f"[{style_label}] {featured['title']}"

    # Engagement module 1: alternate appetite teaser
    if items and modules.get("alt_appetite_teaser", True):
        alt_style = _ALT_STYLE[style]
        alt_emoji, alt_label, alt_color, _ = _STYLE_META[alt_style]
        alt_url = story_url("alt_teaser", featured, alt_style)
        hook = _ALT_HOOKS[alt_style]
        blocks.append(_section(
            alt_color,
            f"🔀 Alternate Perspective Preview · {alt_emoji} {alt_label}",
            _paragraph(f'<strong style="color: {alt_color};">Curiosity Hook:</strong> {html_lib.escape(hook)}')
            + _cta(alt_url, f"{alt_emoji} Read as {alt_label} →", alt_color),
        ))
        text_parts.append(f"ALTERNATE PERSPECTIVE PREVIEW ({alt_label}):\nCuriosity Hook: {hook}\n{alt_url}\n")

    # Engagement module 2: audio edition CTA
    if modules.get("audio_link", True):
        audio_url = track_url("audio_cta", "/downloads")
        blocks.append(_section(
            "#b388ff",
            "🎧 Accessible Audio Suite",
            _paragraph("Prefer to listen? Visit the Accessible Audio Suite on the site.")
            + _cta(audio_url, "🎧 Stream Audio on Site →", "#b388ff"),
        ))
        text_parts.append(f"ACCESSIBLE AUDIO SUITE:\nStream Audio on Site: {audio_url}\n")

    # Engagement module 3: zero-day / KEV radar
    radar = [f for f in (_story_fields(it) for it in items[:8]) if f["cves"]][:5]
    if radar and modules.get("zero_day_radar", True):
        radar_rows, radar_text = [], []
        for f in radar:
            url = story_url("zero_day_radar", f, style)
            cves = ", ".join(f["cves"])
            radar_rows.append(
                f'<li style="margin-bottom: 6px;"><a href="{url}" style="color: #19e6ff; font-family: monospace;">{html_lib.escape(cves)}</a>'
                f' <span style="color: #888899;">· {html_lib.escape(f["level"])} · {html_lib.escape(f["title"])}</span></li>'
            )
            radar_text.append(f"- {cves} [{f['level']}] {f['title']}: {url}")
        blocks.append(_section(
            "#ff7878",
            "🛰️ Bonus Zero-Day & KEV Radar",
            f'<ul style="margin: 0; padding-left: 18px; font-size: 13px;">{"".join(radar_rows)}</ul>',
        ))
        text_parts.append("BONUS ZERO-DAY & KEV RADAR:\n" + "\n".join(radar_text) + "\n")

    # DevCore & E-Profile Engineering News
    devcore_html, devcore_text = build_devcore_engineering_news_section(clean_base, token=token)
    blocks.append(devcore_html)
    text_parts.append(devcore_text)

    # Author credibility
    blocks.append(f"""
    <div style="text-align: center; margin: 24px 0; font-size: 12px; color: #a0aec0;">
        Curated by <strong style="color: #ffffff;">Michael Robberts</strong> ·
        <a href="{LINKEDIN_URL}" style="color: #19e6ff;">LinkedIn</a> ·
        <a href="{CREDLY_URL}" style="color: #19e6ff;">Credly Certifications</a>
        <div data-iframe-width="150" data-iframe-height="270" data-share-badge-id="{CREDLY_BADGE_ID}" data-share-badge-host="https://www.credly.com" style="margin-top: 8px;">
            <a href="https://www.credly.com/badges/{CREDLY_BADGE_ID}" style="color: #888899; font-size: 11px;">View verified Credly badge →</a>
        </div>
    </div>""")
    text_parts.append(f"Curated by Michael Robberts\nLinkedIn: {LINKEDIN_URL}\nCredly: {CREDLY_URL}\n")

    # Footer: activity requirement, inbox relief, RFC 8058 links (zero download links in email)
    blocks.append(f"""
    <div style="margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 20px;">
        <div style="background: rgba(25, 230, 255, 0.04); border: 1px solid rgba(25, 230, 255, 0.15); border-radius: 6px; padding: 12px 14px; margin-bottom: 18px; font-size: 11px; color: #a0aec0; line-height: 1.5;">
            <strong style="color: #19e6ff;">Subscription Activity Requirement:</strong> We require subscribers to visit the site from time to time to keep their subscription active. If you do not visit the website from the emails you receive, your subscription record will be automatically purged.
            <div style="margin-top: 6px;">
                <a href="{visit_site_url}" style="color: #19e6ff; text-decoration: underline; font-weight: bold;">Visit Website to Keep Active →</a>
            </div>
        </div>
        <p style="margin: 0 0 12px 0; font-size: 12px; color: #cbd5e1; text-align: center;">{INBOX_RELIEF_NOTICE}</p>
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
    </div>""")
    text_parts.append(
        "\n" + "=" * 60 +
        "\nSUBSCRIPTION ACTIVITY REQUIREMENT:\n"
        "We require subscribers to visit the site from time to time to keep their subscription active.\n"
        f"Visit Website to Confirm Active Status: {visit_site_url}\n"
        f"\n{INBOX_RELIEF_NOTICE}\n"
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
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e0e0e0;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0a0a0b; padding: 25px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 640px; background-color: #10141d; border: 1px solid rgba(25, 230, 255, 0.25); border-radius: 8px; padding: 24px; text-align: left;">
                    <tr>
                        <td>
                            {''.join(blocks)}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    headers = {
        "List-Unsubscribe": f"<{clean_base}/newsletter/unsubscribe?token={token}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
    }
    return subject, master_html, "\n".join(text_parts), headers


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

    # Fetch recent threat topics for the welcome email brief
    recent_topics_html = []
    recent_topics_text = []
    try:
        from newsletter_mod import load_active_manifest
        manifest = load_active_manifest()
        manifest_items = manifest.get("items", [])[:3]
        for it in manifest_items:
            it_title = html_lib.escape(it.get("title", "Threat Advisory"))
            it_id = it.get("story_id", "")
            it_lvl = html_lib.escape(str(it.get("threat_level", "HIGH")))
            it_score = it.get("score", 75)
            it_cves = ", ".join(it.get("cves", [])) or "Active Exploit Vector"
            raw_summary = it.get("summary", "")
            it_summary = html_lib.escape(raw_summary[:220])
            if len(raw_summary) > 220:
                it_summary += "..."
            it_url = f"{clean_base}/newsletter/story/{it_id}"

            badge_color = "#ff7878" if it_score >= 90 else "#ffaa00"
            recent_topics_html.append(f"""
            <div style="background: rgba(255, 255, 255, 0.03); border-left: 3px solid {badge_color}; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 12px 14px; margin-bottom: 12px;">
                <div style="font-family: monospace; font-size: 11px; margin-bottom: 4px;">
                    <span style="color: {badge_color}; font-weight: bold;">[{it_lvl}]</span>
                    <span style="color: #888899; margin-left: 6px;">{it_cves}</span>
                </div>
                <div style="font-size: 14px; font-weight: 600; margin-bottom: 4px;">
                    <a href="{it_url}" style="color: #19e6ff; text-decoration: none;">{it_title} →</a>
                </div>
                <div style="font-size: 12px; color: #a0aec0; line-height: 1.4; margin-bottom: 8px;">
                    {it_summary}
                </div>
                <div style="text-align: right;">
                    <a href="{it_url}" style="font-size: 11px; font-family: monospace; color: #00ff88; text-decoration: none;">
                        🛡️ Read Dossier & Interactive Playbook →
                    </a>
                </div>
            </div>""")
            recent_topics_text.append(f"- [{it_lvl}] {it.get('title')}\n  CVEs: {it_cves}\n  Summary: {raw_summary[:200]}\n  Dossier Link: {it_url}")
    except Exception:
        pass

    topics_markup = "".join(recent_topics_html) if recent_topics_html else '<p style="color: #888899; font-size: 13px;">Curating latest vulnerability telemetry...</p>'
    devcore_html, devcore_text = build_devcore_engineering_news_section(clean_base, token=token)

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
                            <span style="font-size: 18px; font-weight: bold; color: #00f3ff; letter-spacing: 1px;">MICHAEL ROBBERTS</span>
                            <span style="float: right; font-size: 12px; color: #888899; font-family: monospace;">Zero-Trust Intel</span>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding-top: 24px;">
                            <div style="font-size: 11px; font-family: monospace; letter-spacing: 2px; color: #19e6ff; text-transform: uppercase; margin-bottom: 6px;">
                                Subscription Notification
                            </div>
                            <h1 style="color: #ffffff; font-size: 22px; margin: 0 0 16px 0; font-weight: 700;">
                                Did you subscribe to Cyber Threat Intelligence?
                            </h1>
                            <p style="font-size: 14px; line-height: 1.6; color: #c8d2e0; margin: 0 0 16px 0;">
                                Hello, we received a subscription request for <strong style="color: #ffffff;">{html_lib.escape(email)}</strong> to receive curated, multi-cadence cyber intelligence feeds and zero-day threat dispatches from the Michael Robberts E-Profile platform.
                            </p>

                            <!-- Subscription Details Card -->
                            <div style="background: rgba(25, 230, 255, 0.05); border: 1px solid rgba(25, 230, 255, 0.2); border-radius: 6px; padding: 14px 16px; margin-bottom: 20px;">
                                <div style="font-size: 11px; font-family: monospace; color: #19e6ff; text-transform: uppercase; font-weight: bold; margin-bottom: 6px;">
                                    Selected Preferences:
                                </div>
                                <div style="font-size: 13px; color: #e2e8f0; font-family: monospace;">
                                    Delivery Format: <strong style="color: #ffffff;">{html_lib.escape(format_label)}</strong><br>
                                    Primary Reading Appetite: <strong style="color: #19e6ff;">{html_lib.escape(appetite_label)}</strong>
                                </div>
                            </div>

                            <!-- Recent Active Threat Telemetry Topics Brief -->
                            <div style="margin-bottom: 22px;">
                                <div style="font-size: 11px; font-family: monospace; font-weight: bold; color: #19e6ff; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">
                                    ⚡ RECENT THREAT TELEMETRY (ACTIVE AT TIME OF SUBSCRIPTION)
                                </div>
                                {topics_markup}
                            </div>

                            <!-- DevCore Platform & Engineering News Brief -->
                            <div style="margin-bottom: 22px;">
                                {devcore_html}
                            </div>

                            <!-- Manage Preferences Button -->
                            <div style="margin: 20px 0; text-align: center;">
                                <a href="{pref_url}" style="background-color: #00f3ff; color: #000000; font-family: monospace; font-size: 13px; font-weight: bold; padding: 10px 22px; border-radius: 4px; text-decoration: none; display: inline-block;">
                                    ⚙️ Manage Your Preferences
                                </a>
                            </div>

                            <!-- Accidental Subscription Notice & Pretty Unsubscribe Button -->
                            <div style="margin: 24px 0; padding: 20px 16px; background-color: #1a0f12; border: 1px solid #772228; border-radius: 8px; text-align: center;">
                                <p style="margin: 0 0 14px 0; font-size: 13px; color: #ffffff; font-weight: 600; line-height: 1.4;">
                                    If you have not subscribed to this newsletter, please just hit that pretty button below to relieve your inbox.
                                </p>
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 0 auto;">
                                    <tr>
                                        <td align="center" bgcolor="#d32f2f" style="border-radius: 6px; background-color: #d32f2f; background: linear-gradient(135deg, #e53935 0%, #b71c1c 100%); border: 1px solid #ff4d4d; box-shadow: 0 4px 14px rgba(255, 77, 77, 0.4);">
                                            <a href="{unsub_url}" target="_blank" role="button" aria-label="1-Click Unsubscribe & Purge Data" style="display: inline-block; padding: 12px 28px; font-family: monospace, sans-serif; font-size: 13px; font-weight: bold; color: #ffffff; text-decoration: none; letter-spacing: 0.5px; border-radius: 6px;">
                                                🚫 1-Click Unsubscribe & Purge Data
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                <div style="margin-top: 12px; font-size: 10px; color: #ff9999; font-family: monospace;">
                                    Immediately and completely purges your email address and records from our local registry.
                                </div>
                            </div>

                            <!-- Subscription Activity Requirement Card -->
                            <div style="margin: 24px 0 16px 0; padding: 14px 16px; background: rgba(255, 170, 0, 0.07); border: 1px solid rgba(255, 170, 0, 0.28); border-radius: 6px;">
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

    plain_text_topics = ("\n".join(recent_topics_text)) if recent_topics_text else "Curating latest vulnerability telemetry..."
    plain_text = f"""============================================================
CYBER THREAT INTELLIGENCE · SUBSCRIPTION CONFIRMATION
============================================================

Hello,

We received a subscription request for {email} to receive Cyber Threat Intelligence feeds and advisories from Michael Robberts E-Profile.

------------------------------------------------------------
RECENT THREAT TELEMETRY (ACTIVE AT TIME OF SUBSCRIPTION):
------------------------------------------------------------
{plain_text_topics}

------------------------------------------------------------
DEVCORE PLATFORM & ENGINEERING INTEL:
------------------------------------------------------------
{devcore_text}

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


def build_ready_appetite_email(
    to_address: str,
    story_id: str,
    appetite: str,
    story_data: Dict[str, Any],
    token: str = "",
    base_url: str = ""
) -> Tuple[str, str, str, Dict[str, str]]:
    """Builds an email delivering a previously queued/pending synthesized appetite once ready."""
    clean_base = (base_url or "").rstrip("/")
    if not clean_base:
        clean_base = getattr(config, "BASE_URL", "https://mikeymike.pythonanywhere.com").rstrip("/")

    import markdown
    from story_agent_dispatcher import APPETITE_CONFIG
    app_cfg = APPETITE_CONFIG.get(appetite, {})
    app_title = app_cfg.get("title", appetite.replace("_", " ").title())
    app_color = app_cfg.get("badge_color", "#19e6ff")

    title = story_data.get("story_id", story_id).replace("-", " ").title()
    if isinstance(story_data.get("item_metadata"), dict):
        title = story_data["item_metadata"].get("title", title)
    elif story_data.get("title"):
        title = story_data["title"]

    md_content = story_data.get("markdown", "")
    rendered_html = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

    story_url = f"{clean_base}/newsletter/story/{story_id}?appetite={appetite}"
    pref_url = f"{clean_base}/newsletter/preferences?token={token}" if token else f"{clean_base}/newsletter/preferences"
    unsub_url = f"{clean_base}/newsletter/unsubscribe?token={token}&purge=1" if token else f"{clean_base}/newsletter/unsubscribe"

    subject = f"[Ready] {title} · {app_title}"
    devcore_html, devcore_text = build_devcore_engineering_news_section(clean_base, token=token)

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
                    <tr>
                        <td style="border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 16px;">
                            <span style="font-size: 18px; font-weight: bold; color: #00f3ff; letter-spacing: 1px;">MICHAEL ROBBERTS</span>
                            <span style="float: right; font-size: 12px; color: {app_color}; font-family: monospace;">⚡ SYNTHESIS COMPLETE</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top: 20px;">
                            <div style="font-size: 11px; font-family: monospace; letter-spacing: 2px; color: {app_color}; text-transform: uppercase; margin-bottom: 6px;">
                                {html_lib.escape(app_title)}
                            </div>
                            <h1 style="color: #ffffff; font-size: 20px; margin: 0 0 14px 0; font-weight: 700;">
                                {html_lib.escape(title)}
                            </h1>
                            <p style="font-size: 13px; color: #a0aec0; line-height: 1.5; margin: 0 0 18px 0;">
                                You visited this advisory while our threat intelligence engine was actively synthesizing it. Your requested analysis is now ready:
                            </p>
                            <div style="background: #141824; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 18px; margin-bottom: 20px; color: #d0d8e8; line-height: 1.6; font-size: 13px;">
                                {rendered_html}
                            </div>
                            <div style="text-align: center; margin: 20px 0;">
                                <a href="{story_url}" style="background-color: {app_color}; color: #000000; font-family: monospace; font-size: 13px; font-weight: bold; padding: 10px 22px; border-radius: 4px; text-decoration: none; display: inline-block;">
                                    🛡️ Open Interactive Dossier on Web Portal →
                                </a>
                            </div>
                            <div style="margin-top: 24px; margin-bottom: 20px;">
                                {devcore_html}
                            </div>
                            <div style="border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 16px; font-size: 11px; color: #64748b; text-align: center;">
                                <a href="{pref_url}" style="color: #19e6ff;">Preferences</a> · 
                                <a href="{unsub_url}" style="color: #ff7878;">Unsubscribe & Purge</a>
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    plain_text = f"""{subject}
============================================================
{title}
Appetite: {app_title}
============================================================

You visited this advisory while our threat intelligence engine was actively synthesizing it.
Your requested analysis is now ready:

{md_content}

------------------------------------------------------------
Open Interactive Dossier on Web Portal:
{story_url}

------------------------------------------------------------
DEVCORE PLATFORM & ENGINEERING INTEL:
------------------------------------------------------------
{devcore_text}

Manage Preferences: {pref_url}
Unsubscribe & Purge: {unsub_url}
"""

    headers = {
        "List-Unsubscribe": f"<{unsub_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
    }

    return subject, html_content, plain_text, headers


def send_ready_appetite_email(
    to_address: str,
    story_id: str,
    appetite: str,
    story_data: Dict[str, Any],
    token: str = "",
    base_url: str = ""
) -> Tuple[bool, str, Dict[str, Any]]:
    """Delivers a completed appetite analysis to a user whose request was backlogged."""
    subject, html_content, text_content, headers = build_ready_appetite_email(
        to_address=to_address,
        story_id=story_id,
        appetite=appetite,
        story_data=story_data,
        token=token,
        base_url=base_url
    )
    return send_email(
        to_address=to_address,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        sender=config.NEWSLETTER_SENDER,
        headers=headers
    )


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
        sender=config.NEWSLETTER_SENDER,
        headers=headers
    )


# ---------------------------------------------------------------------------
# CLI Diagnostics & Direct Testing Tools
# ---------------------------------------------------------------------------

def _print_mail_config() -> None:
    username, password = _smtp_credentials()
    print("======================================================")
    print("  E-Profile Email Engine Configuration")
    print("======================================================")
    print(f"  MAIL_BACKEND        : {config.MAIL_BACKEND}")
    print(f"  MAIL_SERVER         : {config.MAIL_SERVER}")
    print(f"  MAIL_PORT           : {config.MAIL_PORT}")
    print(f"  MAIL_USE_TLS        : {config.MAIL_USE_TLS}")
    print(f"  MAIL_USERNAME       : {username or '(missing)'}")
    print(f"  MAIL_PASSWORD       : {'(configured)' if password else '(missing)'}")
    print(f"  MAIL_DEFAULT_SENDER : {config.MAIL_DEFAULT_SENDER}")
    print("======================================================")


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="E-Profile email engine diagnostics.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Print mail configuration and test the SMTP connection.")
    group.add_argument("--send-test", metavar="EMAIL", help="Send a test email to EMAIL and report the honest delivery status.")
    args = parser.parse_args(argv)

    _print_mail_config()
    print()

    if args.check:
        ok, message = test_smtp_connection()
        print(f"[{'OK' if ok else 'FAIL'}] {message}")
        return 0 if ok else 1

    subject = "E-Profile Email Engine Test"
    html_content = build_email_template(
        title=subject,
        body_html=f"<p>Test email generated at {datetime.now():%Y-%m-%d %H:%M:%S} via the '{config.MAIL_BACKEND}' backend.</p>",
    )
    ok, message, record = send_email(args.send_test, subject, html_content)
    print(f"Status : {record['status']}")
    print(f"Result : {message}")
    if record.get("details"):
        print(f"Details: {record['details']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
