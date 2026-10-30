import argparse
import asyncio
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
try:
    import httpx
    import websockets
    from quart import Quart, websocket, request, Response, jsonify
except ImportError:
    httpx = None
    websockets = None
    Quart = None
    websocket = request = Response = jsonify = None

BACKEND_HTTP_URL = os.environ.get("DEVCORE_BACKEND_HTTP_URL", "http://127.0.0.1:5001")
BACKEND_WS_URL = os.environ.get("DEVCORE_BACKEND_WS_URL", "ws://127.0.0.1:5001/ws")

IMMUTABLE_JIT_BASENAMES = {
    "jit_elevation.py",
    ".jit_elevation_lease.json",
    ".devcore_master.key",
}

PROTECTED_FIREWALL_BASENAMES = {
    "raugus_hook.py",
    "hooks.json",
    "local_brain_broker.py",
    "raugus_resolver.py",
    "raugus_map.json",
    "generate_raugusmap.py",
    "tool_security_auditor.py",
}

DEFAULT_ENGINE_REL_PATHS = [
    "core/server.py",
    "core/session_manager.py",
    "core/project_manager.py",
    "core/bootstrap_gateway.py",
    "core/routes/auth.py",
    "core/routes/files.py",
    "core/routes/projects.py",
    "core/routes/system.py",
    "agents/agent_manager.py",
    "agents/mixins/comms_mixin.py",
    "agents/mixins/execution_mixin.py",
    "agents/mixins/transcript_mixin.py",
    "security/security_manager.py",
    "security/raugus_resolver.py",
    "security/local_brain_broker.py",
]

def get_base_dir(base_dir=None) -> str:
    if base_dir:
        return os.path.abspath(base_dir)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _is_jit_active_for_root(base_dir: str) -> bool:
    """Checks if a valid Human-in-the-Loop JIT Elevation Lease is active in base_dir."""
    try:
        lease_file = os.path.join(os.path.abspath(base_dir), "security", ".jit_elevation_lease.json")
        if not os.path.exists(lease_file):
            return False
        repo_root = get_base_dir()
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from security.jit_elevation import verify_jit_elevation
        ver = verify_jit_elevation()
        return bool(ver.get("valid") is True)
    except Exception:
        return False

def get_engine_files(base_dir=None, custom_files=None) -> list:
    root = get_base_dir(base_dir)
    rel_list = custom_files if custom_files is not None else DEFAULT_ENGINE_REL_PATHS
    existing = []
    for rel in rel_list:
        full = os.path.join(root, rel)
        if os.path.exists(full):
            existing.append(rel)
    return existing

def resolve_engine_target(filename: str, base_dir=None) -> str:
    root = get_base_dir(base_dir)
    core_dir = os.path.join(root, "core")
    candidates = [
        os.path.join(core_dir, filename),
        os.path.join(core_dir, "routes", filename),
        os.path.join(root, "agents", filename),
        os.path.join(root, "agents", "mixins", filename),
        os.path.join(root, "security", filename),
        os.path.join(root, ".agents", filename),
        os.path.join(root, filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(core_dir, filename)

def _compile_check(filepath: str) -> tuple:
    """Returns (ok: bool, error_message: str)."""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, ""
    except py_compile.PyCompileError as ce:
        return False, str(ce)
    except Exception as e:
        return False, str(e)

def _promote_staged_patches(base_dir: str, quiet: bool = False) -> tuple:
    """
    Validates and promotes any staged .py files in core/patches/ before running engine checks.
    Returns (promoted_list, rejected_list).
    """
    core_dir = os.path.join(base_dir, "core")
    patch_dir = os.path.join(core_dir, "patches")
    backup_dir = os.path.join(core_dir, "backups")
    os.makedirs(patch_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    promoted = []
    rejected = []
    jit_elevated = _is_jit_active_for_root(base_dir)

    for patch_name in sorted(os.listdir(patch_dir)):
        if not patch_name.endswith(".py"):
            continue
        staged_path = os.path.join(patch_dir, patch_name)
        if patch_name in IMMUTABLE_JIT_BASENAMES:
            if not quiet:
                print(f"[Bootstrap] Blocked staged patch for immutable JIT authority file: {patch_name}")
            try:
                os.remove(staged_path)
            except Exception:
                pass
            rejected.append({"file": patch_name, "reason": "Immutable JIT authority file"})
            continue

        if patch_name in PROTECTED_FIREWALL_BASENAMES and not jit_elevated:
            if not quiet:
                print(f"[Bootstrap] Blocked staged patch for protected guard file: {patch_name}")
            try:
                os.remove(staged_path)
            except Exception:
                pass
            rejected.append({"file": patch_name, "reason": "Protected Raugus guard file"})
            continue

        ok, err = _compile_check(staged_path)
        if not ok:
            if not quiet:
                print(f"[Bootstrap] Quarantining invalid staged patch {patch_name}: {err}")
            try:
                os.remove(staged_path)
            except Exception:
                pass
            rejected.append({"file": patch_name, "reason": err})
            continue

        target_path = resolve_engine_target(patch_name, base_dir=base_dir)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        backup_path = os.path.join(backup_dir, patch_name)

        if os.path.exists(target_path):
            live_ok, _ = _compile_check(target_path)
            if live_ok:
                shutil.copy2(target_path, backup_path)

        shutil.copy2(staged_path, target_path)
        shutil.copy2(staged_path, backup_path)
        try:
            os.remove(staged_path)
        except Exception:
            pass
        promoted.append(patch_name)
        if not quiet:
            print(f"[Bootstrap] Promoted validated staged patch: {patch_name} -> {os.path.relpath(target_path, base_dir)}")

    return promoted, rejected

def run_preflight_checks(
    base_dir=None,
    target_files=None,
    spawn_agent: bool = True,
    exit_on_failure: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Unified Pre-Flight Diagnostics & 3-Tier Self-Healing Supervisor:
      1. Promotes any valid staged patches waiting in core/patches/.
      2. Validates syntax of all engine .py modules via py_compile.
      3. Tier-1 Instant Self-Heal: Restores corrupted modules from core/backups/<name>.py (<5ms).
      4. Tier-2 AI Emergency Auto-Repair: Spawns agy to stage a fix in core/patches/<name>.py,
         then validates and promotes it safely.
    """
    root = get_base_dir(base_dir)
    core_dir = os.path.join(root, "core")
    patch_dir = os.path.join(core_dir, "patches")
    backup_dir = os.path.join(core_dir, "backups")
    os.makedirs(patch_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    if not quiet:
        print("=========================================================")
        print("[Bootstrap] Running Unified Pre-Flight Diagnostics...")

    promoted_patches, rejected_patches = _promote_staged_patches(root, quiet=quiet)
    files_to_check = get_engine_files(root, custom_files=target_files)

    healed_from_backup = []
    healed_by_agent = []
    failed_files = []

    max_retries = 2 if spawn_agent else 1
    for attempt in range(max_retries + 1):
        failed_files = []
        for rel_file in files_to_check:
            full_path = os.path.join(root, rel_file)
            if not os.path.exists(full_path):
                continue

            basename = os.path.basename(full_path)
            backup_path = os.path.join(backup_dir, basename)

            ok, err = _compile_check(full_path)
            if ok:
                if basename not in PROTECTED_FIREWALL_BASENAMES and not os.path.exists(backup_path):
                    try:
                        shutil.copy2(full_path, backup_path)
                    except Exception:
                        pass
                continue

            if not quiet:
                print(f"[Bootstrap] SYNTAX ERROR in {rel_file}:\n{err}")

            staged_candidate = os.path.join(patch_dir, basename)
            if os.path.exists(staged_candidate) and basename not in PROTECTED_FIREWALL_BASENAMES:
                s_ok, _ = _compile_check(staged_candidate)
                if s_ok:
                    shutil.copy2(staged_candidate, full_path)
                    shutil.copy2(staged_candidate, backup_path)
                    try:
                        os.remove(staged_candidate)
                    except Exception:
                        pass
                    healed_from_backup.append(rel_file)
                    if not quiet:
                        print(f"[Bootstrap] Tier-1 Self-Heal: Restored {rel_file} from staged patch in core/patches/{basename}.")
                    continue

            if os.path.exists(backup_path):
                b_ok, _ = _compile_check(backup_path)
                if b_ok:
                    shutil.copy2(backup_path, full_path)
                    healed_from_backup.append(rel_file)
                    if not quiet:
                        print(f"[Bootstrap] Tier-1 Self-Heal: Instantly restored {rel_file} from core/backups/{basename}.")
                    continue

            if spawn_agent and attempt < max_retries and basename not in PROTECTED_FIREWALL_BASENAMES:
                if not quiet:
                    print(
                        f"[Bootstrap] Spawning Emergency Auto-Repair Agent for {rel_file} "
                        f"(Attempt {attempt + 1}/{max_retries})..."
                    )
                agy_binary = shutil.which("agy")
                if not agy_binary:
                    fallback = os.path.expanduser("~/.local/bin/agy")
                    agy_binary = fallback if os.path.exists(fallback) else "agy"

                staged_target_rel = f"core/patches/{basename}"
                repair_prompt = (
                    f"CRITICAL SYSTEM ERROR: The engine file '{rel_file}' failed Python compilation.\n"
                    f"Error Traceback:\n{err}\n\n"
                    f"You are the Emergency Auto-Repair Agent running with ADMIN privileges.\n"
                    f"1. Read the broken file '{rel_file}'.\n"
                    f"2. Fix the syntax or indentation error causing this traceback.\n"
                    f"3. Write the COMPLETE corrected Python module to '{staged_target_rel}' "
                    f"(mandatory hot-patch staging directory).\n"
                    f"4. Do NOT write markdown fences to the file—only valid Python code."
                )
                try:
                    subprocess.run(
                        [agy_binary, "--dangerously-skip-permissions", "--print", repair_prompt],
                        cwd=root,
                        timeout=90,
                    )
                    if os.path.exists(staged_candidate):
                        s_ok, _ = _compile_check(staged_candidate)
                        if s_ok:
                            shutil.copy2(staged_candidate, full_path)
                            shutil.copy2(staged_candidate, backup_path)
                            try:
                                os.remove(staged_candidate)
                            except Exception:
                                pass
                            healed_by_agent.append(rel_file)
                            if not quiet:
                                print(f"[Bootstrap] Tier-2 Self-Heal: Auto-Repair Agent repaired {rel_file} via {staged_target_rel}.")
                            continue
                except Exception as agent_err:
                    if not quiet:
                        print(f"[Bootstrap] Auto-Repair Agent invocation failed: {agent_err}")

            failed_files.append({"file": rel_file, "error": err})

        if not failed_files:
            if not quiet:
                print(
                    f"[Bootstrap] All {len(files_to_check)} engine files passed syntax validation. "
                    f"(Promoted: {len(promoted_patches)}, Backup-Healed: {len(healed_from_backup)}, Agent-Healed: {len(healed_by_agent)})"
                )
                print("=========================================================")
            return {
                "success": True,
                "checked_count": len(files_to_check),
                "promoted_patches": promoted_patches,
                "rejected_patches": rejected_patches,
                "healed_from_backup": healed_from_backup,
                "healed_by_agent": healed_by_agent,
                "failed_files": [],
            }

    if not quiet:
        print(f"[Bootstrap] FATAL: {len(failed_files)} file(s) failed validation after recovery attempts.")
    if exit_on_failure:
        sys.exit(1)

    return {
        "success": False,
        "checked_count": len(files_to_check),
        "promoted_patches": promoted_patches,
        "rejected_patches": rejected_patches,
        "healed_from_backup": healed_from_backup,
        "healed_by_agent": healed_by_agent,
        "failed_files": failed_files,
    }

def heal_crash(
    traceback_str: str,
    base_dir=None,
    spawn_agent: bool = False,
    restart_process: bool = False,
) -> bool:
    """
    Unified Crash Self-Healing Entrypoint (consolidates legacy self_heal.py).
    1. Runs run_preflight_checks() to heal any syntax corruption from core/backups/ or core/patches/.
    2. If all files compiled cleanly but a runtime exception occurred and GEMINI_API_KEY is available,
       requests a staged fix into core/patches/<filename>.py, validates with py_compile, and applies it.
    """
    root = get_base_dir(base_dir)
    print("\n=======================================================")
    print("      CRITICAL CRASH DETECTED - INITIATING SELF-HEAL    ")
    print("=======================================================")

    report = run_preflight_checks(base_dir=root, spawn_agent=spawn_agent, exit_on_failure=False)
    if report["healed_from_backup"] or report["healed_by_agent"] or report["promoted_patches"]:
        print("[Bootstrap] Crash healed via pre-flight backup/patch recovery.")
        if restart_process:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return True

    if not report["success"]:
        print("[Bootstrap] Pre-flight recovery could not resolve syntax errors.")
        return False

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[Bootstrap] Runtime crash self-heal skipped: No GEMINI_API_KEY in environment.")
        return False

    file_matches = re.findall(r'File "([^"]+\.py)"', traceback_str or "")
    target_rel = None
    for candidate in reversed(file_matches):
        abs_cand = os.path.abspath(candidate)
        if abs_cand.startswith(root):
            rel = os.path.relpath(abs_cand, root).replace("\\", "/")
            if os.path.basename(rel) not in PROTECTED_FIREWALL_BASENAMES:
                target_rel = rel
                break

    if not target_rel:
        print("[Bootstrap] Could not pinpoint a modifiable repository file in traceback.")
        return False

    full_target = os.path.join(root, target_rel)
    basename = os.path.basename(full_target)
    try:
        with open(full_target, "r", encoding="utf-8") as f:
            source_code = f.read()
    except Exception as e:
        print(f"[Bootstrap] Could not read {target_rel}: {e}")
        return False

    prompt = (
        f"You are the autonomous self-healing engine for DevCore.\n"
        f"The module '{target_rel}' crashed with the following traceback:\n\n"
        f"{traceback_str}\n\n"
        f"Current contents of '{target_rel}':\n```python\n{source_code}\n```\n\n"
        f"Return ONLY the complete corrected Python file inside a single ```python ... ``` block."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        if not match:
            print("[Bootstrap] Failed to extract valid Python block from AI response.")
            return False

        repaired_code = match.group(1)
        patch_path = os.path.join(root, "core", "patches", basename)
        os.makedirs(os.path.dirname(patch_path), exist_ok=True)
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(repaired_code)

        promoted, _ = _promote_staged_patches(root, quiet=False)
        if basename in promoted:
            print(f"[Bootstrap] Successfully staged, validated, and applied crash fix for {target_rel}.")
            if restart_process:
                os.execv(sys.executable, [sys.executable] + sys.argv)
            return True
    except Exception as e:
        print(f"[Bootstrap] Runtime crash self-healing failed: {e}")

    return False

def create_gateway_app(backend_http_url: str = None, backend_ws_url: str = None):
    """
    Creates a Quart Persistent Bootstrap Gateway application configured to proxy HTTP and WebSocket
    traffic to the specified backend URLs while keeping browser connections alive across reloads.
    """
    if Quart is None:
        return None
    gateway_app = Quart(__name__)
    gateway_app.backend_http_url = (backend_http_url or BACKEND_HTTP_URL).rstrip("/")
    gateway_app.backend_ws_url = backend_ws_url or BACKEND_WS_URL

    @gateway_app.route("/api/gateway/health", methods=["GET"])
    async def gateway_health():
        backend_online = False
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                r = await client.get(f"{gateway_app.backend_http_url}/")
                backend_online = r.status_code < 500
        except Exception:
            backend_online = False
        return jsonify({
            "gateway": "online",
            "backend_http_url": gateway_app.backend_http_url,
            "backend_ws_url": gateway_app.backend_ws_url,
            "backend_reachable": backend_online,
        })

    @gateway_app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    @gateway_app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_http(path):
        target_url = f"{gateway_app.backend_http_url}/{path}"
        headers = {
            key: value
            for key, value in request.headers
            if key.lower() not in ("host", "content-length")
        }
        body = await request.get_data()
        params = request.args

        start_wait = time.time()
        last_err = None
        while time.time() - start_wait < 6.0:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.request(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        params=params,
                        content=body,
                    )
                    excluded_headers = {
                        "content-encoding",
                        "content-length",
                        "transfer-encoding",
                        "connection",
                    }
                    forward_headers = [
                        (name, val)
                        for name, val in res.headers.items()
                        if name.lower() not in excluded_headers
                    ]
                    return Response(res.content, status=res.status_code, headers=forward_headers)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_err = e
                await asyncio.sleep(0.25)

        return Response(f"Backend temporarily unavailable: {last_err}", status=503)

    @gateway_app.websocket("/ws")
    async def proxy_ws():
        client_ws = websocket._get_current_object()
        client_queue = asyncio.Queue()

        async def client_listener():
            """Reads incoming messages from the browser and queues them."""
            try:
                while True:
                    data = await client_ws.receive()
                    if data:
                        await client_queue.put(data)
            except Exception:
                pass

        async def client_heartbeat():
            """Sends a keep-alive pulse every 4 seconds so WSL/TCP never drops the socket."""
            try:
                while True:
                    await asyncio.sleep(4.0)
                    try:
                        await client_ws.send(json.dumps({"type": "gateway_ping", "time": time.time()}))
                    except Exception:
                        break
            except asyncio.CancelledError:
                pass

        client_listen_task = asyncio.create_task(client_listener())
        heartbeat_task = asyncio.create_task(client_heartbeat())

        try:
            while not client_listen_task.done():
                try:
                    async with websockets.connect(
                        gateway_app.backend_ws_url, ping_interval=10, ping_timeout=15
                    ) as backend_ws:
                        await client_ws.send(
                            json.dumps({
                                "type": "system",
                                "level": "info",
                                "message": "Connected to Antigravity Engine.",
                            })
                        )

                        async def forward_to_client():
                            async for msg in backend_ws:
                                await client_ws.send(msg)

                        async def forward_to_backend():
                            while True:
                                msg = await client_queue.get()
                                await backend_ws.send(msg)

                        fwd_to_client_task = asyncio.create_task(forward_to_client())
                        fwd_to_backend_task = asyncio.create_task(forward_to_backend())

                        done, _ = await asyncio.wait(
                            [fwd_to_client_task, fwd_to_backend_task, client_listen_task],
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        for t in (fwd_to_client_task, fwd_to_backend_task):
                            if not t.done():
                                t.cancel()

                        if client_listen_task.done():
                            break

                        if fwd_to_client_task in done:
                            try:
                                await client_ws.send(
                                    json.dumps({
                                        "type": "system",
                                        "level": "info",
                                        "message": "Engine reloading or running tasks. Connection preserved by Bootstrap Gateway...",
                                    })
                                )
                            except Exception:
                                break
                            await asyncio.sleep(0.25)

                except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError):
                    try:
                        await client_ws.send(
                            json.dumps({
                                "type": "system",
                                "level": "info",
                                "message": "Engine reloading or running tasks. Connection preserved by Bootstrap Gateway...",
                            })
                        )
                    except Exception:
                        break
                    await asyncio.sleep(0.25)
        finally:
            client_listen_task.cancel()
            heartbeat_task.cancel()

    return gateway_app

app = create_gateway_app()

async def _run_ephemeral_gateway_failover_test() -> tuple:
    """
    Spins up the Bootstrap Gateway and a simulated Backend on ephemeral localhost ports,
    verifies HTTP proxying, WebSocket forwarding, backend disconnect survival, and automatic
    reconnection without dropping the client WebSocket.
    """
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    gw_port = 15050
    be_port = 15051
    be_http = f"http://127.0.0.1:{be_port}"
    be_ws = f"ws://127.0.0.1:{be_port}/ws"

    mock_backend = Quart("mock_backend")
    drop_backend_ws = asyncio.Event()

    @mock_backend.route("/")
    @mock_backend.route("/ping")
    async def mock_ping():
        return jsonify({"status": "ok", "source": "mock_backend"})

    @mock_backend.websocket("/ws")
    async def mock_ws():
        ws = websocket._get_current_object()
        while not drop_backend_ws.is_set():
            recv_task = asyncio.create_task(ws.receive())
            drop_task = asyncio.create_task(drop_backend_ws.wait())
            done, pending = await asyncio.wait(
                [recv_task, drop_task], return_when=asyncio.FIRST_COMPLETED
            )
            for p in pending:
                p.cancel()
            if drop_task in done:
                break
            msg = recv_task.result()
            await ws.send(json.dumps({"type": "echo", "received": msg}))

    gw_app = create_gateway_app(backend_http_url=be_http, backend_ws_url=be_ws)

    gw_shutdown = asyncio.Event()
    be_shutdown_1 = asyncio.Event()
    be_shutdown_2 = asyncio.Event()

    gw_cfg = Config()
    gw_cfg.bind = [f"127.0.0.1:{gw_port}"]
    gw_cfg.accesslog = None
    gw_cfg.errorlog = None

    be_cfg_1 = Config()
    be_cfg_1.bind = [f"127.0.0.1:{be_port}"]
    be_cfg_1.accesslog = None
    be_cfg_1.errorlog = None

    gw_task = asyncio.create_task(serve(gw_app, gw_cfg, shutdown_trigger=gw_shutdown.wait))
    be_task_1 = asyncio.create_task(serve(mock_backend, be_cfg_1, shutdown_trigger=be_shutdown_1.wait))

    try:
        await asyncio.sleep(0.4)

        async with httpx.AsyncClient(timeout=5.0) as client:
            h_res = await client.get(f"http://127.0.0.1:{gw_port}/api/gateway/health")
            if h_res.status_code != 200 or not h_res.json().get("backend_reachable"):
                return False, f"Gateway health check failed: {h_res.text}"

            p_res = await client.get(f"http://127.0.0.1:{gw_port}/ping")
            if p_res.status_code != 200 or p_res.json().get("source") != "mock_backend":
                return False, f"HTTP reverse proxy failed: {p_res.text}"

        async with websockets.connect(f"ws://127.0.0.1:{gw_port}/ws") as client_ws:
            msg1 = json.loads(await asyncio.wait_for(client_ws.recv(), timeout=3.0))
            if "Connected to Antigravity Engine" not in msg1.get("message", ""):
                return False, f"Unexpected initial WS banner: {msg1}"

            await client_ws.send("hello-before-restart")
            echo1 = json.loads(await asyncio.wait_for(client_ws.recv(), timeout=3.0))
            if echo1.get("received") != "hello-before-restart":
                return False, f"Unexpected echo before restart: {echo1}"

            drop_backend_ws.set()
            be_shutdown_1.set()
            await asyncio.wait_for(be_task_1, timeout=3.0)

            await client_ws.send("queued-while-backend-down")

            preserved_msg = None
            for _ in range(5):
                evt = json.loads(await asyncio.wait_for(client_ws.recv(), timeout=3.0))
                if "Connection preserved by Bootstrap Gateway" in evt.get("message", ""):
                    preserved_msg = evt
                    break
            if not preserved_msg:
                return False, "Did not receive 'Connection preserved by Bootstrap Gateway' notice when backend dropped."

            drop_backend_ws.clear()
            be_cfg_2 = Config()
            be_cfg_2.bind = [f"127.0.0.1:{be_port}"]
            be_cfg_2.accesslog = None
            be_cfg_2.errorlog = None
            be_task_2 = asyncio.create_task(serve(mock_backend, be_cfg_2, shutdown_trigger=be_shutdown_2.wait))

            reconnected = False
            replayed_echo = False
            for _ in range(10):
                evt = json.loads(await asyncio.wait_for(client_ws.recv(), timeout=3.0))
                if "Connected to Antigravity Engine" in evt.get("message", ""):
                    reconnected = True
                elif evt.get("type") == "echo" and evt.get("received") == "queued-while-backend-down":
                    replayed_echo = True
                if reconnected and replayed_echo:
                    break

            drop_backend_ws.set()
            be_shutdown_2.set()
            await asyncio.wait_for(be_task_2, timeout=3.0)

            if not (reconnected and replayed_echo):
                return False, f"Failover incomplete (reconnected={reconnected}, replayed_echo={replayed_echo})"

        return True, "HTTP proxy, WebSocket bridge, backend drop survival, and queued message replay verified."
    except Exception as e:
        return False, f"Exception during gateway failover test: {type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        drop_backend_ws.set()
        gw_shutdown.set()
        be_shutdown_1.set()
        be_shutdown_2.set()
        try:
            await asyncio.wait_for(gw_task, timeout=2.0)
        except Exception:
            pass

def run_self_test() -> int:
    """
    Executes the 4-Stage Non-Destructive Bootstrap Verification Suite without touching live port 5000.
    """
    print("=========================================================")
    print("  DEVCORE BOOTSTRAP & SELF-HEALING VERIFICATION SUITE    ")
    print("=========================================================")
    passed = 0
    total = 4

    res1 = run_preflight_checks(spawn_agent=False, quiet=True)
    if res1["success"] and res1["checked_count"] >= 14:
        print(f"  [PASS] Test 1: Live Engine Pre-Flight Check ({res1['checked_count']} engine modules verified & backed up)")
        passed += 1
    else:
        print(f"  [FAIL] Test 1: Live Engine Pre-Flight Check -> {res1}")

    with tempfile.TemporaryDirectory(prefix="devcore_bootstrap_test_") as tmp_dir:
        os.makedirs(os.path.join(tmp_dir, "core", "backups"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "core", "patches"), exist_ok=True)
        target_file = os.path.join(tmp_dir, "core", "server.py")
        backup_file = os.path.join(tmp_dir, "core", "backups", "server.py")

        with open(backup_file, "w", encoding="utf-8") as f:
            f.write("def healthy_server():\n    return 200\n")
        with open(target_file, "w", encoding="utf-8") as f:
            f.write("def broken_server(:\n    syntax error here!!!\n")

        res2 = run_preflight_checks(
            base_dir=tmp_dir,
            target_files=["core/server.py"],
            spawn_agent=False,
            quiet=True,
        )
        ok_compile, _ = _compile_check(target_file)
        if res2["success"] and "core/server.py" in res2["healed_from_backup"] and ok_compile:
            print("  [PASS] Test 2: Tier-1 Instant Backup Self-Heal (corrupted core/server.py auto-restored from core/backups/)")
            passed += 1
        else:
            print(f"  [FAIL] Test 2: Tier-1 Instant Backup Self-Heal -> {res2}")

    with tempfile.TemporaryDirectory(prefix="devcore_patch_test_") as tmp_dir:
        os.makedirs(os.path.join(tmp_dir, "core", "backups"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "core", "patches"), exist_ok=True)
        target_file = os.path.join(tmp_dir, "core", "session_manager.py")
        staged_good = os.path.join(tmp_dir, "core", "patches", "session_manager.py")
        staged_bad = os.path.join(tmp_dir, "core", "patches", "project_manager.py")
        staged_guard = os.path.join(tmp_dir, "core", "patches", "raugus_hook.py")

        with open(target_file, "w", encoding="utf-8") as f:
            f.write("class Broken(\n")
        with open(staged_good, "w", encoding="utf-8") as f:
            f.write("class SessionManager:\n    def ok(self):\n        return True\n")
        with open(staged_bad, "w", encoding="utf-8") as f:
            f.write("def invalid_syntax(:\n")
        with open(staged_guard, "w", encoding="utf-8") as f:
            f.write("# unauthorized guard overwrite attempt\n")

        res3 = run_preflight_checks(
            base_dir=tmp_dir,
            target_files=["core/session_manager.py"],
            spawn_agent=False,
            quiet=True,
        )
        ok_compile, _ = _compile_check(target_file)
        backup_created = os.path.exists(os.path.join(tmp_dir, "core", "backups", "session_manager.py"))
        rejected_names = {r["file"] for r in res3["rejected_patches"]}
        if (
            res3["success"]
            and "session_manager.py" in res3["promoted_patches"]
            and "project_manager.py" in rejected_names
            and "raugus_hook.py" in rejected_names
            and ok_compile
            and backup_created
        ):
            print("  [PASS] Test 3: Staged Hot-Patch Promotion, Backup Seeding & Bad/Guard Patch Quarantine")
            passed += 1
        else:
            print(f"  [FAIL] Test 3: Staged Hot-Patch Promotion -> {res3}")

    ok4, detail4 = asyncio.run(_run_ephemeral_gateway_failover_test())
    if ok4:
        print(f"  [PASS] Test 4: Ephemeral Gateway Failover (15050 -> 15051): {detail4}")
        passed += 1
    else:
        print(f"  [FAIL] Test 4: Ephemeral Gateway Failover: {detail4}")

    print("---------------------------------------------------------")
    print(f"  SUMMARY: {passed} / {total} Bootstrap Verification Tests Passed")
    print("=========================================================")
    return 0 if passed == total else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DevCore Unified Persistent Bootstrap Gateway & Self-Healing Supervisor")
    parser.add_argument("--preflight-only", action="store_true", help="Run pre-flight syntax & self-healing checks and exit.")
    parser.add_argument("--self-test", action="store_true", help="Run the 4-stage non-destructive bootstrap verification suite.")
    parser.add_argument("--no-agent", action="store_true", help="Disable spawning the agy Auto-Repair Agent during pre-flight.")
    parser.add_argument("--gateway-port", type=int, default=int(os.environ.get("DEVCORE_GATEWAY_PORT", "5000")), help="Port for the Bootstrap Gateway.")
    parser.add_argument("--backend-port", type=int, default=int(os.environ.get("DEVCORE_BACKEND_PORT", "5001")), help="Port of the internal Backend Engine.")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_self_test())

    run_preflight_checks(spawn_agent=not args.no_agent, exit_on_failure=True)
    if args.preflight_only:
        sys.exit(0)

    backend_http = f"http://127.0.0.1:{args.backend_port}"
    backend_ws = f"ws://127.0.0.1:{args.backend_port}/ws"
    gateway = create_gateway_app(backend_http_url=backend_http, backend_ws_url=backend_ws)

    print("=========================================================")
    print(f"Starting Antigravity Persistent Bootstrap Gateway on {args.gateway_port}")
    print(f"Internal Backend Target: {backend_http}")
    print("=========================================================")
    gateway.run(host="0.0.0.0", port=args.gateway_port, use_reloader=False)
