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
    
    # 2. Handshake Security Keys (Loaded from ENV for security)
    ADMIN_KEY = os.environ.get("ADMIN_KEY", "SECURE_ADMIN_KEY_HERE")
    USER_KEY = os.environ.get("USER_KEY", "USER")
    EMPLOYER_KEY = os.environ.get("EMPLOYER_KEY", "SECURE_EMPLOYER_KEY_HERE")

    # --- UI & Theme Configuration ---
    THEME = {
        "bg_color": "#0a0a0b",
        "accent_color": "#00f3ff",
        "contrast_color": "#ff0055",
        "text_primary": "#e0e0e0",
        "glass_effect": "rgba(20, 20, 25, 0.8)"
    }

    # --- Dynamic Navigation Tabs ---
    TABS = ["home", "bio", "blog", "projects", "certifications"]

    @classmethod
    def get_all_required_paths(cls):
        return [
            "static/css",
            "static/js",
            "static/img",
            "templates",
            "content"
        ]