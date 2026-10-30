import asyncio
import json
import os
import time
from quart import Blueprint, request, jsonify, current_app, Response

GLOBAL_AUTH_PROC = None
_AUTH_CHECK_CACHE = {"result": None, "ts": 0.0}
AUTH_CACHE_TTL_SECONDS = 300.0

auth_bp = Blueprint('auth_bp', __name__)


def invalidate_auth_check_cache():
    _AUTH_CHECK_CACHE["result"] = None
    _AUTH_CHECK_CACHE["ts"] = 0.0


def _has_local_cli_credentials() -> bool:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return True
    credential_candidates = [
        os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token"),
        os.path.expanduser("~/.devcore_client_key.txt"),
        os.path.expanduser("~/.gemini/antigravity/credentials.json"),
        os.path.expanduser("~/.config/antigravity/credentials.json"),
        os.path.expanduser("~/.gemini/credentials.json"),
        os.path.expanduser("~/.config/gcloud/application_default_credentials.json"),
    ]
    for path in credential_candidates:
        try:
            if os.path.exists(path) and os.path.getsize(path) > 8:
                return True
        except Exception:
            pass
    return False


@auth_bp.route('/api/auth_check')
async def auth_check():
    """Fast-path local credential verification with optional deep CLI fallback."""
    deep_probe = request.args.get("deep") == "1"
    now = time.time()

    if not deep_probe:
        if _AUTH_CHECK_CACHE["result"] is not None and (now - _AUTH_CHECK_CACHE["ts"]) < AUTH_CACHE_TTL_SECONDS:
            return jsonify(_AUTH_CHECK_CACHE["result"])

        if _has_local_cli_credentials():
            fast_res = {"authenticated": True, "fast_path": True}
            _AUTH_CHECK_CACHE["result"] = fast_res
            _AUTH_CHECK_CACHE["ts"] = now
            return jsonify(fast_res)

        try:
            if hasattr(current_app, "security_mgr") and current_app.security_mgr.check_master_signature():
                fast_res = {"authenticated": True, "fast_path": True}
                _AUTH_CHECK_CACHE["result"] = fast_res
                _AUTH_CHECK_CACHE["ts"] = now
                return jsonify(fast_res)
        except Exception:
            pass

    def run_check():
        global GLOBAL_AUTH_PROC
        import subprocess
        import re
        import shutil
        import sys

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bundled_exe = os.path.join(base_dir, "agy.exe")
        bundled_linux = os.path.join(base_dir, "agy")

        real_agy = None
        cand = shutil.which("agy")
        if cand and os.path.exists(cand) and os.path.getsize(cand) > 1024:
            real_agy = cand
        elif os.path.exists(bundled_exe) and os.path.getsize(bundled_exe) > 1024:
            real_agy = bundled_exe
        elif os.path.exists(bundled_linux) and os.path.getsize(bundled_linux) > 1024:
            real_agy = bundled_linux
        elif sys.platform != "win32":
            local_agy = os.path.expanduser("~/.local/bin/agy")
            if os.path.exists(local_agy) and os.path.getsize(local_agy) > 1024:
                real_agy = local_agy
        elif sys.platform == "win32":
            try:
                wsl_agy = subprocess.check_output(
                    ["wsl.exe", "-e", "bash", "-lc", "which agy"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                ).strip()
                if wsl_agy and wsl_agy.startswith("/"):
                    real_agy = wsl_agy
            except Exception:
                pass

        if not real_agy:
            return {"authenticated": True}

        if GLOBAL_AUTH_PROC:
            try:
                GLOBAL_AUTH_PROC.kill()
            except Exception:
                pass

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["WSLENV"] = "PYTHONUNBUFFERED/u"

        cmd = [real_agy, '--print', 'ping']
        if sys.platform == 'win32' and not real_agy.endswith('.exe'):
            cmd = ['wsl.exe', '-e'] + cmd

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            for _ in range(15):
                line = proc.stdout.readline()
                if not line:
                    break

                if (
                    "Authentication required" in line
                    or "oauth2" in line
                    or "Waiting for authentication" in line
                    or "https://accounts.google.com" in line
                ):
                    match = re.search(r'(https://accounts\.google\.com/[^\s]+)', line)
                    if match:
                        GLOBAL_AUTH_PROC = proc
                        return {"authenticated": False, "url": match.group(1)}

                if "pong" in line.lower():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    GLOBAL_AUTH_PROC = None
                    return {"authenticated": True}

            try:
                proc.kill()
            except Exception:
                pass
            GLOBAL_AUTH_PROC = None
            return {"authenticated": False, "url": "#"}
        except Exception as e:
            print(f"Auth check error in thread: {e}")
            return {"authenticated": False, "url": "#"}

    try:
        result = await asyncio.to_thread(run_check)
        _AUTH_CHECK_CACHE["result"] = result
        _AUTH_CHECK_CACHE["ts"] = time.time()
        return jsonify(result)
    except Exception as e:
        print(f"Auth check error: {e}")
        return jsonify({"authenticated": False, "url": "#"})


@auth_bp.route('/login')
async def login_page():
    import sys
    main_mod = sys.modules.get("__main__") or sys.modules.get("core.server")
    read_fn = getattr(main_mod, "read_asset", None)
    if read_fn is None:
        from core.server import read_asset as read_fn
    template_bytes = read_fn("sandbox/templates/login.html")
    if not template_bytes:
        return "Login template not found", 404
    return template_bytes.decode('utf-8'), 200, {'Content-Type': 'text/html; charset=utf-8'}


@auth_bp.route('/api/set_api_key', methods=['POST'])
async def set_api_key():
    data = await request.get_json() or {}
    if data.get('demo') is True or data.get('api_key') == 'demo':
        now = time.time()
        _AUTH_CHECK_CACHE["result"] = {"authenticated": True, "fast_path": True, "demo_mode": True}
        _AUTH_CHECK_CACHE["ts"] = now
        res = current_app.security_mgr.authenticate("admin:admin")
        return jsonify({
            "success": True,
            "demo": True,
            "token": res.get("token") if res else None,
            "user": res.get("user") if res else None
        })

    api_key = data.get('api_key', '').strip()
    if not api_key:
        return jsonify({"success": False, "error": "No API key provided"})

    os.environ["GEMINI_API_KEY"] = api_key
    client_key_path = os.path.expanduser("~/.devcore_client_key.txt")
    try:
        with open(client_key_path, "w", encoding="utf-8") as f:
            f.write(api_key)
        invalidate_auth_check_cache()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@auth_bp.route('/api/auth_submit', methods=['POST'])
async def auth_submit():
    print("[auth_submit] Starting request...")
    data = await request.get_json() or {}
    token = data.get('token', '').strip()
    if not token:
        print("[auth_submit] No token provided")
        return jsonify({"success": False, "error": "No token provided"})

    def run_submit():
        global GLOBAL_AUTH_PROC
        if not GLOBAL_AUTH_PROC:
            return {"success": False, "error": "No auth check process running"}

        proc = GLOBAL_AUTH_PROC
        try:
            proc.stdin.write(token + "\n")
            proc.stdin.flush()

            for _ in range(15):
                line = proc.stdout.readline()
                if not line:
                    break

                out = line.lower()
                if (
                    "authentication failed" in out
                    or "invalid code" in out
                    or "error" in out
                    or "timed out" in out
                    or "invalid_grant" in out
                    or "malformed" in out
                ):
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    GLOBAL_AUTH_PROC = None
                    return {"success": False}

                if (
                    "authentication successful" in out
                    or "select " in out
                    or "project" in out
                    or "workspace" in out
                    or "pong" in out
                ):
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    GLOBAL_AUTH_PROC = None
                    return {"success": True}

            try:
                proc.kill()
            except Exception:
                pass
            GLOBAL_AUTH_PROC = None
            return {"success": True}
        except Exception as e:
            GLOBAL_AUTH_PROC = None
            return {"success": False, "error": str(e)}

    try:
        result = await asyncio.to_thread(run_submit)
        invalidate_auth_check_cache()
        return jsonify(result)
    except Exception as e:
        print(f"[auth_submit] Exception: {e}")
        return jsonify({"success": False, "error": str(e)})


@auth_bp.route('/api/auth/keys', methods=['GET'])
async def list_keys():
    user = get_current_user()
    if not user or user.get("role") not in ["super_admin", "admin"]:
        return jsonify({"error": "Admin access required"}), 403
    return jsonify(current_app.security_mgr.get_all_keys())


@auth_bp.route('/api/auth/scrub', methods=['POST'])
async def scrub_auth():
    """Removes all Google OAuth and Gemini API key configuration to test fresh state."""
    if 'GEMINI_API_KEY' in os.environ:
        del os.environ['GEMINI_API_KEY']

    paths = [
        os.path.expanduser('~/.devcore_client_key.txt'),
        os.path.expanduser('~/.config/gcloud/application_default_credentials.json'),
        os.path.expanduser('~/.gemini/credentials.json'),
        os.path.expanduser('~/.gemini/antigravity/credentials.json'),
        os.path.expanduser('~/.config/antigravity/credentials.json'),
        os.path.expandvars('%APPDATA%/gcloud/application_default_credentials.json'),
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    invalidate_auth_check_cache()
    return jsonify({"success": True, "message": "Host Authentication scrubbed. You can now test the setup flow."})


@auth_bp.route('/api/auth/keys', methods=['POST'])
async def create_key():
    user = get_current_user()
    if not user or user.get("role") not in ["super_admin", "admin"]:
        return jsonify({"error": "Admin access required"}), 403
    data = await request.get_json() or {}
    role = data.get("role", "guest")
    name = data.get("name", "New User")
    allowed_projects = data.get("allowed_projects")
    expires_in_days = float(data.get("expires_in_days", 30))

    new_key = current_app.security_mgr.generate_key(role, name, allowed_projects, expires_in_days)
    return jsonify({"success": True, "key": new_key})


@auth_bp.route('/api/auth/keys/<key_id>', methods=['DELETE'])
async def delete_key(key_id):
    user = get_current_user()
    if not user or user.get("role") not in ["super_admin", "admin"]:
        return jsonify({"error": "Admin access required"}), 403
    success = current_app.security_mgr.delete_key(key_id)
    return jsonify({"success": success})


@auth_bp.route('/api/auth/system-status', methods=['GET'])
async def auth_system_status():
    """First-Time Setup System Status Check."""
    is_super = current_app.security_mgr.check_master_signature()
    return jsonify({"super_admin": is_super})


@auth_bp.route('/api/auth_demo', methods=['GET', 'POST'])
async def auth_demo():
    res = current_app.security_mgr.authenticate("admin:admin")
    if not res:
        res = {
            "token": "sec-demo-" + os.urandom(8).hex(),
            "user": {
                "username": "Michael (Admin)",
                "role": "admin",
                "name": "Michael (Admin)",
                "allowed_projects": ["*"]
            }
        }
    now = time.time()
    _AUTH_CHECK_CACHE["result"] = {"authenticated": True, "fast_path": True, "demo_mode": True}
    _AUTH_CHECK_CACHE["ts"] = now
    return jsonify({
        "success": True,
        "authenticated": True,
        "token": res.get("token"),
        "user": res.get("user"),
        "message": "Demo mode authenticated successfully"
    })


@auth_bp.route('/api/auth/login', methods=['POST'])
async def auth_login():
    data = await request.get_json() or {}
    if data.get('demo') is True or data.get('access_key') == 'demo':
        res = current_app.security_mgr.authenticate("admin:admin")
        now = time.time()
        _AUTH_CHECK_CACHE["result"] = {"authenticated": True, "fast_path": True, "demo_mode": True}
        _AUTH_CHECK_CACHE["ts"] = now
        return jsonify(res)
    access_key = data.get('access_key')
    if access_key:
        res = current_app.security_mgr.authenticate(access_key)
    else:
        username = data.get('username')
        password = data.get('password')
        res = current_app.security_mgr.authenticate(f"{username}:{password}")
    if res:
        return jsonify(res)
    return jsonify({"error": "Invalid username or password"}), 401


@auth_bp.route('/api/auth/logout', methods=['POST'])
async def auth_logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    current_app.security_mgr.logout(token)
    return jsonify({"success": True})


@auth_bp.route('/api/auth/me', methods=['GET'])
async def auth_me():
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    user = current_app.security_mgr.get_user_from_token(token)
    if user:
        return jsonify({"user": user})
    return jsonify({"error": "Unauthorized"}), 401


def get_current_user():
    from quart import request, current_app
    auth_hdr = request.headers.get('Authorization', '')
    token = auth_hdr.replace('Bearer ', '').strip()
    if not token:
        token = request.args.get('token', '').strip()
    user = current_app.security_mgr.get_user_from_token(token) if token else None
    if not user and hasattr(current_app, "security_mgr") and current_app.security_mgr.check_master_signature():
        user = {
            "username": "Michael (Admin)",
            "role": "super_admin",
            "name": "Michael (Admin)",
            "allowed_projects": ["*"]
        }
    return user


@auth_bp.route('/api/user/subscription/set', methods=['POST'])
async def set_user_subscription_route():
    """Validates and securely stores personal BYOS credentials with a 7-day TTL countdown or ephemeral RAM storage."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = await request.get_json() or {}
    provider = data.get("provider", "gemini").strip()
    credential = data.get("credential", "").strip()
    ttl_days = float(data.get("ttl_days", 7.0))
    storage_mode = str(data.get("storage_mode", "vault")).lower().strip()

    if not credential:
        return jsonify({"success": False, "error": "No credential provided"}), 400

    from security.subscription_guard import verify_subscription_health, set_user_subscription
    valid, reason = verify_subscription_health(provider, credential)
    if not valid:
        return jsonify({"success": False, "error": reason}), 400

    user_identifier = user.get("username") or user.get("name") or "guest"
    result = set_user_subscription(
        user_id=user_identifier,
        provider=provider,
        credential=credential,
        ttl_days=ttl_days,
        storage_mode=storage_mode
    )
    return jsonify(result)


@auth_bp.route('/api/user/subscription/status', methods=['GET'])
async def get_user_subscription_status():
    """Returns the remaining TTL countdown, active provider, and privacy metadata for the user's BYOS credentials."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    from security.subscription_guard import get_user_subscription
    user_identifier = user.get("username") or user.get("name") or "guest"
    sub = get_user_subscription(user_identifier)
    if not sub:
        return jsonify({
            "configured": False,
            "days_remaining": 0,
            "hours_remaining": 0,
            "storage_mode": None,
            "is_ephemeral": False,
            "scope_description": "Generative Language Model API Only (https://www.googleapis.com/auth/generative-language). Zero access to personal Google Account data or email.",
            "revocation_url": "https://myaccount.google.com/permissions",
            "message": "No active personal subscription. Personal tasks will strictly halt."
        })

    return jsonify({
        "configured": True,
        "provider": sub.get("provider"),
        "storage_mode": sub.get("storage_mode", "vault"),
        "is_ephemeral": bool(sub.get("is_ephemeral")),
        "days_remaining": sub.get("days_remaining"),
        "hours_remaining": sub.get("hours_remaining"),
        "expires_at": sub.get("expires_at"),
        "user_id": sub.get("user_id"),
        "scope_description": "Generative Language Model API Only (https://www.googleapis.com/auth/generative-language). Zero access to personal Google Account data or email.",
        "revocation_url": "https://myaccount.google.com/permissions"
    })


@auth_bp.route('/api/user/subscription', methods=['DELETE'])
async def delete_user_subscription_route():
    """Immediately revokes personal BYOS credentials and scrubs the isolated user chamber."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    from security.subscription_guard import delete_user_subscription
    user_identifier = user.get("username") or user.get("name") or "guest"
    deleted = delete_user_subscription(user_identifier)
    return jsonify({"success": deleted})

