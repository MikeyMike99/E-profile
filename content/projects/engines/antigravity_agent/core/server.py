import asyncio
import importlib

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from security import central_logger
central_logger.init_central_logging()
import json
import os
import time
import sys
import httpx

from quart import Quart, websocket, request, jsonify, render_template_string

from core import session_manager as sm
from core import project_manager as pm
from agents import agent_manager as am
from security import security_manager as sec_m

app = Quart(__name__, static_folder=None)

from core.routes.auth import auth_bp
from core.routes.projects import projects_bp
from core.routes.files import files_bp
from core.routes.system import system_bp

app.register_blueprint(auth_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(files_bp)
app.register_blueprint(system_bp)

from security import security_headers
security_headers.init_security_headers(app)

project_mgr = pm.ProjectManager()
session_mgr = sm.SessionManager()
agent_mgr = am.AgentTaskManager(project_manager=project_mgr)
security_mgr = sec_m.SecurityManager()
app.security_mgr = security_mgr
app.project_mgr = project_mgr
app.session_mgr = session_mgr
app.agent_mgr = agent_mgr

async def execute_hot_patch_sequence(manual_trigger=False):
    """Timer sequence for safe hot-patching with syntax validation and automated rollback."""
    from core.routes.system import execute_hot_patch_sequence as _run_hot_patch
    await _run_hot_patch(app_obj=app, manual_trigger=manual_trigger)

async def auto_patch_daemon():
    """Runs continuously in the background to automatically patch exploits."""
    while True:
        await asyncio.sleep(1800)
        await execute_hot_patch_sequence()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def raugus_map_watcher_daemon():
    """
    Background watcher that monitors workspace directories (playground, docs)
    and updates raugus_map.json incrementally if modified out-of-band.
    """
    import os
    import time
    devcore_root = os.path.dirname(BASE_DIR)
    watched_dirs = [
        os.path.join(devcore_root, 'playground'),
        os.path.join(devcore_root, 'docs'),
    ]
    seen_mtimes = {}
    while True:
        try:
            await asyncio.sleep(4)
            for wdir in watched_dirs:
                if not os.path.exists(wdir):
                    continue
                for root, _, files in os.walk(wdir):
                    for fname in files:
                        if fname.startswith('.') or fname.endswith(('.pyc', '.tmp', '.log')):
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            mtime = os.stat(fpath).st_mtime
                            if fpath not in seen_mtimes:
                                seen_mtimes[fpath] = mtime
                            elif seen_mtimes[fpath] != mtime:
                                seen_mtimes[fpath] = mtime
                                try:
                                    from security.raugus_sync import sync_path
                                    sync_path(fpath, root_dir=devcore_root)
                                except Exception:
                                    pass
                        except Exception:
                            continue
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(4)

@app.before_serving
async def start_background_tasks():
    app.add_background_task(auto_patch_daemon)
    app.add_background_task(raugus_map_watcher_daemon)

def get_live_override_path(rel_path):
    """
    LIVE OVERRIDE ARCHITECTURE (OTA Drop-in Updates)
    Checks if a loose file exists next to the .exe (in CWD) before falling back to the compiled bundle.
    This allows updating the UI/Plugins without downloading a new .exe!
    """
    import os
    import sys
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
    
    live_path = os.path.join(exe_dir, rel_path)
    if os.path.exists(live_path):
        return live_path
        
    cwd_path = os.path.join(os.getcwd(), rel_path)
    if os.path.exists(cwd_path):
        return cwd_path
        
    return os.path.join(os.path.dirname(BASE_DIR), rel_path)

def read_asset(rel_path):
    from security.vfs import vfs
    vfs.load()
    live_path = get_live_override_path(rel_path)
    if os.path.exists(live_path):
        return open(live_path, 'rb').read()
    data = vfs.read(rel_path)
    if data:
        return data
    return None

@app.route('/static/<path:filename>')
async def custom_static(filename):
    import mimetypes
    data = read_asset(f"sandbox/static/{filename}")
    if data:
        mime_type, _ = mimetypes.guess_type(filename)
        return data, 200, {'Content-Type': mime_type or 'application/octet-stream'}
    return "Not Found", 404

TEMPLATE_FILE = get_live_override_path("sandbox/templates/index.html")
UI_CONFIG_FILE = get_live_override_path("core/ui_config.json")

CACHED_MODELS = None

async def fetch_dynamic_models(force_cli: bool = False):
    global CACHED_MODELS
    if CACHED_MODELS is not None and not force_cli:
        return CACHED_MODELS

    try:
        from core.local_model_service import discover_local_models
        local_entries = discover_local_models()
    except Exception:
        local_entries = [{"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"}]
    local_values = {e["value"] for e in local_entries}

    if not force_cli:
        try:
            ui_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_config.json")
            if os.path.exists(ui_config_path):
                with open(ui_config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                static_models = cfg.get("header", {}).get("models")
                if isinstance(static_models, list) and static_models:
                    filtered = [m for m in static_models if m.get("value") not in local_values]
                    models_list = ([filtered[0]] + local_entries + filtered[1:]) if filtered else list(local_entries)
                    CACHED_MODELS = models_list
                    return CACHED_MODELS
        except Exception:
            pass

    local_agy = os.path.expanduser("~/.local/bin/agy")
    if not os.path.exists(local_agy):
        return None
        
    try:
        import sys
        if sys.platform == "win32":
            cmd = ["wsl.exe", "-e", "bash", "-c", "~/.local/bin/agy --model invalid --print 'test'"]
        else:
            cmd = [local_agy, "--model", "invalid", "--print", "test"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        out_str = stdout.decode("utf-8", errors="ignore")
        if "Available models:" in out_str:
            models_section = out_str.split("Available models:")[1]
            lines = models_section.strip().split("\n")
            fetched_models = []
            for line in lines:
                val = line.strip()
                if val and not val.startswith("Set-PSReadLineOption") and not val.startswith("At C:") and not val.startswith("+") and not val.startswith("CategoryInfo") and not val.startswith("FullyQualifiedErrorId") and not val.startswith("~"):
                    fetched_models.append({"value": val, "text": val})
            if fetched_models:
                filtered = [m for m in fetched_models if m.get("value") not in local_values]
                fetched_models = ([filtered[0]] + local_entries + filtered[1:]) if filtered else list(local_entries)
                CACHED_MODELS = fetched_models
                return fetched_models
    except Exception:
        pass
    return None

@app.route('/')
async def index():
    """Dynamically serves and renders the template using Jinja2 variables."""
    import json
    template_bytes = read_asset("sandbox/templates/index.html")
    if not template_bytes:
        return "Template not found: sandbox/templates/index.html", 404
    content = template_bytes.decode('utf-8')
    
    ui_bytes = read_asset("core/ui_config.json")
    ui_strings = json.loads(ui_bytes.decode('utf-8')) if ui_bytes else {}
    
    dyn_models = await fetch_dynamic_models()
    if dyn_models:
        if "header" not in ui_strings:
            ui_strings["header"] = {}
        ui_strings["header"]["models"] = dyn_models
    
    rendered_content = await render_template_string(content, ui=ui_strings)
    return rendered_content, 200, {'Content-Type': 'text/html; charset=utf-8'}

GLOBAL_AUTH_PROC = None

@app.route('/plugin/media')
async def plugin_media():
    """Dynamically renders the video application plugin."""
    import json
    video_id = request.args.get('v', 'jNQXAC9IVRw')
    video_title = request.args.get('title', 'Accessible Video Player')
    
    template_bytes = read_asset("sandbox/templates/video_application.html")
    if not template_bytes:
        return "Media template not found", 404
    content = template_bytes.decode('utf-8')
    
    ui_bytes = read_asset("core/ui_config.json")
    ui_strings = json.loads(ui_bytes.decode('utf-8')) if ui_bytes else {}
    
    rendered = await render_template_string(content, ui=ui_strings, video_id=video_id, video_title=video_title)
    return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/plugin/security')
async def plugin_security():
    """Dynamically renders the security dashboard plugin."""
    import json
    template_bytes = read_asset("sandbox/templates/security_dashboard.html")
    if not template_bytes:
        return "Security template not found", 404
    content = template_bytes.decode('utf-8')
    
    ui_bytes = read_asset("core/ui_config.json")
    ui_strings = json.loads(ui_bytes.decode('utf-8')) if ui_bytes else {}
    
    rendered = await render_template_string(content, ui=ui_strings)
    return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/plugin/exam')
async def plugin_exam():
    """Dynamically renders the exam generator plugin."""
    import json
    quiz_file = request.args.get('quiz', 'quiz_temp.json')
    exam_title = request.args.get('title', 'Siraugga Exam')
    
    template_bytes = read_asset("sandbox/templates/exam_application.html")
    if not template_bytes:
        return "Exam template not found", 404
    content = template_bytes.decode('utf-8')
    
    ui_bytes = read_asset("core/ui_config.json")
    ui_strings = json.loads(ui_bytes.decode('utf-8')) if ui_bytes else {}
    
    rendered = await render_template_string(content, ui=ui_strings, quiz_file=quiz_file, exam_title=exam_title)
    return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/plugin/exam_builder')
async def plugin_exam_builder():
    """Serves the visual Exam Builder Dashboard."""
    template_bytes = read_asset("sandbox/templates/exam_builder.html")
    if not template_bytes:
        return "Exam builder template not found", 404
    content = template_bytes.decode('utf-8')
    rendered = await render_template_string(content)
    return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/plugin/audits')
async def plugin_audits():
    """Serves the System Audits Review Hub."""
    template_bytes = read_asset("sandbox/templates/audits.html")
    if not template_bytes:
        template_bytes = read_asset("templates/audits.html")
    if not template_bytes:
        return "Audits template not found", 404
    content = template_bytes.decode('utf-8')
    rendered = await render_template_string(content)
    return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/api/exam/content', methods=['GET', 'POST'])
async def api_exam_content():
    content_dir = os.path.join(os.getcwd(), 'plugins', 'exam_application', 'content')
    os.makedirs(content_dir, exist_ok=True)
    if request.method == 'GET':
        try:
            files = os.listdir(content_dir)
            files = [f for f in files if os.path.isfile(os.path.join(content_dir, f))]
            return jsonify({"files": files})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    if request.method == 'POST':
        files = await request.files
        uploaded = []
        for name, file in files.items():
            path = os.path.join(content_dir, file.filename)
            await file.save(path)
            uploaded.append(file.filename)
        return jsonify({"message": "Files uploaded successfully", "files": uploaded})

@app.route('/api/artifacts', methods=['GET'])
async def get_artifact():
    import sys
    import subprocess
    
    path = request.args.get('path', '')
    if path.startswith('file://'):
        path = path[7:]

    try:
        from security.raugus_resolver import resolver
        if resolver.is_sensitive_path(path):
            return jsonify({"error": "Raugus Sensitive Vault: Direct HTTP read of sensitive files is blocked."}), 403
    except Exception:
        pass
        
    if sys.platform == "win32" and path.startswith("/"):
        try:
            result = subprocess.run(["wsl.exe", "-e", "cat", path], capture_output=True, text=True)
            if result.returncode == 0:
                return jsonify({"content": result.stdout})
            else:
                return jsonify({"error": f"WSL Artifact not found: {result.stderr}"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not os.path.exists(path):
        return jsonify({"error": "Artifact not found"}), 404
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        

@app.route('/api/artifacts/save', methods=['POST'])
async def save_artifacts():
    import sys
    import subprocess
    import shlex
    
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    user = security_mgr.get_user_from_token(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = await request.get_json()
    path = data.get('path', '')
    content = data.get('content', '')
    append_mode = data.get('append', False)
    
    if path.startswith('file://'):
        path = path[7:]

    try:
        from security.raugus_resolver import resolver
        if resolver.is_sensitive_path(path):
            return jsonify({"error": "Raugus Sensitive Vault: Direct HTTP write to sensitive files is blocked."}), 403
    except Exception:
        pass
        
    if not path.startswith("/home/") and not path.startswith("/mnt/"):
        return jsonify({"error": "Path traversal blocked"}), 403
        
    safe_path = shlex.quote(path)
    
    if sys.platform == "win32" and path.startswith("/"):
        import tempfile
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".md")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if append_mode:
                cmd = f"cat $(wslpath -a '{tmp_path}') >> {safe_path}"
            else:
                cmd = f"cp $(wslpath -a '{tmp_path}') {safe_path}"
                
            process = subprocess.Popen(
                ["wsl.exe", "-e", "bash", "-c", cmd],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()
            
            try:
                os.remove(tmp_path)
            except Exception:
                pass
                
            if process.returncode == 0:
                return jsonify({"success": True})
            else:
                return jsonify({"error": f"WSL Artifact write failed: {stderr}"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            mode = "a" if append_mode else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/prompt/massive', methods=['POST'])
async def handle_massive_prompt():
    auth_hdr = request.headers.get('Authorization', '')
    token = auth_hdr.replace('Bearer ', '').strip()
    user = security_mgr.get_user_from_token(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = await request.get_json()
    raw_prompt = data.get("prompt", "")
    conv_id = data.get("conv_id", "")
    
    if not raw_prompt or not conv_id:
        return jsonify({"error": "Missing prompt or conv_id"}), 400
        
    try:
        import os
        try:
            from local_security import LocalSecurity
            local_sec = LocalSecurity()
            scrubbed_prompt = local_sec.scrub_text(raw_prompt)
        except ImportError:
            print("Warning: presidio-analyzer missing. Skipping PII scrubbing.")
            scrubbed_prompt = raw_prompt
        
        upload_dir = os.path.join(".agents", "massive_prompts")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{conv_id}.txt")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(scrubbed_prompt)
            
        return jsonify({"success": True, "file_path": file_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.websocket('/ws')
async def ws_endpoint():
    ws = websocket._get_current_object()
    client_queue = asyncio.Queue()
    await agent_mgr.register_client(client_queue)
    
    async def sender():
        try:
            while True:
                msg = await client_queue.get()
                if msg is None:
                    break
                await ws.send(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"WebSocket Sender Error: {e}")

    sender_task = asyncio.create_task(sender())

    try:
        while True:
            raw_msg = await ws.receive()
            if not raw_msg:
                continue

            prompt = None
            model = "gemini-3.8-flash-high"
            conversation_id = None
            try:
                data = json.loads(raw_msg)
                msg_type = data.get("type", "prompt")
                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong", "time": time.time()}))
                    continue
                elif msg_type == "sync":
                    last_seq = data.get("last_seq", 0)
                    await agent_mgr.sync_client(client_queue, last_seq)
                    continue
                elif msg_type == "cancel":
                    await agent_mgr.cancel_task()
                    continue
                elif msg_type == "auth_token":
                    token = data.get("token", "")
                    user = security_mgr.get_user_from_token(token)
                    if user:
                        await agent_mgr.authenticate_client(client_queue, user.get("username"))
                    await agent_mgr.submit_auth_token(token)
                    continue
                elif msg_type == "save_artifact":
                    path = data.get("path", "")
                    content = data.get("content", "")
                    if path.startswith('file://'):
                        path = path[7:]
                        
                    import subprocess
                    if sys.platform == "win32" and path.startswith("/"):
                        try:
                            temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wsl_temp_save.md")
                            with open(temp_path, "w", encoding="utf-8") as tf:
                                tf.write(content)
                            
                            wsl_temp = subprocess.run(["wsl.exe", "wslpath", "-a", temp_path], capture_output=True, text=True, creationflags=0x08000000).stdout.strip()
                            subprocess.run(["wsl.exe", "bash", "-c", f"cp '{wsl_temp}' '{path}'"], creationflags=0x08000000)
                            
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        except Exception as e:
                            print(f"WSL save error: {e}")
                    else:
                        try:
                            with open(path, 'w', encoding='utf-8') as f:
                                f.write(content)
                        except Exception:
                            pass
                    continue
                elif msg_type == "exam_ready":
                    await agent_mgr.broadcast(data)
                    continue
                elif msg_type == "cli_input":
                    cli_in = data.get("input", "")
                    await agent_mgr.send_input(cli_in)
                    continue
                elif msg_type == "clear_queue":
                    if hasattr(agent_mgr, "clear_queue"):
                        await agent_mgr.clear_queue()
                    continue
                elif msg_type == "promote_queue":
                    if hasattr(agent_mgr, "promote_queued_to_steer"):
                        await agent_mgr.promote_queued_to_steer()
                    continue
                elif msg_type == "ack":
                    seq = data.get("seq")
                    if seq is not None:
                        agent_mgr.handle_ack(seq)
                    continue
                elif msg_type in ("prompt", "steer", "queue_prompt"):
                    prompt = data.get("prompt", "").strip()
                    model = data.get("model", "gemini-3.8-flash-high")
                    conversation_id = data.get("conversation_id")
                    token = data.get("token")
                    req_mode = data.get("mode") or (
                        "steer" if msg_type == "steer" else ("queue" if msg_type == "queue_prompt" else "normal")
                    )
                    
                    if token:
                        user = security_mgr.get_user_from_token(token)
                        if not user:
                            if security_mgr.check_master_signature():
                                user = {
                                    "username": "Michael (Admin)",
                                    "role": "super_admin",
                                    "name": "Michael (Admin)",
                                    "allowed_projects": ["*"],
                                    "token_scope": "root"
                                }
                            else:
                                await websocket.send(json.dumps({
                                    "type": "system",
                                    "level": "error",
                                    "message": "Your session has expired. Please refresh the page and log in again."
                                }))
                                continue
                        await agent_mgr.authenticate_client(client_queue, user.get("username"))
                    else:
                        user = security_mgr.get_user_from_token(None)
                    
                    is_role_admin = bool(user and user.get("role") in ("admin", "super_admin", "super admin", "Tier5_SysAdmin"))
                    admin_override = is_role_admin or (os.environ.get("ADMIN_OVERRIDE", "false").lower() == "true")
            except (json.JSONDecodeError, AttributeError):
                prompt = str(raw_msg).strip()
                user = None
                req_mode = "normal"
                admin_override = os.environ.get("ADMIN_OVERRIDE", "false").lower() == "true"

            if prompt:
                is_admin = bool(user and user.get("role") in ("admin", "super_admin", "super admin", "Tier5_SysAdmin")) or (os.environ.get("ADMIN_OVERRIDE", "false").lower() == "true")
                if not is_admin:
                    try:
                        from local_security import LocalSecurity
                        ls = LocalSecurity()
                        security_status = ls.analyze_intent(prompt)
                        if security_status == "ATTACK":
                            print("[Semantic Firewall] Dropping malicious prompt.")
                            await ws.send(json.dumps({
                                "type": "agent_article",
                                "markdown": "> [!CAUTION] Semantic Firewall Active\n> Malicious intent or prompt injection detected. Your request has been blocked and dropped."
                            }))
                            continue
                    except ImportError:
                        pass
                    except Exception as e:
                        print(f"[Security Firewall] Error parsing intent: {e}")

                if locals().get("req_mode") == "queue" and hasattr(agent_mgr, "queue_prompt"):
                    clean_q = prompt[len("[QUEUE_NEXT]\n"):].strip() if prompt.startswith("[QUEUE_NEXT]\n") else prompt
                    await agent_mgr.queue_prompt(clean_q, model=model, conversation_id=conversation_id, user=user, admin_override=admin_override)
                elif locals().get("req_mode") == "steer" and hasattr(agent_mgr, "steer_task"):
                    clean_s = prompt[len("[STEER_NOW]\n"):].strip() if prompt.startswith("[STEER_NOW]\n") else prompt
                    await agent_mgr.steer_task(clean_s, model=model, conversation_id=conversation_id, user=user, admin_override=admin_override)
                else:
                    await agent_mgr.start_task(prompt, model=model, conversation_id=conversation_id, user=user, admin_override=admin_override)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            with open("ws_error.log", "a") as f:
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        print(f"WebSocket Error: {e}")
    finally:
        sender_task.cancel()
        await agent_mgr.unregister_client(client_queue)

@app.route('/api/sounds/<sound_name>')
async def play_sound(sound_name):
    from quart import send_file
    
    sounds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sandbox", "static", "sounds")
    
    for ext in ['.wav', '.mp3', '.ogg']:
        file_path = os.path.join(sounds_dir, f"{sound_name}{ext}")
        if os.path.exists(file_path):
            return await send_file(file_path)
    
    return jsonify({"error": f"No custom {sound_name} audio file found in {sounds_dir}"}), 404

async def trigger_dast_scan_internal():
    """Triggers the Red Team ZAP Docker scan natively."""
    await agent_mgr.broadcast({
        "type": "system",
        "level": "warning",
        "message": "🔴 ACTIVE SPEAR: Initiating internal Red Team DAST strike..."
    })
    
    scanner_path = r"C:\Users\michael\Documents\scanners\scanner.py"
    cmd = ["python3", scanner_path, "--dast", "http://host.docker.internal:5000"]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=r"C:\Users\michael\Documents\scanners"
        )
    except Exception as e:
        print(f"[DAST] Failed to launch Red Team engine: {e}")

async def auto_red_team_daemon():
    """Biological clock: Wakes up every 12 hours to strike the server."""
    while True:
        await asyncio.sleep(43200)
        await trigger_dast_scan_internal()

import signal

def force_shutdown(sig, frame):
    print("\n[Antigravity] Force quitting server (bypassing asyncio graceful shutdown)...")
    os._exit(0)

@app.route('/api/plugin/tts', methods=['POST'])
async def plugin_tts():
    try:
        data = await request.get_json()
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "No text provided"}), 400
            
        import sys
        import os
        sys.path.append(os.path.abspath("plugins"))
        import tts_proxy
        from quart import Response
        
        ui_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_config.json")
        
        audio_content, status_code = tts_proxy.generate_audio(text, ui_config_path)
        
        if status_code == 200:
            return Response(audio_content, mimetype="audio/mpeg")
        else:
            return jsonify(audio_content), status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/proxy/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
async def proxy_gemini(subpath):
    """
    Intercepts the Agent's API calls, replaces the dummy token with the true root 
    vault key, and forwards it to Google. The Agent never sees the real key.
    """
    real_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not real_api_key:
        client_key_path = os.path.expanduser("~/.devcore_client_key.txt")
        if os.path.exists(client_key_path):
            try:
                with open(client_key_path, "r", encoding="utf-8") as f:
                    real_api_key = f.read().strip()
            except Exception:
                pass
                
    if not real_api_key:
        return jsonify({"error": "No root billing key configured on server."}), 500

    target_url = f"https://generativelanguage.googleapis.com/{subpath}"
    
    headers = dict(request.headers)
    headers.pop("Host", None)
    
    if headers.get("x-goog-api-key") == "dummy_token_123":
        headers["x-goog-api-key"] = real_api_key
        
    query_params = dict(request.args)
    if query_params.get("key") == "dummy_token_123":
        query_params["key"] = real_api_key

    body = await request.get_data()
    
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=query_params,
            content=body,
            timeout=180.0
        )
        
    from quart import Response
    return Response(resp.content, status=resp.status_code, headers=dict(resp.headers))

if __name__ == '__main__':
    import signal
    def force_shutdown(sig, frame):
        import os
        print('\n[Antigravity] Force quitting...')
        os._exit(0)
    signal.signal(signal.SIGINT, force_shutdown)
    try:
        from core.bootstrap_gateway import run_preflight_checks
        run_preflight_checks(spawn_agent=False, exit_on_failure=True)
    except Exception as preflight_err:
        print(f"[Bootstrap] Pre-flight check warning: {preflight_err}")
    print('Starting Antigravity Backend Engine on port 5000...')
    import asyncio
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    config = Config()
    
    import os
    devcore_root = os.path.dirname(BASE_DIR)
    cert_path = os.path.join(devcore_root, "cert.pem")
    key_path = os.path.join(devcore_root, "key.pem")
    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        cert_path = os.path.join(os.getcwd(), "cert.pem")
        key_path = os.path.join(os.getcwd(), "key.pem")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        config.certfile = cert_path
        config.keyfile = key_path
        config.bind = ['0.0.0.0:5001', '[::1]:5001']
        config.insecure_bind = ['0.0.0.0:5000', '[::1]:5000']
    else:
        config.bind = ['0.0.0.0:5000', '[::1]:5000']
        
    asyncio.run(serve(app, config))
