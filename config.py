import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    # 1. Base Paths
    ROOT_DIR = Path(__file__).resolve().parent
    CONTENT_DIR = ROOT_DIR / "content"
    STATIC_DIR = ROOT_DIR / "static"
    TEMPLATES_DIR = ROOT_DIR / "templates"
    
    # 2. Centralized Documentation Sources (Zero-Touch Discovery)
    CENTRAL_DOCS_DIR = Path(os.environ.get("CENTRAL_DOCS_DIR", "/mnt/c/Users/michael/Documents/Central_Docs"))
    
    # 2. Handshake Security Keys (Loaded from ENV for security)
    ADMIN_KEY = os.environ.get("ADMIN_KEY", "SECURE_ADMIN_KEY_HERE")
    USER_KEY = os.environ.get("USER_KEY", "USER")
    EMPLOYER_KEY = os.environ.get("EMPLOYER_KEY", "SECURE_EMPLOYER_KEY_HERE")

    # --- Email Service Configuration ---
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "local")  # 'local', 'smtp'
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "notifications@eprofile.local")
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
    TABS = ["home", "hub", "docs", "bio", "blog", "projects", "certifications", "downloads", "usage"]
    @classmethod
    def get_all_required_paths(cls):
        return [
            "static/css",
            "static/js",
            "static/img",
            "templates",
            "content"
        ]