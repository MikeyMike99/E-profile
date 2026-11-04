import io
import os
import subprocess
import zipfile
from pathlib import Path
from flask import Blueprint, jsonify, request, session

from config import Config
from bridge_manager import bridge_mgr

sync_bp = Blueprint('sync_bp', __name__)
config = Config()


def _is_authorized(req) -> bool:
    expected_secret = os.environ.get("SYNC_SECRET")
    if not expected_secret:
        return False
    header_secret = req.headers.get("X-Sync-Secret")
    form_secret = req.form.get("secret") if req.form else None
    json_secret = None
    if req.is_json:
        json_secret = (req.get_json(silent=True) or {}).get("secret")
    args_secret = req.args.get("secret")
    provided = header_secret or form_secret or json_secret or args_secret
    return provided == expected_secret


def _touch_wsgi_reload() -> bool:
    reloaded = False
    wsgi_dir = Path("/var/www/")
    if wsgi_dir.exists():
        for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
            try:
                wsgi_file.touch()
                reloaded = True
            except Exception:
                pass
    return reloaded


@sync_bp.route('/sync', methods=['POST'])
def handle_sync():
    if not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    rel_path = request.form.get('path')
    if not rel_path:
        return jsonify({"status": "error", "message": "No path provided"}), 400

    if any(k in rel_path for k in ('.git', 'profiles.json', '__pycache__', '.env')):
        return jsonify({"status": "error", "message": "Forbidden path"}), 403

    file = request.files.get('file')
    if not file:
        return jsonify({"status": "error", "message": "No file provided"}), 400

    target_path = (config.ROOT_DIR / rel_path).resolve()
    if config.ROOT_DIR.resolve() not in target_path.parents and target_path != config.ROOT_DIR.resolve():
        return jsonify({"status": "error", "message": "Path traversal detected"}), 403

    target_path.parent.mkdir(parents=True, exist_ok=True)
    file.save(str(target_path))

    reloaded = False
    if target_path.suffix == '.py':
        reloaded = _touch_wsgi_reload()

    return jsonify({
        "status": "success",
        "message": f"Updated {rel_path}",
        "reloaded": reloaded
    })


@sync_bp.route('/sync/package', methods=['POST'])
def handle_package_sync():
    if not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    pkg_file = request.files.get('package')
    if not pkg_file:
        return jsonify({"status": "error", "message": "No package file provided"}), 400

    extracted_files = []
    py_updated = False
    root_resolved = config.ROOT_DIR.resolve()

    try:
        with zipfile.ZipFile(pkg_file) as zf:
            for member in zf.infolist():
                norm_name = member.filename.replace("\\", "/").lstrip("/")
                if any(k in norm_name for k in ('.git', 'profiles.json', '__pycache__', '.env')):
                    continue

                target = (config.ROOT_DIR / norm_name).resolve()
                if root_resolved not in target.parents and target != root_resolved:
                    continue

                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    extracted_files.append(norm_name)
                    if target.suffix == '.py':
                        py_updated = True
    except Exception as e:
        return jsonify({"status": "error", "message": f"Corrupt or invalid zip package: {e}"}), 400

    reloaded = False
    if py_updated:
        reloaded = _touch_wsgi_reload()

    return jsonify({
        "status": "success",
        "extracted_count": len(extracted_files),
        "files": extracted_files,
        "reloaded": reloaded
    })


@sync_bp.route('/sync/git-pull', methods=['POST'])
def handle_remote_git_pull():
    if not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        git_env = os.environ.copy()
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        git_env["GIT_EDITOR"] = "true"

        token = ""
        for t_file in (config.ROOT_DIR / "gethub_token.txt", Path.home() / "gethub_token.txt"):
            if t_file.is_file():
                try:
                    token = t_file.read_text(encoding="utf-8").strip()
                    if token:
                        break
                except Exception:
                    pass
        if not token:
            token = os.environ.get("GITHUB_TOKEN", "").strip()

        auth_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/E-profile.git" if token else "origin"

        git_dir = config.ROOT_DIR / ".git"
        if git_dir.is_dir():
            for lock_f in git_dir.rglob("*.lock"):
                try:
                    lock_f.unlink(missing_ok=True)
                except Exception:
                    pass

        res = subprocess.run(
            ['git', 'pull', auth_url, 'main', '--no-edit', '--allow-unrelated-histories', '-X', 'ours'],
            cwd=str(config.ROOT_DIR),
            env=git_env,
            capture_output=True,
            text=True,
            timeout=30
        )
        if res.returncode != 0:
            subprocess.run(['git', 'fetch', auth_url, 'main'], cwd=str(config.ROOT_DIR), env=git_env, capture_output=True, text=True, timeout=20)
            res = subprocess.run(['git', 'reset', '--hard', 'FETCH_HEAD'], cwd=str(config.ROOT_DIR), env=git_env, capture_output=True, text=True, timeout=10)

        reloaded = _touch_wsgi_reload()
        return jsonify({
            "status": "success" if res.returncode == 0 else "error",
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "reloaded": reloaded
        })
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Git pull timed out after 30 seconds"}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@sync_bp.route('/bridge/poll', methods=['GET', 'POST'])
def handle_bridge_poll():
    if not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    worker_id = request.args.get('worker_id') or (request.get_json(silent=True) or {}).get('worker_id') or "local_core"
    task = bridge_mgr.poll_task(worker_id)
    if task:
        return jsonify({"status": "task", "task": task})
    return jsonify({"status": "idle"})


@sync_bp.route('/bridge/stream', methods=['POST'])
def handle_bridge_stream():
    if not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    seq = int(data.get("seq", 0))
    chunk = data.get("chunk", "")
    done = bool(data.get("done", False))

    if not task_id:
        return jsonify({"status": "error", "message": "Missing task_id"}), 400

    bridge_mgr.append_stream_chunk(task_id, seq, chunk, done=done)
    return jsonify({"status": "success"})


@sync_bp.route('/bridge/complete', methods=['POST'])
def handle_bridge_complete():
    if not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    result = data.get("result", {})
    status = data.get("status", "completed")

    if not task_id:
        return jsonify({"status": "error", "message": "Missing task_id"}), 400

    bridge_mgr.complete_task(task_id, result, status=status)
    return jsonify({"status": "success"})


@sync_bp.route('/bridge/status', methods=['GET'])
def handle_bridge_status():
    return jsonify(bridge_mgr.get_status())


@sync_bp.route('/bridge/enqueue', methods=['POST'])
def handle_bridge_enqueue():
    is_admin = bool(session.get("is_admin", False) or session.get("admin", False))
    if not is_admin and not _is_authorized(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    task_type = data.get("type", "chat")
    payload = data.get("payload", {})

    task = bridge_mgr.enqueue_task(task_type, payload)
    return jsonify({"status": "enqueued", "task": task})
