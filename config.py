import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if present
load_dotenv(ROOT_DIR / ".env")

class Config:
    # 1. Base Paths
    ROOT_DIR = ROOT_DIR
    CONTENT_DIR = ROOT_DIR / "content"
    STATIC_DIR = ROOT_DIR / "static"
    TEMPLATES_DIR = ROOT_DIR / "templates"
    
    # 2. Centralized Documentation Sources (Zero-Touch Discovery)
    CENTRAL_DOCS_DIR = Path(os.environ.get("CENTRAL_DOCS_DIR", "/mnt/c/Users/michael/Documents/Central_Docs"))
    
    # 2. Handshake Security Keys (Loaded from ENV for security)
    ADMIN_KEY = os.environ.get("ADMIN_KEY", "SECURE_ADMIN_KEY_HERE")
    USER_KEY = os.environ.get("USER_KEY", "USER")
    EMPLOYER_KEY = os.environ.get("EMPLOYER_KEY", "SECURE_EMPLOYER_KEY_HERE")

    # --- AI Brain Credentials (Claude) ---
    # Single named surface for the host; env is the one source of truth.
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    ANTHROPIC_AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN")

    # --- Threat Intelligence Feeds ---
    OTX_API_KEY = os.environ.get("OTX_API_KEY", "")
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
    THREAT_FEED_REFRESH_HOURS = int(os.environ.get("THREAT_FEED_REFRESH_HOURS", 6))

    # --- Public address used in every email link (newsletter "read more", welcome, unsubscribe) ---
    # Never the address of the page that pressed "send": sending from this computer used to put
    # http://127.0.0.1:5001 links into subscribers' emails.
    BASE_URL = (os.environ.get("PUBLIC_BASE_URL") or "https://mikeymike.pythonanywhere.com").rstrip("/")

    # --- Email Service Configuration ---
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "smtp")  # 'smtp' (live), 'local' (mock)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "notifications@eprofile.local")
    # Newsletter goes out as CyberBrief. It is a verified Gmail "Send mail as" alias of
    # MAIL_USERNAME; mail sent TO it is dropped by Cloudflare Email Routing (no replies).
    NEWSLETTER_SENDER = os.environ.get("NEWSLETTER_SENDER", "CyberBrief <cyberbrief@mikeytech.dev>")
    MAILBOX_FILE = ROOT_DIR / "cache" / "mailbox.json"

    # --- UI & Theme Configuration ---
    THEME = {
        "bg_color": "#0a0a0b",
        "accent_color": "#00f3ff",
        "contrast_color": "#ff0055",
        "text_primary": "#e0e0e0",
        "glass_effect": "rgba(20, 20, 25, 0.8)"
    }

    # --- Dynamic Navigation Tabs ---
    TABS = ["home", "newsletter", "docs", "bio", "blog", "projects", "certifications", "downloads", "usage"]
    @classmethod
    def get_all_required_paths(cls):
        return [
            "static/css",
            "static/js",
            "static/img",
            "templates",
            "content"
        ]