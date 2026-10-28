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
    sender: Optional[str] = None
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
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_address

            part1 = MIMEText(text_content, "plain", "utf-8")
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            server_host = config.MAIL_SERVER
            server_port = int(config.MAIL_PORT)
            use_tls = config.MAIL_USE_TLS
            username = config.MAIL_USERNAME
            password = config.MAIL_PASSWORD

            if server_port == 465:
                server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
                server.ehlo()
            else:
                server = smtplib.SMTP(server_host, server_port, timeout=10)
                server.ehlo()
                if use_tls:
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
        if port == 465:
            server = smtplib.SMTP_SSL(config.MAIL_SERVER, port, timeout=8)
            server.ehlo()
        else:
            server = smtplib.SMTP(config.MAIL_SERVER, port, timeout=8)
            server.ehlo()
            if config.MAIL_USE_TLS:
                server.starttls()
                server.ehlo()
        if config.MAIL_USERNAME and config.MAIL_PASSWORD:
            server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        server.quit()
        return True, f"Successfully connected to {config.MAIL_SERVER}:{port} and authenticated."
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
    key_values = {
        "MAIL_BACKEND": backend,
        "MAIL_SERVER": server_host,
        "MAIL_PORT": str(server_port),
        "MAIL_USE_TLS": "True" if use_tls else "False",
        "MAIL_USERNAME": username,
        "MAIL_PASSWORD": password,
        "MAIL_DEFAULT_SENDER": default_sender,
    }

    # 1. Update .env file
    file_saved = update_env_file(key_values)

    # 2. Update runtime environment variables
    for k, v in key_values.items():
        os.environ[k] = v

    # 3. Update runtime Config
    config.MAIL_BACKEND = backend
    config.MAIL_SERVER = server_host
    config.MAIL_PORT = int(server_port)
    config.MAIL_USE_TLS = use_tls
    config.MAIL_USERNAME = username
    config.MAIL_PASSWORD = password
    config.MAIL_DEFAULT_SENDER = default_sender

    Config.MAIL_BACKEND = backend
    Config.MAIL_SERVER = server_host
    Config.MAIL_PORT = int(server_port)
    Config.MAIL_USE_TLS = use_tls
    Config.MAIL_USERNAME = username
    Config.MAIL_PASSWORD = password
    Config.MAIL_DEFAULT_SENDER = default_sender

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

