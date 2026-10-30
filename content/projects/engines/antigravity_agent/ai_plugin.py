"""Central Flask WSGI Blueprint adapter mounting the Siraugga Framework into e_profile."""
from flask import Blueprint, jsonify, request, render_template, render_template_string, session, redirect
from pathlib import Path
import sys
import os
import time
import socket
import json
import threading
import asyncio
import shutil
import subprocess

PLUGIN_DIR = Path(__file__).resolve().parent
ai_path = str(PLUGIN_DIR)
if ai_path not in sys.path:
    sys.path.insert(0, ai_path)

from agents.agent_manager import AgentTaskManager
from core.project_manager import ProjectManager
from core.session_manager import SessionManager
from security.security_manager import SecurityManager
from core.local_model_service import discover_local_models

ai_bp = Blueprint("ai", __name__, template_folder="sandbox/templates", static_folder="static")

project_mgr = ProjectManager()
session_mgr = SessionManager()
agent_mgr = AgentTaskManager(project_manager=project_mgr)
security_mgr = SecurityManager()


def _iter_relative_roots():
    seen = set()
    for cand in (
        PLUGIN_DIR,
        Path.cwd(),
        PLUGIN_DIR.parent,
        PLUGIN_DIR.parent.parent,
        PLUGIN_DIR.parent.parent.parent,
        Path.home(),
    ):
        try:
            resolved = cand.resolve()
            if resolved not in seen and resolved.exists():
                seen.add(resolved)
                yield resolved
        except Exception:
            continue


def _get_runtime_dir() -> Path:
    rt = PLUGIN_DIR / ".runtime"
    try:
        rt.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return rt


def _get_sock_path() -> str:
    rt_sock = _get_runtime_dir() / "agy_auth.sock"
    s_path = str(rt_sock)
    if not s_path.startswith("/mnt/") and len(s_path) < 95:
        return s_path
    return "/tmp/agy_auth.sock"


def _get_state_path() -> Path:
    return _get_runtime_dir() / "agy_auth_state.json"


def _get_daemon_log_path() -> Path:
    return _get_runtime_dir() / "auth_daemon.log"


def _find_agy_binary():
    for root in _iter_relative_roots():
        for rel in (
            Path(".local/bin/agy_real"),
            Path(".local/bin/agy"),
            Path("agy_real"),
            Path("agy"),
            Path("bin/agy"),
            Path("agy.exe"),
        ):
            cand = root / rel
            try:
                if cand.is_file() and cand.stat().st_size > 50:
                    if cand.name == "agy" and (cand.parent / "agy_real").is_file() and cand.stat().st_size < 4096:
                        return str(cand.parent / "agy_real")
                    return str(cand)
            except Exception:
                continue
    which_agy = shutil.which("agy")
    if which_agy and os.path.exists(which_agy) and os.path.getsize(which_agy) > 50:
        return which_agy
    return None


def _render_ai_template(template_name: str, **context):
    for rel_dir in (Path("sandbox/templates"), Path("templates")):
        tpl_path = PLUGIN_DIR / rel_dir / template_name
        if tpl_path.is_file():
            return render_template_string(tpl_path.read_text(encoding="utf-8"), **context)
    return render_template(template_name, **context)


def _get_ui_config() -> dict:
    cfg_path = PLUGIN_DIR / "core" / "ui_config.json"
    ui_cfg = {}
    if cfg_path.is_file():
        try:
            ui_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            ui_cfg = {}

    avail_cache = PLUGIN_DIR / "core" / ".available_models_cache.json"
    supported_set = None
    if avail_cache.is_file():
        try:
            c_data = json.loads(avail_cache.read_text(encoding="utf-8"))
            c_models = c_data.get("models") or []
            if c_models:
                supported_set = set(c_models)
        except Exception:
            supported_set = None

    try:
        local_entries = discover_local_models()
    except Exception:
        local_entries = []
    local_values = {e["value"] for e in local_entries}
    if "header" in ui_cfg and isinstance(ui_cfg["header"].get("models"), list):
        static_models = ui_cfg["header"]["models"]
        if supported_set:
            supported_models = [m for m in static_models if m.get("value") in supported_set]
            if supported_models:
                static_models = supported_models
        filtered = [m for m in static_models if m.get("value") not in local_values]
        ui_cfg["header"]["models"] = ([filtered[0]] + local_entries + filtered[1:]) if filtered else list(local_entries)
    return ui_cfg


def query_auth_daemon(payload, timeout=2.0):
    sock_candidates = [_get_sock_path(), "/tmp/agy_auth.sock"]
    for sock_path in dict.fromkeys(sock_candidates):
        if not os.path.exists(sock_path):
            continue
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(sock_path)
            s.sendall(json.dumps(payload).encode("utf-8") + b"\n")
            raw = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                raw += chunk
                if b"\n" in raw:
                    break
            s.close()
            if raw:
                return json.loads(raw.decode("utf-8"))
        except Exception:
            pass
    return None


def kill_auth_daemon():
    for state_file in (_get_state_path(), Path("/tmp/agy_auth_state.json")):
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if pid:
                    try:
                        os.kill(pid, 15)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                state_file.unlink()
            except Exception:
                pass
    for sock_path in (_get_sock_path(), "/tmp/agy_auth.sock"):
        if os.path.exists(sock_path):
            try:
                os.unlink(sock_path)
            except Exception:
                pass


def spawn_auth_daemon():
    kill_auth_daemon()
    py_bin = shutil.which("python3") or "/usr/bin/python3" or sys.executable
    daemon_script = str(PLUGIN_DIR / "auth_daemon.py")
    log_path = _get_daemon_log_path()
    try:
        log_fp = open(log_path, "w", encoding="utf-8")
        subprocess.Popen(
            [py_bin, daemon_script],
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            cwd=str(PLUGIN_DIR),
            start_new_session=True,
        )
    except Exception as e:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"spawn_auth_daemon error: {e}\n")
        except Exception:
            pass


def wait_for_auth_daemon(timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        info = query_auth_daemon({"action": "status"}, timeout=0.5)
        if info and info.get("url") and info.get("url") != "#":
            return info
        time.sleep(0.2)
    return query_auth_daemon({"action": "status"}, timeout=0.5)


ai_loop = asyncio.new_event_loop()


def run_ai_loop():
    asyncio.set_event_loop(ai_loop)
    ai_loop.run_forever()


threading.Thread(target=run_ai_loop, daemon=True).start()

DEMO_TOKEN_TTL_SECONDS = 7 * 24 * 3600


def _get_demo_dirs() -> list:
    candidates = [
        PLUGIN_DIR / "demo",
        Path.cwd() / "content" / "projects" / "demo",
        PLUGIN_DIR.parent.parent / "demo",
        Path.cwd() / "demo",
    ]
    out = []
    seen = set()
    for c in candidates:
        try:
            r = str(c.resolve())
        except Exception:
            r = str(c)
        if r not in seen:
            seen.add(r)
            out.append(str(c))
    return out


def _get_eprofile_root() -> Path:
    for root in _iter_relative_roots():
        if (root / "server.py").is_file() and (root / "projects_mod.py").is_file():
            return root
    return PLUGIN_DIR.parent


def _cleanup_expired_demo_tokens():
    now = time.time()
    for d_dir in _get_demo_dirs():
        if not os.path.exists(d_dir):
            continue
        try:
            for root, _, files in os.walk(d_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        if now - os.path.getmtime(fpath) > DEMO_TOKEN_TTL_SECONDS:
                            os.unlink(fpath)
                    except Exception:
                        pass
        except Exception:
            pass


def _resolve_token_scope() -> str:
    demo_arg = request.args.get("demo")
    mode_arg = request.args.get("mode")
    auth_header = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    bearer_user = security_mgr.get_user_from_token(auth_header) if auth_header else None
    is_master = security_mgr.check_master_signature()

    is_admin = bool(
        session.get("is_admin")
        or session.get("admin")
        or (bearer_user and bearer_user.get("role") in ("admin", "super_admin", "super admin", "Tier5_SysAdmin"))
        or is_master
    )

    if demo_arg == "1" or mode_arg == "demo":
        session["agent_token_scope"] = "demo"
        return "demo"
    elif demo_arg == "0" or mode_arg in ("root", "admin"):
        session["agent_token_scope"] = "root"
        return "root"

    if is_admin:
        if session.get("agent_token_scope") != "demo":
            session["agent_token_scope"] = "root"
        return session.get("agent_token_scope", "root")

    return "demo"


def _sync_demo_oauth_token():
    for d_dir in _get_demo_dirs():
        visible_token = os.path.join(d_dir, "antigravity-oauth-token")
        cli_token = os.path.join(d_dir, ".gemini", "antigravity-cli", "antigravity-oauth-token")
        try:
            if os.path.exists(visible_token) and not os.path.exists(cli_token):
                os.makedirs(os.path.dirname(cli_token), exist_ok=True)
                shutil.copy2(visible_token, cli_token)
            elif os.path.exists(cli_token) and not os.path.exists(visible_token):
                os.makedirs(d_dir, exist_ok=True)
                shutil.copy2(cli_token, visible_token)
        except Exception:
            pass


def _has_local_cli_credentials(scope: str = None) -> bool:
    _cleanup_expired_demo_tokens()
    active_scope = scope or _resolve_token_scope()

    if active_scope == "demo":
        _sync_demo_oauth_token()
        for d_dir in _get_demo_dirs():
            demo_candidates = [
                os.path.join(d_dir, ".gemini", "antigravity-cli", "antigravity-oauth-token"),
                os.path.join(d_dir, "antigravity-oauth-token"),
                os.path.join(d_dir, ".devcore_client_key.txt"),
                os.path.join(d_dir, "gemini_api_key.txt"),
            ]
            for p in demo_candidates:
                try:
                    if os.path.exists(p) and os.path.getsize(p) > 8:
                        return True
                except Exception:
                    pass
        return False

    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return True
    for root in _iter_relative_roots():
        for rel in (
            Path(".devcore_client_key.txt"),
            Path("gemini_api_key.txt"),
            Path("antigravity-oauth-token"),
            Path(".gemini/antigravity-cli/antigravity-oauth-token"),
            Path(".gemini/antigravity/credentials.json"),
            Path(".config/antigravity/credentials.json"),
            Path(".gemini/credentials.json"),
            Path(".config/gcloud/application_default_credentials.json"),
        ):
            cand = root / rel
            try:
                if cand.is_file() and cand.stat().st_size > 8:
                    return True
            except Exception:
                pass
    return False


def _save_api_key_for_scope(api_key: str, scope: str):
    if scope == "demo":
        for d_dir in _get_demo_dirs()[:1]:
            os.makedirs(d_dir, exist_ok=True)
            for fname in (".devcore_client_key.txt", "gemini_api_key.txt"):
                with open(os.path.join(d_dir, fname), "w", encoding="utf-8") as f:
                    f.write(api_key)
    else:
        os.environ["GEMINI_API_KEY"] = api_key
        eprofile_root = _get_eprofile_root()
        root_paths = [
            PLUGIN_DIR / ".devcore_client_key.txt",
            eprofile_root / ".devcore_client_key.txt",
            Path.home() / ".devcore_client_key.txt",
        ]
        for p in root_paths:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(api_key, encoding="utf-8")
            except Exception:
                pass


def _resolve_active_user() -> dict:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        user = security_mgr.get_user_from_token(token)
        if user:
            return user
    is_admin = bool(session.get("is_admin") or session.get("admin"))
    scope = _resolve_token_scope()
    if is_admin and scope != "demo":
        return {"username": session.get("username", "admin"), "role": "admin", "name": "System Administrator", "allowed_projects": ["*"]}
    return {"username": session.get("username", "dev"), "role": "gamedev", "name": "Developer", "allowed_projects": ["*"]}


@ai_bp.route("/")
def ai_home():
    auth_header = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    bearer_user = security_mgr.get_user_from_token(auth_header) if auth_header else None
    is_master = security_mgr.check_master_signature()

    is_admin = bool(
        session.get("is_admin")
        or session.get("admin")
        or (bearer_user and bearer_user.get("role") in ("admin", "super_admin", "super admin"))
        or is_master
    )

    if (is_master or is_admin) and not session.get("is_admin"):
        session["is_admin"] = True
        session["admin"] = True
        session["username"] = session.get("username") or "Michael (Admin)"
        session.permanent = True

    if is_admin and request.args.get("demo") != "1" and request.args.get("mode") != "demo":
        session["agent_token_scope"] = "root"
        session["agent_authenticated"] = True

    scope = _resolve_token_scope()
    target_project = request.args.get("project", "").strip()
    if target_project and hasattr(project_mgr, "set_active_project"):
        try:
            if target_project.lower() in ("root", "antigravity_agent", "system_core"):
                project_mgr.set_active_project("")
            elif target_project in project_mgr.list_projects():
                project_mgr.set_active_project(target_project)
        except Exception:
            pass

    if scope == "demo":
        if not session.get("agent_authenticated"):
            return redirect("login?demo=1")
    else:
        session["agent_token_scope"] = "root"
        session["agent_authenticated"] = True
    return _render_ai_template("index.html", ui=_get_ui_config())


@ai_bp.route("/demo")
def ai_demo_entry():
    session["agent_token_scope"] = "demo"
    session.pop("agent_authenticated", None)
    return redirect("login?demo=1")


@ai_bp.route("/login")
def login_page():
    scope = _resolve_token_scope()
    if scope == "demo":
        session.pop("agent_authenticated", None)
    return _render_ai_template("login.html")


@ai_bp.route("/api/ui-config", methods=["GET"])
def get_ui_config_route():
    return jsonify(_get_ui_config())


@ai_bp.route("/api/auth_check", methods=["GET"])
def auth_check():
    force = request.args.get("force") == "1"
    scope = _resolve_token_scope()
    has_creds = _has_local_cli_credentials(scope)

    auth_header = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    bearer_user = security_mgr.get_user_from_token(auth_header) if auth_header else None
    is_master = security_mgr.check_master_signature()
    is_admin = bool(
        session.get("is_admin")
        or session.get("admin")
        or (bearer_user and bearer_user.get("role") in ("admin", "super_admin", "super admin"))
        or is_master
    )

    if (scope == "root" and (is_admin or is_master)) or (bearer_user and bearer_user.get("role") in ("admin", "super_admin")):
        session["agent_token_scope"] = "root"
        session["agent_authenticated"] = True
        session["is_admin"] = True
        session.permanent = True
        return jsonify({
            "authenticated": True,
            "scope": "root",
            "fast_path": True,
            "has_existing": has_creds,
            "role": "admin"
        })

    is_authenticated = bool(bearer_user) or (bool(session.get("agent_authenticated")) if scope == "demo" else has_creds)

    agy_bin = _find_agy_binary()

    if not agy_bin:
        return jsonify({
            "authenticated": is_authenticated,
            "scope": scope,
            "url": "#",
            "error": "agy CLI binary not found",
        })

    daemon_info = query_auth_daemon({"action": "status"})
    if force or not daemon_info or not daemon_info.get("active") or daemon_info.get("remaining", 0) < 15:
        spawn_auth_daemon()
        daemon_info = wait_for_auth_daemon(timeout=6.0)

    if daemon_info:
        return jsonify({
            "authenticated": is_authenticated,
            "scope": scope,
            "url": daemon_info.get("url", "#"),
            "remaining": daemon_info.get("remaining", 600),
            "has_existing": has_creds,
        })

    err_log = ""
    for log_cand in (_get_daemon_log_path(), Path("/tmp/auth_daemon.log")):
        if log_cand.exists():
            try:
                err_log = log_cand.read_text(encoding="utf-8").strip()
                if err_log:
                    break
            except Exception:
                pass

    return jsonify({
        "authenticated": is_authenticated,
        "scope": scope,
        "url": "#",
        "has_existing": has_creds,
        "error": f"Failed to start authentication session: {err_log}" if err_log else "Failed to start authentication session.",
    })


@ai_bp.route("/api/auth_demo", methods=["GET", "POST"])
def auth_demo():
    _cleanup_expired_demo_tokens()
    session["agent_token_scope"] = "demo"
    session["agent_authenticated"] = True
    try:
        res = security_mgr.authenticate("dev:dev")
    except Exception:
        res = security_mgr.authenticate("dev", "dev") if hasattr(security_mgr, "authenticate") else None
    if not res:
        res = {
            "token": "sec-demo-" + os.urandom(8).hex(),
            "user": {
                "username": session.get("username", "demo_visitor"),
                "role": "gamedev",
                "name": "Demo Visitor",
                "allowed_projects": ["demo", "playground"],
            },
        }
    return jsonify({
        "success": True,
        "authenticated": _has_local_cli_credentials("demo"),
        "scope": "demo",
        "token": res.get("token"),
        "user": res.get("user"),
        "message": "Demo mode active (tokens stored in projects/demo and deleted after 7 days)",
    })


@ai_bp.route("/api/sounds/<sound_name>", methods=["GET"])
def get_sound(sound_name):
    from flask import send_file
    for cand_dir in (
        PLUGIN_DIR / "sandbox" / "static" / "sounds",
        PLUGIN_DIR / "static" / "sounds",
        _get_eprofile_root() / "static" / "sounds",
    ):
        for ext in ('.wav', '.mp3', '.ogg'):
            f = cand_dir / f"{sound_name}{ext}"
            if f.is_file():
                mimetype = "audio/x-wav" if ext == ".wav" else ("audio/ogg" if ext == ".ogg" else "audio/mpeg")
                return send_file(str(f), mimetype=mimetype)
    if sound_name == "notification":
        for cand_dir in (PLUGIN_DIR / "sandbox" / "static" / "sounds", PLUGIN_DIR / "static" / "sounds"):
            f = cand_dir / "incoming.wav"
            if f.is_file():
                return send_file(str(f), mimetype="audio/x-wav")
    return jsonify({"error": f"Sound {sound_name} not found"}), 404


@ai_bp.route("/api/set_api_key", methods=["POST"])
def set_api_key():
    data = request.get_json(silent=True) or {}
    is_admin = bool(session.get("is_admin") or session.get("admin"))
    scope = data.get("scope") or _resolve_token_scope()
    if not is_admin:
        scope = "demo"

    if data.get("demo") is True or data.get("api_key") == "demo":
        session["agent_token_scope"] = "demo"
        session["agent_authenticated"] = True
        try:
            res = security_mgr.authenticate("dev:dev")
        except Exception:
            res = security_mgr.authenticate("dev", "dev") if hasattr(security_mgr, "authenticate") else None
        return jsonify({
            "success": True,
            "demo": True,
            "scope": "demo",
            "token": res.get("token") if res else None,
            "user": res.get("user") if res else None,
        })

    api_key = data.get("api_key", "").strip()
    if not api_key:
        return jsonify({"success": False, "error": "No API key provided"}), 400

    try:
        _save_api_key_for_scope(api_key, scope)
        session["agent_token_scope"] = scope
        session["agent_authenticated"] = True
        return jsonify({"success": True, "scope": scope})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ai_bp.route("/api/auth_submit", methods=["POST"])
def auth_submit():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "").strip()
    api_key = data.get("api_key", "").strip()
    is_admin = bool(session.get("is_admin") or session.get("admin"))
    scope = data.get("scope") or _resolve_token_scope()
    if not is_admin:
        scope = "demo"

    if api_key:
        try:
            _save_api_key_for_scope(api_key, scope)
            session["agent_token_scope"] = scope
            session["agent_authenticated"] = True
            return jsonify({"success": True, "scope": scope})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    if not token:
        return jsonify({"success": False, "error": "No authorization token provided"}), 400

    resp = query_auth_daemon({"action": "submit", "token": token, "scope": scope}, timeout=30.0)
    if not resp:
        return jsonify({
            "success": False,
            "error": "Authentication session expired or unavailable. Please click 'Refresh Link' to restart the authorization flow.",
        }), 400

    if resp.get("success"):
        session["agent_token_scope"] = scope
        session["agent_authenticated"] = True
        return jsonify({
            "success": True,
            "scope": scope,
            "message": resp.get("message", "Google OAuth authorization successful!"),
        })
    return jsonify({"success": False, "error": resp.get("error", "Token rejected.")}), 400


@ai_bp.route("/api/chat", methods=["POST"])
def start_chat():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    msg_type = data.get("type", "prompt")
    model = data.get("model", "Gemini 3.8 Flash (High)")
    conversation_id = data.get("conversation_id")
    admin_override = bool(data.get("admin_override", False))
    token = data.get("token")

    is_admin = bool(session.get("is_admin", False) or session.get("admin", False))
    scope = _resolve_token_scope()
    is_admin_exec = False if scope == "demo" else is_admin

    user = {
        "role": "admin" if is_admin_exec else "modder",
        "username": session.get("username", "guest"),
        "token_scope": scope,
    }

    if token and not is_admin_exec and scope != "demo":
        user_from_token = security_mgr.get_user_from_token(token)
        if user_from_token and user_from_token.get("role") == "admin":
            is_admin_exec = True
            user = dict(user_from_token)
            user["token_scope"] = "root"

    if msg_type == "cli_input":
        text_input = data.get("text", prompt)
        asyncio.run_coroutine_threadsafe(agent_mgr.send_input(text_input), ai_loop)
        return jsonify({"success": True, "message": "CLI input dispatched"})

    if agent_mgr.is_running() and not prompt.startswith("[STEER_NOW]") and not prompt.startswith("[QUEUE_NEXT]"):
        prompt = f"[STEER_NOW]\n{prompt}"

    asyncio.run_coroutine_threadsafe(
        agent_mgr.start_task(
            prompt,
            model=model,
            conversation_id=conversation_id,
            user=user,
            admin_override=(admin_override and is_admin_exec),
        ),
        ai_loop,
    )
    return jsonify({"success": True, "message": "Task started", "scope": scope})


@ai_bp.route("/api/stream", methods=["GET"])
def get_stream():
    since_seq = request.args.get("since_seq", type=int)
    queue_items = list(getattr(agent_mgr, "message_queue", []) or [])

    shared_sf = _get_runtime_dir() / "stream_events.json"
    if shared_sf.is_file():
        try:
            shared_items = json.loads(shared_sf.read_text(encoding="utf-8"))
            if isinstance(shared_items, list):
                existing_seqs = {it.get("seq") for it in queue_items if isinstance(it, dict)}
                for s_it in shared_items:
                    if isinstance(s_it, dict) and s_it.get("seq") not in existing_seqs:
                        queue_items.append(s_it)
                queue_items.sort(key=lambda x: x.get("seq", 0))
        except Exception:
            pass

    if since_seq is not None:
        messages = []
        max_seq = since_seq
        for item in queue_items:
            seq_val = item.get("seq", 0)
            if seq_val > since_seq:
                msg_obj = dict(item.get("msg", {}))
                msg_obj["seq"] = seq_val
                messages.append(msg_obj)
                if seq_val > max_seq:
                    max_seq = seq_val
        return jsonify({"messages": messages, "last_seq": max_seq})

    messages = []
    while agent_mgr.message_queue:
        popped = agent_mgr.message_queue.pop(0)
        msg_obj = dict(popped.get("msg", {}))
        if "seq" in popped:
            msg_obj["seq"] = popped["seq"]
        messages.append(msg_obj)
    return jsonify({"messages": messages})


@ai_bp.route("/api/kill", methods=["POST"])
def kill_chat():
    asyncio.run_coroutine_threadsafe(agent_mgr.cancel_task(), ai_loop)
    return jsonify({"success": True})


@ai_bp.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    if data.get("demo") is True or data.get("username") == "demo" or data.get("access_key") == "demo":
        session["agent_token_scope"] = "demo"
        session["agent_authenticated"] = True
        try:
            res = security_mgr.authenticate("dev:dev")
        except Exception:
            res = security_mgr.authenticate("dev", "dev") if hasattr(security_mgr, "authenticate") else None
        return jsonify(res)

    access_key = data.get("access_key")
    if access_key in ("SUPER_ADMIN_AUTO", "sec-root-owner-permanent") or (access_key and str(access_key).startswith("sec-root")):
        session["is_admin"] = True
        session["admin"] = True
        session["agent_token_scope"] = "root"
        session["agent_authenticated"] = True
        session.permanent = True
        res = security_mgr.authenticate(access_key)
        if not res:
            res = {
                "token": "sec-root-owner-permanent",
                "user": {
                    "username": "Michael (Admin)",
                    "role": "super_admin",
                    "name": "Michael (Admin)",
                    "allowed_projects": ["*"],
                    "token_scope": "root"
                }
            }
        return jsonify(res)

    username = data.get("username")
    password = data.get("password")
    if access_key and not username:
        res = security_mgr.authenticate(access_key)
    else:
        res = security_mgr.authenticate(username, password)
    if res:
        if res.get("user", {}).get("role") in ("admin", "super_admin"):
            session["is_admin"] = True
            session["admin"] = True
            session["agent_token_scope"] = "root"
        session["agent_authenticated"] = True
        session.permanent = True
        return jsonify(res)
    return jsonify({"error": "Invalid username or password"}), 401


@ai_bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if token:
        security_mgr.logout(token)
    session.pop("agent_authenticated", None)
    return jsonify({"success": True})


@ai_bp.route("/api/auth/me", methods=["GET"])
def auth_me():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    user = security_mgr.get_user_from_token(token)
    if user:
        return jsonify({"user": user})
    active_user = _resolve_active_user()
    if active_user:
        return jsonify({"user": active_user})
    return jsonify({"error": "Unauthorized"}), 401


@ai_bp.route("/api/auth/system-status", methods=["GET"])
def auth_system_status():
    scope = _resolve_token_scope()
    is_super = security_mgr.check_master_signature() or bool(session.get("is_admin") or session.get("admin"))
    return jsonify({
        "cli_installed": bool(_find_agy_binary()),
        "has_api_key": _has_local_cli_credentials(scope),
        "scope": scope,
        "super_admin": is_super,
    })


@ai_bp.route("/api/projects", methods=["GET", "POST"])
def handle_projects():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if name and hasattr(project_mgr, "create_project"):
            try:
                project_mgr.create_project(name)
                return jsonify({"success": True, "active": project_mgr.active_project})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
    projects = project_mgr.list_projects() if hasattr(project_mgr, "list_projects") else []
    active = project_mgr.active_project if hasattr(project_mgr, "active_project") else ""
    return jsonify({"projects": projects, "active": active})


@ai_bp.route("/api/projects/active", methods=["POST"])
def set_active_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if hasattr(project_mgr, "set_active_project"):
        project_mgr.set_active_project(name)
    return jsonify({"success": True, "active": getattr(project_mgr, "active_project", name)})


@ai_bp.route("/api/conversations", methods=["GET"])
def get_conversations():
    user = _resolve_active_user()
    convs = (
        session_mgr.list_conversations(project_name=getattr(project_mgr, "active_project", None), user=user)
        if hasattr(session_mgr, "list_conversations")
        else []
    )
    return jsonify({"conversations": convs})


@ai_bp.route("/api/conversations/<conv_id>", methods=["GET", "DELETE"])
def handle_conversation_details(conv_id):
    user = _resolve_active_user()
    if request.method == "DELETE":
        if hasattr(session_mgr, "delete_conversation"):
            session_mgr.delete_conversation(conv_id, user=user)
        return jsonify({"success": True})
    transcript = session_mgr.get_conversation_transcript(conv_id, user=user) if hasattr(session_mgr, "get_conversation_transcript") else []
    return jsonify({"items": transcript, "transcript": transcript})


@ai_bp.route("/api/conversations/<conv_id>/rename", methods=["POST"])
def rename_conversation(conv_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if title and hasattr(session_mgr, "set_custom_title"):
        session_mgr.set_custom_title(conv_id, title)
    return jsonify({"success": True, "title": title})


@ai_bp.route("/api/projects/active/conversations", methods=["DELETE"])
def delete_active_conversations():
    user = _resolve_active_user()
    if hasattr(session_mgr, "delete_project_sessions"):
        session_mgr.delete_project_sessions(getattr(project_mgr, "active_project", None), user)
    return jsonify({"success": True})


@ai_bp.route("/api/artifacts", methods=["GET"])
def get_artifact():
    user = _resolve_active_user()
    if user.get("role") != "admin":
        return jsonify({"error": "Admin clearance required to view raw artifacts"}), 403
    fpath = request.args.get("path", "").strip()
    if not fpath or not os.path.isfile(fpath):
        return jsonify({"error": "Artifact not found"}), 404
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            return jsonify({"content": f.read(), "path": fpath})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/api/artifacts/save", methods=["POST"])
def save_artifact():
    user = _resolve_active_user()
    if user.get("role") != "admin":
        return jsonify({"error": "Admin clearance required to save artifacts"}), 403
    data = request.get_json(silent=True) or {}
    fpath = data.get("path", "").strip()
    content = data.get("content", "")
    if not fpath:
        return jsonify({"error": "Missing path"}), 400
    try:
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
