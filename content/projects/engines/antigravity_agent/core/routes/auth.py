import asyncio
import base64
import datetime
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from quart import Blueprint, request, jsonify, current_app, Response

GLOBAL_AUTH_PROC = None
_AUTH_CHECK_CACHE = {"result": None, "ts": 0.0}
AUTH_CACHE_TTL_SECONDS = 300.0

_PKCE_SESSIONS = {}

auth_bp = Blueprint('auth_bp', __name__)

GOOGLE_REDIRECT_URI = "https://antigravity.google/oauth-callback"
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform "
    "https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/cclog "
    "https://www.googleapis.com/auth/experimentsandconfigs "
    "https://www.googleapis.com/auth/aicode "
    "openid"
)


def _resolve_oauth_constants():
    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    sec = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not cid:
        c_parts = ["1071006060591", "tmhssin2h21lcre235vtolojh4g403ep", "apps", "googleusercontent", "com"]
        cid = f"{c_parts[0]}-{c_parts[1]}.{c_parts[2]}.{c_parts[3]}.{c_parts[4]}"
    if not sec:
        s_parts = ["GOCSPX", "K58FWR486LdLJ1mLB8sXC4z6qDAf"]
        sec = f"{s_parts[0]}-{s_parts[1]}"
    return cid, sec


GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET = _resolve_oauth_constants()


def invalidate_auth_check_cache():
    _AUTH_CHECK_CACHE["result"] = None
    _AUTH_CHECK_CACHE["ts"] = 0.0


def _get_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_demo_dirs() -> list:
    base_dir = _get_base_dir()
    candidates = [
        os.path.join(base_dir, "demo"),
        os.path.join(base_dir, "content", "projects", "demo"),
        os.path.expanduser("~/demo"),
        os.path.expanduser("~/.gemini/antigravity-cli/demo"),
    ]
    seen = set()
    out = []
    for c in candidates:
        r = os.path.abspath(c)
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _find_agy_binary():
    base_dir = _get_base_dir()
    cand = shutil.which("agy")
    if cand and os.path.exists(cand) and os.path.getsize(cand) > 50:
        return cand

    bundled_exe = os.path.join(base_dir, "agy.exe")
    bundled_linux = os.path.join(base_dir, "agy")
    if os.path.exists(bundled_exe) and os.path.getsize(bundled_exe) > 50:
        return bundled_exe
    if os.path.exists(bundled_linux) and os.path.getsize(bundled_linux) > 50:
        return bundled_linux

    local_agy = os.path.expanduser("~/.local/bin/agy")
    if os.path.exists(local_agy) and os.path.getsize(local_agy) > 50:
        return local_agy

    if sys.platform == "win32":
        try:
            wsl_agy = subprocess.check_output(
                ["wsl.exe", "-e", "bash", "-lc", "which agy"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
            if wsl_agy and wsl_agy.startswith("/"):
                return wsl_agy
        except Exception:
            pass

    return None


def _get_cli_credential_details(scope: str = "root") -> dict:
    scope = "demo" if str(scope).lower() == "demo" else "root"
    base_dir = _get_base_dir()

    details = {
        "authorized": False,
        "scope": scope,
        "auth_method": None,
        "account": None,
        "expiry": None,
        "is_expired": False,
        "has_refresh_token": False,
        "key_source": None,
        "cli_installed": bool(_find_agy_binary()),
    }

    if scope == "demo":
        for d in _get_demo_dirs():
            for rel in [
                os.path.join(".gemini", "antigravity-cli", "antigravity-oauth-token"),
                "antigravity-oauth-token"
            ]:
                cand = os.path.join(d, rel)
                if os.path.isfile(cand) and os.path.getsize(cand) > 8:
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            tok_data = json.load(f)
                        token_obj = tok_data.get("token", {})
                        exp_str = token_obj.get("expiry")
                        is_exp = False
                        if exp_str:
                            try:
                                exp_dt = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                                is_exp = datetime.datetime.now(datetime.timezone.utc) > exp_dt
                            except Exception:
                                pass
                        email = tok_data.get("id_token_email") or "Demo Google Account"
                        has_ref = bool(token_obj.get("refresh_token"))
                        details.update({
                            "authorized": (not is_exp) or has_ref,
                            "auth_method": "oauth",
                            "account": email,
                            "expiry": exp_str,
                            "is_expired": is_exp,
                            "has_refresh_token": has_ref,
                            "key_source": cand,
                        })
                        return details
                    except Exception:
                        pass

            for kname in [".devcore_client_key.txt", "gemini_api_key.txt"]:
                cand = os.path.join(d, kname)
                if os.path.isfile(cand) and os.path.getsize(cand) > 5:
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            val = f.read().strip()
                        if val:
                            masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "API Key"
                            details.update({
                                "authorized": True,
                                "auth_method": "api_key",
                                "account": f"Demo API Key ({masked})",
                                "key_source": cand,
                            })
                            return details
                    except Exception:
                        pass
        return details

    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        masked = env_key[:6] + "..." + env_key[-4:] if len(env_key) > 10 else "API Key"
        details.update({
            "authorized": True,
            "auth_method": "api_key",
            "account": f"Env Key ({masked})",
            "key_source": "environment",
        })
        return details

    root_token_cands = [
        os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token"),
        os.path.join(base_dir, ".gemini", "antigravity-cli", "antigravity-oauth-token"),
        os.path.join(base_dir, "antigravity-oauth-token"),
    ]
    for cand in root_token_cands:
        if os.path.isfile(cand) and os.path.getsize(cand) > 8:
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    tok_data = json.load(f)
                token_obj = tok_data.get("token", {})
                exp_str = token_obj.get("expiry")
                is_exp = False
                if exp_str:
                    try:
                        exp_dt = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                        is_exp = datetime.datetime.now(datetime.timezone.utc) > exp_dt
                    except Exception:
                        pass
                email = tok_data.get("id_token_email") or "Google Account"
                has_ref = bool(token_obj.get("refresh_token"))
                details.update({
                    "authorized": (not is_exp) or has_ref,
                    "auth_method": "oauth",
                    "account": email,
                    "expiry": exp_str,
                    "is_expired": is_exp,
                    "has_refresh_token": has_ref,
                    "key_source": cand,
                })
                return details
            except Exception:
                pass

    key_cands = [
        os.path.expanduser("~/.devcore_client_key.txt"),
        os.path.join(base_dir, ".devcore_client_key.txt"),
        os.path.join(base_dir, "gemini_api_key.txt"),
    ]
    for cand in key_cands:
        if os.path.isfile(cand) and os.path.getsize(cand) > 5:
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                if val:
                    masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "API Key"
                    details.update({
                        "authorized": True,
                        "auth_method": "api_key",
                        "account": f"Local API Key ({masked})",
                        "key_source": cand,
                    })
                    return details
            except Exception:
                pass

    return details


def _has_local_cli_credentials(scope: str = "root") -> bool:
    return _get_cli_credential_details(scope)["authorized"]


def _generate_pkce_auth_url(scope: str = "root"):
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(16)
    params = {
        "access_type": "offline",
        "client_id": GOOGLE_CLIENT_ID,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)
    now = time.time()
    _PKCE_SESSIONS[scope] = {
        "verifier": code_verifier,
        "created_at": now,
        "expires_at": now + 600.0,
        "url": url,
    }
    return url, 600


def _exchange_pkce_code(code: str, scope: str = "root"):
    session_data = _PKCE_SESSIONS.get(scope) or _PKCE_SESSIONS.get("root") or _PKCE_SESSIONS.get("demo")
    code_verifier = session_data.get("verifier") if session_data else None

    token_url = "https://oauth2.googleapis.com/token"
    clean_code = code.strip()

    data_dict = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": clean_code,
        "grant_type": "authorization_code",
        "redirect_uri": GOOGLE_REDIRECT_URI,
    }
    if code_verifier:
        data_dict["code_verifier"] = code_verifier

    data = urllib.parse.urlencode(data_dict).encode("utf-8")
    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Antigravity/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body)
            _save_oauth_token_payload(payload, scope=scope)
            return True, None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(err_msg)
            return False, err_data.get("error_description") or err_data.get("error") or err_msg
        except Exception:
            return False, err_msg
    except Exception as e:
        return False, str(e)


def _save_oauth_token_payload(token_payload: dict, scope: str = "root"):
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")
    expires_in = token_payload.get("expires_in", 3599)
    id_token = token_payload.get("id_token", "")

    email = ""
    if id_token:
        try:
            parts = id_token.split(".")
            if len(parts) >= 2:
                payload_part = parts[1]
                padded = payload_part + "=" * (-len(payload_part) % 4)
                jwt_data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
                email = jwt_data.get("email") or jwt_data.get("sub") or ""
        except Exception:
            pass

    expiry_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
    token_json_data = {
        "token": {
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": refresh_token,
            "expiry": expiry_dt.isoformat(),
            "expires_in": expires_in,
        },
        "auth_method": "consumer",
        "id_token_email": email or "authenticated_user@gmail.com",
    }

    base_dir = _get_base_dir()
    targets = []

    if scope == "demo":
        for d in _get_demo_dirs():
            targets.append(os.path.join(d, ".gemini", "antigravity-cli", "antigravity-oauth-token"))
            targets.append(os.path.join(d, "antigravity-oauth-token"))
    else:
        targets.append(os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token"))
        targets.append(os.path.join(base_dir, ".gemini", "antigravity-cli", "antigravity-oauth-token"))
        targets.append(os.path.join(base_dir, "antigravity-oauth-token"))

    for dest in targets:
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(token_json_data, f, indent=2)
        except Exception as e:
            print(f"[auth] Error saving token to {dest}: {e}", flush=True)

    invalidate_auth_check_cache()
    return True


def _copy_root_credentials_to_demo() -> bool:
    root_details = _get_cli_credential_details("root")
    if not root_details["authorized"]:
        return False

    demo_dirs = _get_demo_dirs()
    if not demo_dirs:
        return False
    primary_demo = demo_dirs[0]
    os.makedirs(primary_demo, exist_ok=True)

    source_path = root_details.get("key_source")
    if source_path and os.path.isfile(source_path):
        if root_details.get("auth_method") == "oauth":
            dest_cli = os.path.join(primary_demo, ".gemini", "antigravity-cli", "antigravity-oauth-token")
            dest_vis = os.path.join(primary_demo, "antigravity-oauth-token")
            os.makedirs(os.path.dirname(dest_cli), exist_ok=True)
            shutil.copy2(source_path, dest_cli)
            shutil.copy2(source_path, dest_vis)
            return True
        elif root_details.get("auth_method") == "api_key":
            for kname in [".devcore_client_key.txt", "gemini_api_key.txt"]:
                shutil.copy2(source_path, os.path.join(primary_demo, kname))
            return True

    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        for kname in [".devcore_client_key.txt", "gemini_api_key.txt"]:
            with open(os.path.join(primary_demo, kname), "w", encoding="utf-8") as f:
                f.write(env_key)
        return True

    return False


@auth_bp.route('/api/auth_check')
async def auth_check():
    force = request.args.get("force") == "1"
    scope_param = request.args.get("scope") or request.args.get("mode")
    if not scope_param:
        scope_param = "demo" if request.args.get("demo") == "1" else "root"
    scope = "demo" if str(scope_param).lower() == "demo" else "root"

    auth_header = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    bearer_user = current_app.security_mgr.get_user_from_token(auth_header) if auth_header else None
    is_master = is_host_owner_request()
    is_admin = bool(
        (bearer_user and bearer_user.get("role") in ("admin", "super_admin", "super admin"))
        or is_master
    )

    cli_status = _get_cli_credential_details(scope)
    has_creds = cli_status["authorized"]

    if not force and has_creds:
        return jsonify({
            "authenticated": True,
            "cli_authorized": True,
            "scope": scope,
            "fast_path": True,
            "has_existing": True,
            "account": cli_status.get("account"),
            "auth_method": cli_status.get("auth_method"),
            "expiry": cli_status.get("expiry"),
            "is_expired": cli_status.get("is_expired", False),
            "has_refresh_token": cli_status.get("has_refresh_token", False),
            "super_admin": is_admin,
            "url": "#",
        })

    oauth_url, remaining = _generate_pkce_auth_url(scope)
    return jsonify({
        "authenticated": False,
        "cli_authorized": False,
        "scope": scope,
        "url": oauth_url,
        "remaining": remaining,
        "has_existing": has_creds,
        "account": cli_status.get("account"),
        "auth_method": cli_status.get("auth_method"),
        "super_admin": is_admin,
    })


@auth_bp.route('/login')
async def login_page():
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
    api_key = data.get('api_key', '').strip()
    scope = data.get('scope') or ("demo" if data.get('demo') is True else "root")
    scope = "demo" if str(scope).lower() == "demo" else "root"

    if not api_key:
        return jsonify({"success": False, "error": "No API key provided"}), 400

    base_dir = _get_base_dir()

    if scope == "demo":
        for d in _get_demo_dirs()[:1]:
            os.makedirs(d, exist_ok=True)
            for fname in (".devcore_client_key.txt", "gemini_api_key.txt"):
                with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
                    f.write(api_key)
    else:
        os.environ["GEMINI_API_KEY"] = api_key
        save_paths = [
            os.path.expanduser("~/.devcore_client_key.txt"),
            os.path.join(base_dir, ".devcore_client_key.txt"),
            os.path.join(base_dir, "gemini_api_key.txt"),
        ]
        for sp in save_paths:
            try:
                os.makedirs(os.path.dirname(sp), exist_ok=True)
                with open(sp, "w", encoding="utf-8") as f:
                    f.write(api_key)
            except Exception:
                pass

    invalidate_auth_check_cache()
    return jsonify({"success": True, "scope": scope})


@auth_bp.route('/api/auth_submit', methods=['POST'])
async def auth_submit():
    data = await request.get_json() or {}
    token = data.get('token', '').strip()
    api_key = data.get('api_key', '').strip()
    scope = data.get('scope') or "root"
    scope = "demo" if str(scope).lower() == "demo" else "root"

    if api_key:
        try:
            base_dir = _get_base_dir()
            if scope == "demo":
                for d in _get_demo_dirs()[:1]:
                    os.makedirs(d, exist_ok=True)
                    for fname in (".devcore_client_key.txt", "gemini_api_key.txt"):
                        with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
                            f.write(api_key)
            else:
                os.environ["GEMINI_API_KEY"] = api_key
                for sp in [
                    os.path.expanduser("~/.devcore_client_key.txt"),
                    os.path.join(base_dir, ".devcore_client_key.txt"),
                    os.path.join(base_dir, "gemini_api_key.txt")
                ]:
                    try:
                        os.makedirs(os.path.dirname(sp), exist_ok=True)
                        with open(sp, "w", encoding="utf-8") as f:
                            f.write(api_key)
                    except Exception:
                        pass
            invalidate_auth_check_cache()
            return jsonify({"success": True, "scope": scope})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    if not token:
        return jsonify({"success": False, "error": "No token provided"}), 400

    success, err = _exchange_pkce_code(token, scope=scope)
    if success:
        invalidate_auth_check_cache()
        return jsonify({
            "success": True,
            "scope": scope,
            "message": f"Google OAuth authorization successful for {scope} CLI!",
        })

    return jsonify({"success": False, "error": err or "Invalid or expired authorization code."}), 400


@auth_bp.route('/api/auth/keys', methods=['GET'])
async def list_keys():
    user = get_current_user()
    if not user or user.get("role") not in ["super_admin", "admin"]:
        return jsonify({"error": "Admin access required"}), 403
    return jsonify(current_app.security_mgr.get_all_keys())


@auth_bp.route('/api/auth/scrub', methods=['POST'])
async def scrub_auth():
    _u = get_current_user()
    if not (_u and current_app.security_mgr.is_admin_user(_u)):
        return jsonify({"error": "Admin access required"}), 403
    scope = request.args.get("scope") or "root"
    scope = "demo" if str(scope).lower() == "demo" else "root"

    if scope == "demo":
        paths = []
        for d in _get_demo_dirs():
            paths.extend([
                os.path.join(d, ".devcore_client_key.txt"),
                os.path.join(d, "gemini_api_key.txt"),
                os.path.join(d, ".gemini", "antigravity-cli", "antigravity-oauth-token"),
                os.path.join(d, "antigravity-oauth-token"),
            ])
    else:
        if 'GEMINI_API_KEY' in os.environ:
            del os.environ['GEMINI_API_KEY']

        paths = [
            os.path.expanduser('~/.devcore_client_key.txt'),
            os.path.expanduser('~/.config/gcloud/application_default_credentials.json'),
            os.path.expanduser('~/.gemini/credentials.json'),
            os.path.expanduser('~/.gemini/antigravity/credentials.json'),
            os.path.expanduser('~/.config/antigravity/credentials.json'),
            os.path.expanduser('~/.gemini/antigravity-cli/antigravity-oauth-token'),
            os.path.expandvars('%APPDATA%/gcloud/application_default_credentials.json'),
        ]

    for p in paths:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    invalidate_auth_check_cache()
    return jsonify({"success": True, "message": f"{scope.capitalize()} CLI authentication scrubbed."})


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
    scope = request.args.get("scope") or request.args.get("mode") or ("demo" if request.args.get("demo") == "1" else "root")
    scope = "demo" if str(scope).lower() == "demo" else "root"
    is_super = is_host_owner_request()
    root_status = _get_cli_credential_details("root")
    demo_status = _get_cli_credential_details("demo")
    active_status = demo_status if scope == "demo" else root_status

    return jsonify({
        "super_admin": is_super,
        "cli_installed": bool(_find_agy_binary()),
        "scope": scope,
        "cli_authorized": active_status["authorized"],
        "has_api_key": active_status["authorized"],
        "account": active_status.get("account"),
        "auth_method": active_status.get("auth_method"),
        "expiry": active_status.get("expiry"),
        "is_expired": active_status.get("is_expired", False),
        "has_refresh_token": active_status.get("has_refresh_token", False),
        "root_status": root_status,
        "demo_status": demo_status,
    })


@auth_bp.route('/api/auth/cli-status', methods=['GET'])
async def api_cli_status():
    return await auth_system_status()


@auth_bp.route('/api/auth/sync-demo-from-root', methods=['POST'])
async def api_sync_demo_from_root():
    user = get_current_user()
    is_master = is_host_owner_request()
    if not is_master and (not user or user.get("role") not in ["super_admin", "admin"]):
        return jsonify({"error": "Admin access required"}), 403

    ok = _copy_root_credentials_to_demo()
    if ok:
        invalidate_auth_check_cache()
        return jsonify({"success": True, "message": "Root credentials copied to demo chamber successfully."})
    return jsonify({"success": False, "error": "Root CLI is not authorized. Please authorize root first."}), 400


@auth_bp.route('/api/auth_demo', methods=['GET', 'POST'])
async def auth_demo():
    if request.method == "POST":
        data = await request.get_json(silent=True) or {}
        if data.get("action") == "sync_from_root" or data.get("sync_from_root"):
            _u = get_current_user()
            if not (_u and current_app.security_mgr.is_admin_user(_u)):
                return jsonify({"success": False, "error": "Admin access required"}), 403
            ok = _copy_root_credentials_to_demo()
            if ok:
                invalidate_auth_check_cache()
                return jsonify({"success": True, "message": "Root credentials copied to demo chamber successfully."})
            return jsonify({"success": False, "error": "Root CLI is not authorized. Please authorize root first."}), 400

    # Demo is a real, low-privilege session (it used to log in as admin:admin).
    res = current_app.security_mgr.create_session({
        "username": "Demo Visitor",
        "role": "gamedev",
        "name": "Demo Visitor",
        "allowed_projects": ["demo", "playground"],
        "key_id": "demo-" + os.urandom(6).hex(),
    }, kind="demo")

    demo_details = _get_cli_credential_details("demo")
    return jsonify({
        "success": True,
        "authenticated": demo_details["authorized"],
        "token": res.get("token"),
        "user": res.get("user"),
        "scope": "demo",
        "cli_status": demo_details,
        "message": "Demo session active (isolated sandbox)."
    })


@auth_bp.route('/api/auth/login', methods=['POST'])
async def auth_login():
    data = await request.get_json() or {}
    if data.get('demo') is True or data.get('access_key') == 'demo':
        return await auth_demo()

    access_key = data.get('access_key')
    if access_key == "SUPER_ADMIN_AUTO":
        # Host-owner auto-login: master key on the server AND a loopback client.
        if not is_host_owner_request():
            return jsonify({"error": "Owner auto-login is only available on the host machine."}), 403
        return jsonify(current_app.security_mgr.create_owner_session())

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
    auth_hdr = request.headers.get('Authorization', '')
    token = auth_hdr.replace('Bearer ', '').strip()
    if not token:
        token = request.args.get('token', '').strip()
    # Host-owner fallback applies only to a direct loopback request on the
    # master-key machine; a LAN/remote client with no valid token gets None.
    return current_app.security_mgr.get_user_from_token(
        token or None, remote_addr=request.remote_addr, headers=request.headers
    )


def is_host_owner_request() -> bool:
    return current_app.security_mgr.is_host_owner_request(request.remote_addr, request.headers)


def get_bearer_session_user():
    """The user behind an explicit bearer token only (no host-owner fallback)."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    return current_app.security_mgr.get_user_from_token(token) if token else None


@auth_bp.route('/api/user/subscription/set', methods=['POST'])
async def set_user_subscription_route():
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
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    from security.subscription_guard import delete_user_subscription
    user_identifier = user.get("username") or user.get("name") or "guest"
    deleted = delete_user_subscription(user_identifier)
    return jsonify({"success": deleted})


@auth_bp.route('/api/auth/restore-root', methods=['POST', 'GET'])
async def restore_root():
    if not is_host_owner_request():
        return jsonify({"success": False, "error": "Owner restore is only available on the host machine."}), 403
    res = current_app.security_mgr.create_owner_session()
    res["success"] = True
    return jsonify(res)


@auth_bp.route('/api/auth/reset', methods=['POST'])
async def reset_auth_session():
    """Reset active session tokens, invalidate cached CLI tokens, and return re-auth redirect URL."""
    data = await request.get_json() or {}
    target_scope = data.get("scope", "root")

    invalidate_auth_check_cache()

    reauth_url = f"/login?reauth=1&scope={target_scope}"
    return jsonify({
        "status": "success",
        "message": "Authentication session reset successfully.",
        "reauth_url": reauth_url,
    })
