from __future__ import annotations

import os
import sys
import traceback
import subprocess
from pathlib import Path
import argparse
import json
import shutil
import threading
import hashlib
import urllib.parse

# --- BULLETPROOF PATH INJECTION ---
local_lib = Path.home() / '.local' / 'lib'
if local_lib.exists():
    for py_dir in local_lib.glob('python*'):
        site_pkg = py_dir / 'site-packages'
        if site_pkg.exists() and str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))
# ---------------------------------

# Required dependencies
REQUIRED_PACKAGES = {
    'Flask': 'flask',
    'Markdown': 'markdown',
    'Werkzeug': 'werkzeug',
    'python-dotenv': 'dotenv',
    'bleach': 'bleach',
    'libcst': 'libcst',
    'requests': 'requests',
    'flask-socketio': 'flask_socketio'
}

# Required files/directories (Added sync_mod.py to pre-flight checks)
REQUIRED_PATHS = [
    'server.py',
    'config.py',
    'sync_mod.py',
    'templates',
    'static'
]

def install_package(package):
    """Attempts to install a package programmatically."""
    try:
        # Wipe the incompatible 3.10 directory if it exists to prevent syntax errors
        import shutil
        bad_path = Path.home() / '.local' / 'lib' / 'python3.10'
        if bad_path.exists():
            shutil.rmtree(bad_path, ignore_errors=True)
            
        # The WSGI server is running Python 3.9, so we MUST install for 3.9
        if package == 'python-dotenv':
            subprocess.run(['python3.9', '-m', 'pip', 'uninstall', '-y', 'dotenv'], capture_output=True)
            subprocess.check_call(['python3.9', '-m', 'pip', 'install', '--user', 'python-dotenv'])
        else:
            subprocess.check_call(['python3.9', '-m', 'pip', 'install', '--user', package])
        return True
    except Exception as e:
        return False


_GIT_SYNC_DONE = False
_GIT_SYNC_LOCK = threading.Lock()
_SYNC_THREAD_STARTED = False
_SYNC_THREAD_LOCK = threading.Lock()
_EMERGENCY_RETRY_DONE = False
_FLASK_APP = None


def is_production_server() -> bool:
    """Accurately identifies production server environments (e.g. PythonAnywhere)
    while strictly excluding local Windows and WSL2 development environments.
    """
    if os.environ.get("FORCE_BOOTSTRAP_SYNC") == "1":
        return True
    if os.name == "nt":
        return False
    if "WSL_DISTRO_NAME" in os.environ or "WSL_INTEROP" in os.environ:
        return False
    try:
        proc_ver = Path("/proc/version")
        if proc_ver.exists():
            content = proc_ver.read_text(encoding="utf-8", errors="ignore").lower()
            if "microsoft" in content or "wsl" in content:
                return False
    except Exception:
        pass
    if Path("/mnt/c").exists():
        return False

    return (
        "PYTHONANYWHERE_DOMAIN" in os.environ
        or "PYTHONANYWHERE_SITE" in os.environ
        or Path("/var/www").exists()
    )


def trigger_background_sync(base_dir: Path, force: bool = False) -> None:
    """Spawns git sync in a detached background daemon thread so incoming WSGI
    requests are served immediately in milliseconds without blocking on network I/O.
    """
    global _SYNC_THREAD_STARTED
    if not is_production_server() and not force:
        return

    with _SYNC_THREAD_LOCK:
        if _SYNC_THREAD_STARTED and not force:
            return
        _SYNC_THREAD_STARTED = True

    thread = threading.Thread(
        target=auto_sync_git,
        args=(base_dir, force),
        name="GitAutoSyncDaemon",
        daemon=True,
    )
    thread.start()


def auto_sync_git(base_dir: Path, force: bool = False) -> bool:
    """Synchronizes repository with origin/main on worker startup or reload."""
    global _GIT_SYNC_DONE
    if _GIT_SYNC_DONE and not force:
        return True

    if not is_production_server() and not force:
        _GIT_SYNC_DONE = True
        return False

    with _GIT_SYNC_LOCK:
        if _GIT_SYNC_DONE and not force:
            return True

        git_dir = base_dir / ".git"
        if not git_dir.exists():
            _GIT_SYNC_DONE = True
            return False

        git_bin = shutil.which("git") or "/usr/bin/git"
        if not os.path.exists(git_bin) and not shutil.which("git"):
            _GIT_SYNC_DONE = True
            return False

        for base in (git_dir, Path.home() / ".git"):
            if base.is_dir():
                for lock_file in base.rglob("*.lock"):
                    try:
                        lock_file.unlink(missing_ok=True)
                    except Exception:
                        pass

        if os.name != "nt":
            home = Path.home()
            shutil.rmtree(home / ".cache", ignore_errors=True)
            shutil.rmtree(home / ".npm", ignore_errors=True)
            shutil.rmtree(home / ".local" / "share" / "Trash", ignore_errors=True)
            shutil.rmtree(base_dir / ".git" / "modules", ignore_errors=True)
            (base_dir / ".gitmodules").unlink(missing_ok=True)
            (base_dir / "content" / "projects" / "engines" / "antigravity_agent" / ".git").unlink(missing_ok=True)

            pack_dir = git_dir / "objects" / "pack"
            if pack_dir.is_dir():
                for tmp_pack in pack_dir.glob("tmp_*"):
                    tmp_pack.unlink(missing_ok=True)
            (git_dir / "gc.log").unlink(missing_ok=True)

            obj_dir = git_dir / "objects"
            if obj_dir.is_dir():
                for obj in obj_dir.glob("*/*"):
                    try:
                        if obj.is_file() and obj.stat().st_size == 0:
                            obj.unlink(missing_ok=True)
                    except Exception:
                        pass

        token = ""
        token_file = base_dir / "gethub_token.txt"
        if not token_file.exists():
            token_file = Path.home() / "gethub_token.txt"
        if token_file.exists():
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        if not token:
            token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GIT_TOKEN", "").strip()

        authenticated_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/E-profile.git" if token else "origin"

        def _git(args, timeout=30):
            cmd = [git_bin, "-c", "credential.helper="] + args
            try:
                res = subprocess.run(cmd, cwd=str(base_dir), capture_output=True, text=True, timeout=timeout)
                return res.returncode == 0, res.stdout, res.stderr
            except Exception as e:
                return False, "", str(e)

        _git(["config", "user.name", "MikeyMike99"])
        _git(["config", "user.email", "mikeymike@server.local"])
        _git(["merge", "--abort"])
        _git(["rebase", "--abort"])

        traffic_file = base_dir / "traffic_metrics.json"
        if traffic_file.exists():
            _git(["add", "traffic_metrics.json"])
            _git(["commit", "-m", "Auto-preserve local traffic metrics [skip ci]"])

        _git(["checkout", "-B", "main"])

        pull_ok, out, err = _git(["pull", authenticated_url, "main", "--no-edit", "--allow-unrelated-histories", "-X", "ours"], timeout=35)
        if not pull_ok:
            _git(["merge", "--abort"])
            _git(["fetch", authenticated_url, "main", "--prune"], timeout=25)
            _git(["merge", "origin/main", "--no-edit", "-m", "Auto-merge main updates", "-X", "ours"], timeout=20)

        post_sync_script = base_dir / "post_sync.py"
        if post_sync_script.exists():
            py_bin = shutil.which("python3") or sys.executable
            try:
                subprocess.run([py_bin, str(post_sync_script)], cwd=str(base_dir), capture_output=True, text=True, timeout=25)
            except Exception:
                pass

        try:
            wsgi_dir = Path("/var/www/")
            if wsgi_dir.exists():
                for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                    wsgi_file.touch()
        except Exception:
            pass

        _GIT_SYNC_DONE = True
        return True

def _parse_bootstrap_request(environ):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    query_string = environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(query_string)

    post_params = {}
    if method == "POST":
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
            if 0 < content_length < 65536:
                raw_body = environ["wsgi.input"].read(content_length)
                post_params = urllib.parse.parse_qs(raw_body.decode("utf-8", errors="replace"))
        except Exception:
            pass

    cookies = {}
    raw_cookie = environ.get("HTTP_COOKIE", "")
    if raw_cookie:
        for part in raw_cookie.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k.strip()] = v.strip()

    return method, params, post_params, cookies


def authenticate_bootstrap_admin(base_dir: Path, params: dict, post_params: dict, cookies: dict, environ: dict) -> tuple[bool, str, tuple | None]:
    token = (
        (post_params.get("admin_token") or [""])[0].strip()
        or (post_params.get("token") or [""])[0].strip()
        or (params.get("admin_token") or [""])[0].strip()
        or (params.get("token") or [""])[0].strip()
    )

    auth_header = environ.get("HTTP_AUTHORIZATION", "")
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
        if bearer:
            token = bearer

    cookie_hash = cookies.get("bootstrap_admin_session", "").strip()

    admin_hashes = {}
    profiles_path = base_dir / "profiles.json"
    if profiles_path.exists():
        try:
            data = json.loads(profiles_path.read_text(encoding="utf-8"))
            for h, u in data.get("data", {}).items():
                if u.get("is_admin", False):
                    admin_hashes[h] = u.get("username", "Administrator")
        except Exception:
            pass

    sync_secret = os.environ.get("SYNC_SECRET", "").strip()
    if sync_secret:
        admin_hashes[hashlib.sha256(sync_secret.encode("utf-8")).hexdigest()] = "Root (SYNC_SECRET)"

    token_file = base_dir / "gethub_token.txt"
    if not token_file.exists():
        token_file = Path.home() / "gethub_token.txt"
    if token_file.exists():
        try:
            gt = token_file.read_text(encoding="utf-8").strip()
            if gt:
                admin_hashes[hashlib.sha256(gt.encode("utf-8")).hexdigest()] = "Root (GitHub Token)"
        except Exception:
            pass

    master_key_file = base_dir / ".devcore_master.key"
    if master_key_file.exists():
        try:
            mk = master_key_file.read_text(encoding="utf-8").strip()
            if mk:
                admin_hashes[hashlib.sha256(mk.encode("utf-8")).hexdigest()] = "Root (Master Key)"
        except Exception:
            pass

    if cookie_hash and cookie_hash in admin_hashes:
        return True, admin_hashes[cookie_hash], None

    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if token_hash in admin_hashes:
            cookie_hdr = ("Set-Cookie", f"bootstrap_admin_session={token_hash}; Path=/; HttpOnly; SameSite=Lax")
            return True, admin_hashes[token_hash], cookie_hdr

    return False, "", None


def generate_secure_holding_html(login_failed: bool = False) -> bytes:
    """Renders a zero-disclosure maintenance page with an admin authentication gate."""
    alert_html = """
    <div style="background: rgba(255, 0, 85, 0.15); border: 1px solid #ff0055; color: #ff80a0; padding: 10px 14px; margin-bottom: 18px; border-radius: 6px; font-size: 13px; text-align: left;">
        Access denied. Invalid administrator token.
    </div>
    """ if login_failed else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Unavailable | Maintenance Mode</title>
    <style>
        :root {{
            --bg: #090a10;
            --card-bg: rgba(18, 20, 29, 0.95);
            --text-main: #f0f3f8;
            --text-muted: #8b949e;
            --accent-cyan: #00e5ff;
            --accent-magenta: #ff0055;
            --border-color: rgba(255, 255, 255, 0.08);
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: radial-gradient(circle at 50% 20%, #151928 0%, var(--bg) 80%);
            color: var(--text-main);
            font-family: var(--font);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            max-width: 480px;
            width: 100%;
            padding: 36px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), 0 0 1px rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(12px);
            text-align: center;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 229, 255, 0.08);
            border: 1px solid rgba(0, 229, 255, 0.3);
            color: var(--accent-cyan);
            font-family: var(--mono);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 6px 14px;
            border-radius: 999px;
            margin-bottom: 20px;
        }}
        .status-badge::before {{
            content: "";
            width: 8px;
            height: 8px;
            background: var(--accent-cyan);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--accent-cyan);
        }}
        h1 {{
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 10px;
            letter-spacing: -0.5px;
        }}
        p {{
            color: var(--text-muted);
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        .divider {{
            height: 1px;
            background: var(--border-color);
            margin: 24px 0;
        }}
        .admin-section {{
            text-align: left;
        }}
        .admin-label {{
            display: block;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .input-group {{
            display: flex;
            gap: 8px;
        }}
        input[type="password"] {{
            flex: 1;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: #fff;
            font-family: var(--mono);
            font-size: 13px;
            padding: 10px 14px;
            outline: none;
            transition: border-color 0.2s;
        }}
        input[type="password"]:focus {{
            border-color: var(--accent-cyan);
        }}
        button {{
            background: linear-gradient(135deg, #00b4d8 0%, #0077b6 100%);
            border: none;
            border-radius: 6px;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            padding: 10px 16px;
            transition: opacity 0.2s;
        }}
        button:hover {{ opacity: 0.92; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="status-badge">System Status: Standby</div>
        <h1>Service Temporarily Unavailable</h1>
        <p>The application server is currently updating or undergoing maintenance. Please check back shortly.</p>
        
        <div class="divider"></div>
        
        <div class="admin-section">
            <span class="admin-label">Administrator Terminal Access</span>
            {alert_html}
            <form method="POST">
                <div class="input-group">
                    <input type="password" name="admin_token" placeholder="Enter Admin Token / PIN" autocomplete="off" required>
                    <button type="submit">Unlock</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>"""
    return html.encode("utf-8")


def generate_diagnostic_html(error_msg, traceback_str, missing_pkgs, missing_files, admin_name="Administrator"):
    """Generates an authenticated diagnostic dashboard for administrators."""
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BOOTSTRAP | SYSTEM_DIAGNOSTICS</title>
        <style>
            :root {{
                --bg: #0a0a0f;
                --text: #e0e0e0;
                --cyan: #00e5ff;
                --magenta: #ff0055;
                --panel: rgba(20, 20, 25, 0.95);
                --font: 'Consolas', monospace;
            }}
            body {{
                background-color: var(--bg);
                color: var(--text);
                font-family: var(--font);
                padding: 30px;
                margin: 0;
            }}
            .container {{
                max-width: 950px;
                margin: 0 auto;
                background: var(--panel);
                border: 1px solid var(--magenta);
                padding: 30px;
                box-shadow: 0 0 30px rgba(255, 0, 85, 0.2);
                border-radius: 8px;
            }}
            .top-bar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: rgba(0, 229, 255, 0.08);
                border: 1px solid rgba(0, 229, 255, 0.2);
                padding: 10px 16px;
                margin-bottom: 20px;
                border-radius: 4px;
                font-size: 13px;
            }}
            .operator {{
                color: var(--cyan);
                font-weight: bold;
            }}
            .actions {{
                display: flex;
                gap: 10px;
            }}
            .btn {{
                background: rgba(0, 229, 255, 0.15);
                border: 1px solid var(--cyan);
                color: var(--cyan);
                padding: 6px 12px;
                border-radius: 4px;
                font-family: var(--font);
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
            }}
            .btn:hover {{
                background: var(--cyan);
                color: #000;
            }}
            .btn-danger {{
                background: rgba(255, 0, 85, 0.15);
                border-color: var(--magenta);
                color: var(--magenta);
            }}
            .btn-danger:hover {{
                background: var(--magenta);
                color: #fff;
            }}
            h1 {{
                color: var(--magenta);
                text-transform: uppercase;
                letter-spacing: 2px;
                border-bottom: 1px solid var(--magenta);
                padding-bottom: 10px;
                font-size: 20px;
            }}
            h2 {{
                color: var(--cyan);
                margin-top: 25px;
                font-size: 15px;
                letter-spacing: 1px;
            }}
            .status-box {{
                background: rgba(0, 0, 0, 0.5);
                padding: 15px;
                border-left: 4px solid var(--cyan);
                margin: 10px 0;
            }}
            .status-box.error {{
                border-left-color: var(--magenta);
                color: #ffb3c6;
            }}
            pre {{
                background: #000;
                padding: 15px;
                border: 1px solid #333;
                overflow-x: auto;
                color: #a3be8c;
                font-size: 12px;
                line-height: 1.4;
            }}
            ul {{
                list-style-type: square;
                padding-left: 20px;
            }}
            li.missing {{ color: var(--magenta); }}
            li.found {{ color: var(--cyan); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <span class="operator">🛡️ AUTHENTICATED: {admin_name}</span>
                <div class="actions">
                    <form method="POST" style="margin:0;">
                        <input type="hidden" name="action" value="pull_and_restart">
                        <button type="submit" class="btn">⚡ 2-Way Git Sync & Restart</button>
                    </form>
                    <form method="POST" style="margin:0;">
                        <input type="hidden" name="action" value="logout">
                        <button type="submit" class="btn btn-danger">🔒 Lock Console</button>
                    </form>
                </div>
            </div>

            <h1>[CRITICAL_FAILURE] Server Initialization Halted</h1>
            
            <div class="status-box error">
                <strong>ERROR:</strong> {error_msg}
            </div>
            
            <h2>[01] TRACEBACK_LOG</h2>
            <pre>{traceback_str}</pre>

            <h2>[02] DEPENDENCY_CHECK</h2>
            <ul>
    """
    for pkg, status in missing_pkgs.items():
        if status == 'MISSING':
            html += f"<li class='missing'>[MISSING] {pkg} (Attempted auto-install, failed. Please run: pip install --user {pkg})</li>"
        else:
            html += f"<li class='found'>[INSTALLED] {pkg}</li>"

    html += """
            </ul>

            <h2>[03] FILE_SYSTEM_CHECK</h2>
            <ul>
    """
    for path, status in missing_files.items():
        if status == 'MISSING':
            html += f"<li class='missing'>[MISSING] {path}</li>"
        else:
            html += f"<li class='found'>[FOUND] {path}</li>"
            
    html += """
            </ul>
            
            <h2>[04] RECOVERY_INSTRUCTIONS</h2>
            <div class="status-box">
                1. Ensure <strong>sync_mod.py</strong> and all required modules are uploaded.<br>
                2. Verify that <strong>SYNC_SECRET</strong> is set in your environment variables.<br>
                3. Click "2-Way Git Sync & Restart" above or the green "Reload" button on PythonAnywhere.
            </div>
        </div>
    </body>
    </html>
    """
    return html.encode('utf-8')


def render_bootstrap_response(environ, start_response, base_dir: Path, error_msg: str, traceback_str: str, missing_pkgs: dict, missing_files: dict):
    """Guards diagnostic environment information behind administrator authentication."""
    method, params, post_params, cookies = _parse_bootstrap_request(environ)
    action = (post_params.get("action") or params.get("action") or [""])[0].strip()

    if action == "logout":
        headers = [
            ("Content-type", "text/html; charset=utf-8"),
            ("Set-Cookie", "bootstrap_admin_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax")
        ]
        start_response("200 OK", headers)
        return [generate_secure_holding_html()]

    is_admin, admin_name, set_cookie_header = authenticate_bootstrap_admin(base_dir, params, post_params, cookies, environ)

    if not is_admin:
        token_attempted = bool(post_params.get("admin_token") or post_params.get("token") or params.get("admin_token") or params.get("token"))
        headers = [("Content-type", "text/html; charset=utf-8")]
        start_response("503 Service Unavailable", headers)
        return [generate_secure_holding_html(login_failed=token_attempted)]

    if action == "pull_and_restart":
        auto_sync_git(base_dir, force=True)
        try:
            import importlib
            if "server" in sys.modules:
                importlib.reload(sys.modules["server"])
            from server import app as flask_app
            global _FLASK_APP
            _FLASK_APP = flask_app
            return flask_app(environ, start_response)
        except Exception as retry_err:
            error_msg = f"Post-pull reload failed: {retry_err}"
            traceback_str = traceback.format_exc()

    headers = [("Content-type", "text/html; charset=utf-8")]
    if set_cookie_header:
        headers.append(set_cookie_header)

    start_response("200 OK", headers)
    return [generate_diagnostic_html(error_msg, traceback_str, missing_pkgs, missing_files, admin_name)]

# The main WSGI application entry point
def application(environ, start_response):
    global _FLASK_APP
    try:
        # Step 1: Set working directory and prioritize path
        BASE_DIR = Path(__file__).resolve().parent
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        os.chdir(str(BASE_DIR))

        # Fast path: Serve healthy Flask app immediately with zero filesystem overhead
        if _FLASK_APP is not None:
            return _FLASK_APP(environ, start_response)

        # Trigger non-blocking background sync on production servers
        trigger_background_sync(BASE_DIR)

        missing_pkgs = {}
        missing_files = {}
        has_errors = False
        
        # Wipe the incompatible 3.10 directory unconditionally before importing (production only)
        if is_production_server():
            import shutil
            bad_path = Path.home() / '.local' / 'lib' / 'python3.10'
            if bad_path.exists():
                shutil.rmtree(bad_path, ignore_errors=True)
            
        # Step 2: Check dependencies programmatically
        import importlib
        for pkg_name, import_name in REQUIRED_PACKAGES.items():
            try:
                mod = importlib.import_module(import_name)
                # Ensure the correct dotenv is installed
                if import_name == 'dotenv' and not hasattr(mod, 'load_dotenv'):
                    raise ImportError("Wrong dotenv package installed")
                missing_pkgs[pkg_name] = 'INSTALLED'
            except Exception:  # Catch TypeError/SyntaxError from bad versions too!
                success = install_package(pkg_name)
                if success:
                    missing_pkgs[pkg_name] = 'INSTALLED (Auto-Recovered)'
                else:
                    missing_pkgs[pkg_name] = 'MISSING'
                    has_errors = True

        # Step 3: Check required files/directories (including sync_mod.py)
        for path in REQUIRED_PATHS:
            target = BASE_DIR / path
            if target.exists():
                missing_files[path] = 'FOUND'
            else:
                missing_files[path] = 'MISSING'
                has_errors = True

        # Step 3.5: Verify if SYNC_SECRET environment variable is loaded
        # (This warns you if the secret is missing on the server without breaking startup entirely)
        sync_secret_set = os.environ.get("SYNC_SECRET") is not None

        # Step 4: If structural file or package errors exist, render the diagnostic page immediately
        if has_errors:
            return render_bootstrap_response(
                environ, start_response, BASE_DIR,
                "System validation failed. Missing core components or sync module.",
                "None (Caught during pre-flight checks)",
                missing_pkgs,
                missing_files
            )

        try:
            import sync_mod
            from server import app as flask_app
            _FLASK_APP = flask_app
            return _FLASK_APP(environ, start_response)
        except Exception as import_err:
            global _EMERGENCY_RETRY_DONE
            if not _EMERGENCY_RETRY_DONE:
                _EMERGENCY_RETRY_DONE = True
                if is_production_server():
                    synced = auto_sync_git(BASE_DIR, force=True)
                    if synced:
                        try:
                            import importlib
                            if "server" in sys.modules:
                                importlib.reload(sys.modules["server"])
                            from server import app as flask_app
                            _FLASK_APP = flask_app
                            return _FLASK_APP(environ, start_response)
                        except Exception:
                            pass

            missing_files[str(import_err).split("'")[-1]] = 'MISSING (Import Failed)'
            return render_bootstrap_response(
                environ, start_response, BASE_DIR,
                f"Initialization error: {import_err}",
                traceback.format_exc(),
                missing_pkgs,
                missing_files
            )
        
    except Exception as e:
        return render_bootstrap_response(
            environ, start_response, BASE_DIR,
            str(e),
            traceback.format_exc(),
            missing_pkgs if 'missing_pkgs' in locals() else {},
            missing_files if 'missing_files' in locals() else {}
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap and Maintenance Utility")
    parser.add_argument('--undo', '--rollback', action='store_true', help='Revert file renames using rename_history.json')
    args = parser.parse_args()

    if args.undo:
        BASE_DIR = Path(__file__).resolve().parent
        history_file = BASE_DIR / "rename_history.json"
        cert_dir = BASE_DIR / "content" / "certifications" / "digital badges and certificates"
        
        if not history_file.exists():
            print("No rename_history.json found. Nothing to rollback.")
            sys.exit(0)
            
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except Exception as e:
            print(f"Error reading history file: {e}")
            sys.exit(1)
            
        print(f"Attempting to rollback {len(history)} items...")
        success_count = 0
        
        for old_rel, new_rel in reversed(history):
            old_abs = cert_dir / old_rel
            new_abs = cert_dir / new_rel
            
            if not new_abs.exists():
                print(f"[SKIP] Target file not found (already reverted or moved): {new_rel}")
                continue
                
            if old_abs.exists():
                print(f"[SKIP] Original path already exists (avoiding overwrite): {old_rel}")
                continue
                
            try:
                old_abs.parent.mkdir(parents=True, exist_ok=True)
                new_abs.rename(old_abs)
                print(f"[OK] Reverted: {new_rel} -> {old_rel}")
                success_count += 1
            except Exception as e:
                print(f"[ERROR] Could not revert {new_rel}: {e}")
                
        print(f"\nRollback complete. Successfully restored {success_count}/{len(history)} items.")
        
        if success_count == len(history):
            history_file.unlink(missing_ok=True)
            print("Cleared rename_history.json.")
        else:
            print("WARNING: Not all files were restored. rename_history.json was kept.")
            
        sys.exit(0)
        
    print("This is a WSGI bootstrap file. Use --undo to rollback renames.")