"""Claude brain authentication + status endpoints for the standalone (Quart)
DevCore server. Mirrors the Flask ai_plugin endpoints so the Claude sign-in
works in standalone mode too. Shares the credential/brain helpers in
core.local_model_service."""
import asyncio
import json
import os
import re
import subprocess
import threading

from quart import Blueprint, request, jsonify, current_app

ai_bp = Blueprint("ai_routes_bp", __name__)

_login = {"proc": None, "buf": ""}


def _claude_bin():
    import shutil
    return shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")


def _owner_ok():
    """Owner gate: the host master key must be present."""
    try:
        return bool(current_app.security_mgr.is_host_owner_request(request.remote_addr, request.headers))
    except Exception:
        return False


def _extract_oauth_url(raw):
    clean = raw.replace("\x1b", "").replace("\x07", "").replace("]8;;", "")
    m = re.search(r"https://claude\.com/cai/oauth/authorize\?\S+", clean)
    if not m:
        return None
    url = m.group(0)
    i = url.find("https://", 8)  # printed twice, back-to-back
    return url[:i] if i != -1 else url


async def _run(fn):
    return await asyncio.get_event_loop().run_in_executor(None, fn)


@ai_bp.route("/api/ai/status")
async def ai_status():
    from core.local_model_service import get_anthropic_credential
    if get_anthropic_credential():
        return jsonify({"connected": True, "backend": "api", "message": "Connected via API key."})
    cb = _claude_bin()
    if cb and os.path.exists(cb):
        logged_in = False
        try:
            r = await _run(lambda: subprocess.run([cb, "auth", "status"], capture_output=True, text=True, timeout=8))
            logged_in = bool((json.loads(r.stdout or "{}") or {}).get("loggedIn"))
        except Exception:
            logged_in = False
        if logged_in:
            return jsonify({"connected": True, "backend": "subscription",
                            "message": "Connected via your Claude subscription — no API key needed."})
        return jsonify({"connected": False, "backend": "subscription",
                        "message": "Not connected. Sign in with your Claude subscription (no API key needed), or paste an API key below."})
    return jsonify({"connected": False, "backend": "none",
                    "message": "Claude is not set up yet. Paste an API key below to connect."})


@ai_bp.route("/api/ai/connect", methods=["POST"])
async def ai_connect():
    if not _owner_ok():
        return jsonify({"ok": False, "error": "Admin privileges are required to connect Claude."}), 403
    data = (await request.get_json(silent=True)) or {}
    key = (data.get("api_key") or "").strip()
    if not key.startswith("sk-ant-"):
        return jsonify({"ok": False, "error": "That doesn't look like an Anthropic API key (expected sk-ant-...)."}), 400
    from core.local_model_service import set_claude_api_key, run_claude_model
    try:
        set_claude_api_key(key)
    except Exception:
        os.environ["ANTHROPIC_API_KEY"] = key
    result = await _run(lambda: run_claude_model("Connectivity test.", "Reply with exactly: OK",
                                                 "Claude Opus 5.5", 64, "selftest"))
    ok = not result.startswith("[LOCAL_BRAIN_")
    return jsonify({"ok": ok, "message": "Connected and tested successfully." if ok else result[:200]}), (200 if ok else 502)


@ai_bp.route("/api/ai/login/start", methods=["POST"])
async def ai_login_start():
    if not _owner_ok():
        return jsonify({"ok": False, "error": "Admin privileges are required."}), 403
    cb = _claude_bin()
    if not (cb and os.path.exists(cb)):
        return jsonify({"ok": False, "error": "The Claude CLI is not installed on the server."}), 400
    old = _login.get("proc")
    if old and old.poll() is None:
        try:
            old.kill()
        except Exception:
            pass
    _login["buf"] = ""
    proc = subprocess.Popen(
        [cb, "auth", "login", "--claudeai"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    _login["proc"] = proc

    def _reader(p):
        try:
            for ch in iter(lambda: p.stdout.read(1), ""):
                _login["buf"] += ch
        except Exception:
            pass
    threading.Thread(target=_reader, args=(proc,), daemon=True).start()

    for _ in range(120):
        url = _extract_oauth_url(_login["buf"])
        if url:
            return jsonify({"ok": True, "url": url})
        await asyncio.sleep(0.1)
    return jsonify({"ok": False, "error": "Timed out waiting for the sign-in link. Try again."}), 504


@ai_bp.route("/api/ai/login/complete", methods=["POST"])
async def ai_login_complete():
    if not _owner_ok():
        return jsonify({"ok": False, "error": "Admin privileges are required."}), 403
    data = (await request.get_json(silent=True)) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "Paste the code from the sign-in page."}), 400
    proc = _login.get("proc")
    if not proc or proc.poll() is not None:
        return jsonify({"ok": False, "error": "No active sign-in. Click Sign in again."}), 409
    try:
        proc.stdin.write(code + "\n")
        proc.stdin.flush()
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not submit code: {e}"}), 500
    try:
        await _run(lambda: proc.wait(timeout=30))
    except Exception:
        pass
    cb = _claude_bin()
    logged_in = False
    try:
        r = await _run(lambda: subprocess.run([cb, "auth", "status"], capture_output=True, text=True, timeout=8))
        logged_in = bool((json.loads(r.stdout or "{}") or {}).get("loggedIn"))
    except Exception:
        pass
    return jsonify({
        "ok": logged_in,
        "message": "Signed in with your Claude subscription." if logged_in
        else "Sign-in did not complete. Check the code and try again.",
    }), (200 if logged_in else 502)
