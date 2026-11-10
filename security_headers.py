"""Security headers and login guessing limit for e_profile, matching DevCore's (the root).

DevCore keeps the agent and its security (resolver, hooks, vault isolation, JIT). e_profile is
only a front end, so it gets DevCore's web-side protections:
  * the same security headers on every response (security/security_headers.py in DevCore);
  * a limit on wrong login tokens, like DevCore's limit on wrong owner passwords.
"""
import threading
import time

from flask import request

SIRAUGGA_URL = "https://mikeytech.dev"   # the agent's back end (the console calls it directly)

# Pages here load nothing from other sites; the console talks to Siraugga's domain.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data:; "
    "media-src 'self' data: blob:; "
    f"connect-src 'self' {SIRAUGGA_URL}; "
    "frame-src 'self'; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# Wrong login tokens: at most this many per window, counted across ALL visitors (an attacker can
# change IP, so a per-IP limit wouldn't hold). Kept in memory; resets when the app restarts.
LOGIN_FAIL_LIMIT = 10
LOGIN_FAIL_WINDOW = 15 * 60
_lock = threading.Lock()
_login_failures = []


def _is_https() -> bool:
    try:
        if request.is_secure:
            return True
        return (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower() == "https"
    except Exception:
        return False


def apply_security_headers(response):
    """Same protections as DevCore. Headers a route set on purpose (e.g. a stricter
    Referrer-Policy on newsletter downloads) are kept."""
    h = response.headers
    h.setdefault("X-Frame-Options", "SAMEORIGIN")
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=(), usb=()")
    if _is_https():
        h.setdefault("Strict-Transport-Security", "max-age=31536000")
    h.pop("Server", None)
    return response


def login_locked() -> str:
    """'' when a login attempt may go ahead, else a message saying how long to wait."""
    now = time.time()
    with _lock:
        _login_failures[:] = [t for t in _login_failures if t > now - LOGIN_FAIL_WINDOW]
        if len(_login_failures) >= LOGIN_FAIL_LIMIT:
            wait = int((_login_failures[0] + LOGIN_FAIL_WINDOW - now) / 60) + 1
            return f"Too many wrong tokens. Try again in {wait} minute(s)."
    return ""


def record_login_failure() -> None:
    with _lock:
        _login_failures.append(time.time())


def init_security(app):
    app.after_request(apply_security_headers)
