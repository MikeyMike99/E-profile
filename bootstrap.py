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
import time
import shlex

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
    'requests': 'requests'
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


def _find_agy_binary() -> Path | None:
    """Discovers the Antigravity (agy) CLI binary and ensures it is executable."""
    candidates = [
        Path.home() / ".local" / "bin" / "agy",
        Path("/home/MikeyMike/.local/bin/agy"),
        Path.home() / "bin" / "agy",
    ]
    for p in candidates:
        if p.is_file():
            try:
                if not os.access(str(p), os.X_OK):
                    os.chmod(str(p), 0o755)
            except Exception:
                pass
            return p

    which_agy = shutil.which("agy")
    if which_agy:
        p = Path(which_agy)
        try:
            if not os.access(str(p), os.X_OK):
                os.chmod(str(p), 0o755)
        except Exception:
            pass
        return p

    return None


def _run_agy_command(base_dir: Path, cmd_or_args, timeout: int = 90) -> tuple[int, str, str]:
    """Safely executes agy CLI operations in a properly configured subshell."""
    agy_bin = _find_agy_binary()
    if not agy_bin:
        return -1, "", "Antigravity CLI binary (agy) not found in ~/.local/bin/agy or PATH."

    env = os.environ.copy()
    local_bin = str(Path.home() / ".local" / "bin")
    if "PATH" in env and local_bin not in env["PATH"]:
        env["PATH"] = f"{local_bin}:{env['PATH']}"
    elif "PATH" not in env:
        env["PATH"] = local_bin

    # Ensure headless auto-approvals in settings.json
    try:
        agy_settings_dir = Path.home() / ".gemini" / "antigravity-cli"
        agy_settings_dir.mkdir(parents=True, exist_ok=True)
        agy_settings_file = agy_settings_dir / "settings.json"
        settings_data = {}
        if agy_settings_file.exists():
            try:
                settings_data = json.loads(agy_settings_file.read_text(encoding="utf-8"))
            except Exception:
                settings_data = {}
        perms = settings_data.setdefault("permissions", {})
        allow_list = perms.setdefault("allow", [])
        for tool_rule in ["read_file()", "run_command()", "search_web()"]:
            if tool_rule not in allow_list:
                allow_list.append(tool_rule)
        agy_settings_file.write_text(json.dumps(settings_data, indent=2), encoding="utf-8")
    except Exception:
        pass

    if isinstance(cmd_or_args, list):
        args = list(cmd_or_args)
        if "--print" in args and "--dangerously-skip-permissions" not in args:
            args = ["--dangerously-skip-permissions"] + args
        full_cmd = [str(agy_bin)] + args
        shell = False
    else:
        raw_cmd = str(cmd_or_args).strip()
        if raw_cmd.startswith("agy ") or raw_cmd == "agy":
            parts = raw_cmd.split(maxsplit=1)
            sub = parts[1].strip() if len(parts) > 1 else ""
            std_cmds = {"agent", "agents", "models", "mcp", "plugin", "plugins", "help", "--help", "-h", "version", "--version", "update", "changelog", "doctor"}
            if sub and not sub.startswith("-") and sub.split()[0] not in std_cmds:
                raw_cmd = f"{shlex.quote(str(agy_bin))} --dangerously-skip-permissions --print {shlex.quote(sub)}"
            elif not sub:
                raw_cmd = f"{shlex.quote(str(agy_bin))} --help"
            else:
                raw_cmd = f"{shlex.quote(str(agy_bin))} {sub}"
        full_cmd = raw_cmd
        shell = True

    try:
        res = subprocess.run(full_cmd, shell=shell, cwd=str(base_dir), capture_output=True, text=True, timeout=timeout, env=env)
        return res.returncode, res.stdout or "", res.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"Operation timed out after {timeout} seconds."
    except Exception as e:
        return -1, "", str(e)


_LAST_STORAGE_CHECK_EPOCH = 0.0
_STORAGE_CHECK_LOCK = threading.Lock()


def auto_enforce_storage_limits(base_dir: Path, force: bool = False) -> dict:
    """Automatic background and startup storage sentinel.
    Ensures .git repo, caches, and temp files never exceed quota limits.
    Guarantees agy binary in ~/.local/bin/agy is preserved and protected.
    """
    global _LAST_STORAGE_CHECK_EPOCH
    if not is_production_server() and not force:
        return {}

    now = time.time()
    with _STORAGE_CHECK_LOCK:
        if not force and (now - _LAST_STORAGE_CHECK_EPOCH) < 1800:
            return {}
        _LAST_STORAGE_CHECK_EPOCH = now

    return cleanup_storage(base_dir, verbose=False)


def cleanup_storage(base_dir: Path, verbose: bool = True) -> dict:
    """Automated storage recovery & quota optimization protocol for PythonAnywhere (512MB limit).
    Purges pip caches, system caches, stale git packfiles/reflogs in e_profile,
    unneeded heavy dependencies, bytecode caches, and temporary files.
    Strictly preserves the essential agy binary (~/.local/bin/agy).
    """
    home = Path.home()
    report = {
        "actions_taken": [],
        "freed_estimate_mb": 0.0,
        "errors": []
    }

    if os.name == "nt":
        if verbose:
            print("[cleanup] Storage cleanup protocol skipped on Windows development host.")
        return report

    def _log(msg):
        report["actions_taken"].append(msg)
        if verbose:
            print(f"🧹 {msg}")

    # 1. Purge pip cache via CLI and direct filesystem removal
    for py_cmd in ["python3.9", "python3", sys.executable]:
        try:
            res = subprocess.run([py_cmd, "-m", "pip", "cache", "purge"], capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and "Files removed" in (res.stdout or ""):
                _log(f"Purged pip cache via {py_cmd}")
                break
        except Exception:
            pass

    for cache_sub in [home / ".cache", home / ".npm", home / ".local" / "share" / "Trash"]:
        if cache_sub.exists():
            try:
                shutil.rmtree(cache_sub, ignore_errors=True)
                _log(f"Removed cache directory: ~/{cache_sub.relative_to(home)}")
            except Exception as e:
                report["errors"].append(str(e))

    # 2. Incompatible Python 3.10 directory cleanup (PythonAnywhere runs 3.9)
    bad_py310 = home / ".local" / "lib" / "python3.10"
    if bad_py310.exists():
        try:
            shutil.rmtree(bad_py310, ignore_errors=True)
            _log("Removed incompatible ~/.local/lib/python3.10 directory")
        except Exception as e:
            report["errors"].append(str(e))

    # 3. Uninstall unneeded heavy packages if present
    heavy_pkgs = [
        "spacy", "presidio-analyzer", "presidio-anonymizer",
        "thinc", "blis", "spacy-legacy", "spacy-loggers",
        "libcst", "flask-socketio", "watchdog"
    ]
    for py_cmd in ["python3.9", "python3", sys.executable]:
        try:
            res = subprocess.run([py_cmd, "-m", "pip", "uninstall", "-y"] + heavy_pkgs, capture_output=True, text=True, timeout=20)
            if res.returncode == 0 and "Successfully uninstalled" in (res.stdout or ""):
                _log(f"Pruned unneeded heavy packages via {py_cmd}")
                break
        except Exception:
            pass

    # 4. Safe Git Garbage Collection strictly on e_profile
    git_bin = shutil.which("git") or "/usr/bin/git"
    g_dir = base_dir / ".git"
    git_size_mb = 0.0
    if g_dir.is_dir():
        for lock_file in g_dir.rglob("*.lock"):
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Unconditionally wipe ALL orphaned tmp_* pack files from interrupted/failed repacks
        pack_dir = g_dir / "objects" / "pack"
        if pack_dir.is_dir():
            for tmp_pack in pack_dir.glob("tmp_*"):
                try:
                    tmp_pack.unlink(missing_ok=True)
                    _log(f"Evicted orphaned pack artifact: {tmp_pack.name}")
                except Exception:
                    pass
        (g_dir / "gc.log").unlink(missing_ok=True)

        obj_dir = g_dir / "objects"
        if obj_dir.is_dir():
            for obj in obj_dir.glob("*/*"):
                try:
                    if obj.is_file() and obj.stat().st_size == 0:
                        obj.unlink(missing_ok=True)
                except Exception:
                    pass

        shutil.rmtree(base_dir / ".git" / "modules", ignore_errors=True)
        (base_dir / ".gitmodules").unlink(missing_ok=True)

        # Measure current git directory size
        try:
            total_b = sum(f.stat().st_size for f in g_dir.rglob("*") if f.is_file())
            git_size_mb = round(total_b / (1024 * 1024), 1)
        except Exception:
            pass

        # Expire reflogs and prune dead objects without running quota-risky repack
        for cmd_args in [
            ["reflog", "expire", "--expire=now", "--all"],
            ["prune", "--expire=now"]
        ]:
            try:
                subprocess.run([git_bin, "-c", "credential.helper="] + cmd_args, cwd=str(base_dir), capture_output=True, timeout=25)
            except Exception:
                pass
        _log(f"Pruned git reflogs & unreachable objects (current .git: {git_size_mb} MB)")

        # Enforce shallow history boundary if .git exceeds 30 MB
        if git_size_mb > 30.0:
            token = ""
            token_file = base_dir / "gethub_token.txt"
            if not token_file.exists():
                token_file = home / "gethub_token.txt"
            if token_file.exists():
                try:
                    token = token_file.read_text(encoding="utf-8").strip()
                except Exception:
                    pass
            if not token:
                token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GIT_TOKEN", "").strip()
            auth_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/E-profile.git" if token else "origin"
            try:
                subprocess.run([git_bin, "-c", "credential.helper=", "fetch", "--depth", "1", auth_url, "main"], cwd=str(base_dir), capture_output=True, timeout=35)
                subprocess.run([git_bin, "-c", "credential.helper=", "reflog", "expire", "--expire=now", "--all"], cwd=str(base_dir), capture_output=True, timeout=20)
                subprocess.run([git_bin, "-c", "credential.helper=", "prune", "--expire=now"], cwd=str(base_dir), capture_output=True, timeout=20)
                _log(f"Enforced --depth 1 shallow boundary on .git (reduced from {git_size_mb} MB)")
            except Exception as e:
                report["errors"].append(f"Git shallow truncate error: {e}")

    # 5. Ephemeral workspace & bytecode caches
    pyc_count = 0
    for p in base_dir.rglob("__pycache__"):
        if p.is_dir():
            try:
                shutil.rmtree(p, ignore_errors=True)
                pyc_count += 1
            except Exception:
                pass
    for p in base_dir.rglob("*.py[co]"):
        try:
            p.unlink(missing_ok=True)
            pyc_count += 1
        except Exception:
            pass
    if pyc_count > 0:
        _log(f"Cleared {pyc_count} cached bytecode objects")

    temp_docs = base_dir / "cache" / "temp_docs"
    if temp_docs.is_dir():
        doc_count = 0
        for f in temp_docs.glob("*.json"):
            try:
                f.unlink(missing_ok=True)
                doc_count += 1
            except Exception:
                pass
        if doc_count > 0:
            _log(f"Evicted {doc_count} transient story cache files from cache/temp_docs")

    shutil.rmtree(base_dir / ".backup", ignore_errors=True)

    # 6. Verify and protect AGY CLI binary
    agy_bin = _find_agy_binary()
    if agy_bin:
        try:
            if not os.access(str(agy_bin), os.X_OK):
                os.chmod(str(agy_bin), 0o755)
            _log(f"Verified AGY CLI binary preserved & executable: {agy_bin}")
        except Exception:
            pass

    # 7. Quota status measurement
    try:
        usage = shutil.disk_usage(str(home))
        used_mb = (usage.total - usage.free) / (1024 * 1024)
        total_mb = usage.total / (1024 * 1024)
        pct = (used_mb / total_mb) * 100 if total_mb else 0
        report["disk_used_mb"] = round(used_mb, 1)
        report["disk_total_mb"] = round(total_mb, 1)
        report["disk_pct"] = round(pct, 1)
        if verbose:
            print(f"📊 Storage Status: {round(used_mb, 1)} MB used / {round(total_mb, 1)} MB total ({round(pct, 1)}%)")
    except Exception:
        pass

    return report


def trigger_background_sync(base_dir: Path, force: bool = False) -> None:
    """Spawns git sync in a detached background daemon thread so incoming WSGI
    requests are served immediately in milliseconds without blocking on network I/O.
    Enforces a persistent cooldown to prevent infinite restart loops.
    """
    global _SYNC_THREAD_STARTED
    if not is_production_server() and not force:
        return

    sync_stamp_file = base_dir / "cache" / ".last_sync_timestamp"
    if not force:
        try:
            if sync_stamp_file.exists():
                last_ts = float(sync_stamp_file.read_text(encoding="utf-8").strip())
                if (time.time() - last_ts) < 14400:  # 4-hour cooldown
                    return
        except Exception:
            pass

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
    """Synchronizes repository with origin/main."""
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

        # Record attempt timestamp immediately to prevent retry hammering
        try:
            sync_stamp_file = base_dir / "cache" / ".last_sync_timestamp"
            sync_stamp_file.parent.mkdir(parents=True, exist_ok=True)
            sync_stamp_file.write_text(str(time.time()), encoding="utf-8")
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

        # Capture commit hash BEFORE pulling
        old_ok, old_head, _ = _git(["rev-parse", "HEAD"])
        old_head = old_head.strip() if old_ok else ""

        pull_ok, out, err = _git(["pull", "--depth", "1", authenticated_url, "main", "--no-edit", "--allow-unrelated-histories", "-X", "ours"], timeout=35)
        if not pull_ok:
            _git(["merge", "--abort"])
            _git(["fetch", "--depth", "1", authenticated_url, "main", "--prune"], timeout=25)
            _git(["merge", "origin/main", "--no-edit", "-m", "Auto-merge main updates", "-X", "ours"], timeout=20)

        # Immediate shallow maintenance to prevent pack and reflog bloat
        _git(["reflog", "expire", "--expire=now", "--all"], timeout=15)
        _git(["prune", "--expire=now"], timeout=15)

        # Capture commit hash AFTER pulling (locale-independent)
        new_ok, new_head, _ = _git(["rev-parse", "HEAD"])
        new_head = new_head.strip() if new_ok else ""

        has_new_commits = bool(old_head and new_head and old_head != new_head)

        import devcore_locator
        devcore_dir = devcore_locator.find_devcore(require_marker=False) or devcore_locator.default_clone_target()

        if token:
            devcore_auth_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/DevCore.git"
            if not devcore_dir.is_dir():
                target_clone = base_dir.parent / "DevCore"
                _git(["clone", "--depth", "1", devcore_auth_url, str(target_clone)], timeout=45)
            elif (devcore_dir / ".git").is_dir():
                def _git_dc(args, timeout=30):
                    cmd = [git_bin, "-c", "credential.helper="] + args
                    try:
                        res = subprocess.run(cmd, cwd=str(devcore_dir), capture_output=True, text=True, timeout=timeout)
                        return res.returncode == 0
                    except Exception:
                        return False
                _git_dc(["pull", devcore_auth_url, "main", "--no-edit", "-X", "ours"], timeout=30)

        post_sync_script = base_dir / "post_sync.py"
        if post_sync_script.exists():
            py_bin = shutil.which("python3") or sys.executable
            try:
                subprocess.run([py_bin, str(post_sync_script)], cwd=str(base_dir), capture_output=True, text=True, timeout=25)
            except Exception:
                pass

        # CRITICAL ANTI-LOOP GUARD: Only touch WSGI file if new commits were actually pulled!
        # Touching WSGI on "Already up to date" causes an infinite restart loop that crashes PythonAnywhere!
        if has_new_commits:
            try:
                req_file = base_dir / "requirements.txt"
                if req_file.exists():
                    py_bin = shutil.which("python3.9") or shutil.which("python3") or sys.executable
                    subprocess.run([py_bin, "-m", "pip", "install", "--no-cache-dir", "--user", "-r", str(req_file)], capture_output=True, timeout=40)
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
import time
import datetime


def _format_size(num_bytes: int) -> str:
    """Formats bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}" if unit != 'B' else f"{num_bytes} B"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def _load_dotenv_raw(base_dir: Path) -> dict:
    """Zero-dependency parser for .env files."""
    env_vars = {}
    env_path = base_dir / ".env"
    if env_path.is_file():
        try:
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
        except Exception:
            pass
    return env_vars


def _parse_bootstrap_request(environ):
    """Zero-dependency parser for incoming WSGI requests (Query, Form, JSON, Multipart)."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    query_string = environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(query_string)

    post_params = {}
    content_type = environ.get("CONTENT_TYPE", "")
    
    if method == "POST":
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
            if 0 < content_length < 25 * 1024 * 1024:
                raw_body = environ["wsgi.input"].read(content_length)
                if "application/json" in content_type.lower():
                    try:
                        parsed_json = json.loads(raw_body.decode("utf-8", errors="replace"))
                        if isinstance(parsed_json, dict):
                            for k, v in parsed_json.items():
                                post_params[k] = [str(v)] if not isinstance(v, list) else [str(x) for x in v]
                    except Exception:
                        pass
                elif "multipart/form-data" in content_type.lower() and "boundary=" in content_type:
                    boundary = content_type.split("boundary=")[1].strip().strip('"').encode("utf-8")
                    parts = raw_body.split(b"--" + boundary)
                    for part in parts:
                        if not part or part == b"--\r\n" or part == b"--":
                            continue
                        if b"\r\n\r\n" in part:
                            header_bytes, body_bytes = part.split(b"\r\n\r\n", 1)
                            body_clean = body_bytes.rstrip(b"\r\n")
                            header_text = header_bytes.decode("utf-8", errors="replace")
                            if 'name="' in header_text:
                                field_name = header_text.split('name="')[1].split('"')[0]
                                if 'filename="' in header_text:
                                    fname = header_text.split('filename="')[1].split('"')[0]
                                    post_params["upload_filename"] = [fname]
                                    post_params["upload_content"] = [body_clean.decode("utf-8", errors="replace")]
                                else:
                                    post_params[field_name] = [body_clean.decode("utf-8", errors="replace")]
                else:
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
    """Authenticates admin access across env variables, .env, master keys, tokens, and profiles."""
    token = (
        (post_params.get("admin_token") or [""])[0].strip()
        or (post_params.get("token") or [""])[0].strip()
        or (post_params.get("secret") or [""])[0].strip()
        or (post_params.get("key") or [""])[0].strip()
        or (params.get("admin_token") or [""])[0].strip()
        or (params.get("token") or [""])[0].strip()
        or (params.get("secret") or [""])[0].strip()
        or (params.get("key") or [""])[0].strip()
    )

    auth_header = environ.get("HTTP_AUTHORIZATION", "")
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
        if bearer:
            token = bearer
    elif environ.get("HTTP_X_BREAKGLASS_SECRET"):
        token = environ.get("HTTP_X_BREAKGLASS_SECRET", "").strip()
    elif environ.get("HTTP_X_SYNC_SECRET"):
        token = environ.get("HTTP_X_SYNC_SECRET", "").strip()
    elif environ.get("HTTP_X_ADMIN_KEY"):
        token = environ.get("HTTP_X_ADMIN_KEY", "").strip()

    cookie_hash = cookies.get("bootstrap_admin_session", "").strip()

    admin_hashes = {}
    env_vars = _load_dotenv_raw(base_dir)

    profiles_path = base_dir / "profiles.json"
    if profiles_path.exists():
        try:
            data = json.loads(profiles_path.read_text(encoding="utf-8"))
            for h, u in data.get("data", {}).items():
                if u.get("is_admin", False):
                    admin_hashes[h] = u.get("username", "Administrator")
        except Exception:
            pass

    for s in [os.environ.get("SYNC_SECRET", "").strip(), env_vars.get("SYNC_SECRET", "").strip()]:
        if s:
            admin_hashes[hashlib.sha256(s.encode("utf-8")).hexdigest()] = "Root (SYNC_SECRET)"

    for s in [os.environ.get("ADMIN_KEY", "").strip(), env_vars.get("ADMIN_KEY", "").strip()]:
        if s:
            admin_hashes[hashlib.sha256(s.encode("utf-8")).hexdigest()] = "Root (ADMIN_KEY)"

    for s in [os.environ.get("BREAK_GLASS_KEY", "").strip(), env_vars.get("BREAK_GLASS_KEY", "").strip()]:
        if s:
            admin_hashes[hashlib.sha256(s.encode("utf-8")).hexdigest()] = "Root (BREAK_GLASS_KEY)"

    for s in [os.environ.get("GITHUB_TOKEN", "").strip(), env_vars.get("GITHUB_TOKEN", "").strip(), env_vars.get("GIT_TOKEN", "").strip()]:
        if s and not s.startswith("INSERT_"):
            admin_hashes[hashlib.sha256(s.encode("utf-8")).hexdigest()] = "Root (GitHub Token)"

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


def _safe_resolve_path(base_dir: Path, rel_path: str) -> tuple[Path | None, str]:
    """Safely resolves path within base_dir, home, or /var/www while blocking traversal escapes."""
    clean = rel_path.strip().lstrip("/")
    if not clean:
        return base_dir.resolve(), ""
    raw_path = Path(rel_path.strip())
    if raw_path.is_absolute():
        target = raw_path.resolve()
    else:
        target = (base_dir / clean).resolve()

    base_resolved = base_dir.resolve()
    home_resolved = Path.home().resolve()
    allowed = False
    try:
        if base_resolved in target.parents or target == base_resolved:
            allowed = True
        elif home_resolved in target.parents or target == home_resolved:
            allowed = True
        elif Path("/var/www").resolve() in target.parents or target == Path("/var/www").resolve():
            allowed = True
        elif Path("/var/log").resolve() in target.parents or target == Path("/var/log").resolve():
            allowed = True
    except Exception:
        pass
    if not allowed:
        return None, "Access denied: Path resolves outside authorized directories."
    return target, ""


def _read_server_logs(base_dir: Path, max_lines: int = 150) -> str:
    """Reads latest error and application logs from system and repository."""
    log_candidates = []
    for p in Path("/var/log").glob("*error*.log"):
        log_candidates.append(p)
    for p in Path("/var/www").glob("*error*.log"):
        log_candidates.append(p)
    logs_dir = base_dir / "logs"
    if logs_dir.is_dir():
        for p in logs_dir.glob("*.log"):
            log_candidates.append(p)
    for p in [base_dir / "server_stdout.log", base_dir / "server_stderr.log"]:
        if p.exists():
            log_candidates.append(p)

    out = []
    for lp in log_candidates:
        try:
            if lp.is_file() and lp.stat().st_size > 0:
                lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
                recent = "\n".join(lines[-max_lines:])
                out.append(f"=== [LOG: {lp} (last {min(len(lines), max_lines)} lines)] ===\n{recent}\n")
        except Exception:
            pass
    if not out:
        return "No persistent log files located in /var/log, /var/www, or local logs/ directory."
    return "\n".join(out)


def _gather_system_status(base_dir: Path, error_msg: str, traceback_str: str, missing_pkgs: dict, missing_files: dict) -> dict:
    """Collects server telemetry, git status, and storage quotas."""
    git_bin = shutil.which("git") or "/usr/bin/git"
    git_branch = "unknown"
    git_commit = "unknown"
    git_status = "clean"
    try:
        res = subprocess.run([git_bin, "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(base_dir), capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            git_branch = res.stdout.strip()
        res = subprocess.run([git_bin, "rev-parse", "HEAD"], cwd=str(base_dir), capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            git_commit = res.stdout.strip()
        res = subprocess.run([git_bin, "status", "-s"], cwd=str(base_dir), capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            git_status = res.stdout.strip() or "clean"
    except Exception:
        pass

    quota = {"used_mb": 0.0, "total_mb": 0.0, "pct": 0.0}
    try:
        usage = shutil.disk_usage(str(Path.home()))
        used_mb = (usage.total - usage.free) / (1024 * 1024)
        total_mb = usage.total / (1024 * 1024)
        quota["used_mb"] = round(used_mb, 1)
        quota["total_mb"] = round(total_mb, 1)
        quota["pct"] = round((used_mb / total_mb) * 100, 1) if total_mb else 0.0
    except Exception:
        pass

    agy_bin = _find_agy_binary()
    agy_data = {
        "installed": agy_bin is not None,
        "path": str(agy_bin) if agy_bin else "Not Found (~/.local/bin/agy)",
        "size_mb": round(agy_bin.stat().st_size / (1024 * 1024), 1) if agy_bin else 0.0,
        "executable": os.access(str(agy_bin), os.X_OK) if agy_bin else False,
        "status_label": "Ready / Active" if agy_bin else "Offline / Missing"
    }

    return {
        "status": "ok",
        "server_state": "crashed" if error_msg else "healthy_standby",
        "error_msg": error_msg or "None (Clean State)",
        "traceback": traceback_str or "No unhandled exceptions recorded.",
        "git": {
            "branch": git_branch,
            "commit": git_commit,
            "status": git_status
        },
        "quota": quota,
        "agy": agy_data,
        "python_version": sys.version,
        "missing_packages": missing_pkgs or {},
        "missing_files": missing_files or {}
    }


def generate_secure_holding_html(login_failed: bool = False, alert_text: str = "") -> bytes:
    """Renders a zero-disclosure maintenance page with an admin authentication gate."""
    alert_html = ""
    if login_failed or alert_text:
        msg = alert_text or "Access denied. Invalid administrator token."
        alert_html = f'''
        <div style="background: rgba(255, 0, 85, 0.15); border: 1px solid #ff0055; color: #ff80a0; padding: 10px 14px; margin-bottom: 18px; border-radius: 6px; font-size: 13px; text-align: left;">
            {msg}
        </div>
        '''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Unavailable | Break-Glass Gate</title>
    <style>
        :root {{
            --bg: #090a10;
            --card-bg: rgba(18, 20, 29, 0.95);
            --text-main: #f0f3f8;
            --text-muted: #8b949e;
            --accent-cyan: #00e5ff;
            --accent-magenta: #ff0055;
            --border-color: rgba(255, 255, 255, 0.08);
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --mono: "SFMono-Regular", Consolas, Menlo, monospace;
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
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
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
        h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 10px; }}
        p {{ color: var(--text-muted); font-size: 14px; line-height: 1.6; margin-bottom: 24px; }}
        .divider {{ height: 1px; background: var(--border-color); margin: 24px 0; }}
        .admin-section {{ text-align: left; }}
        .admin-label {{ display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }}
        .input-group {{ display: flex; gap: 8px; }}
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
        }}
        input[type="password"]:focus {{ border-color: var(--accent-cyan); }}
        button {{
            background: linear-gradient(135deg, #00b4d8 0%, #0077b6 100%);
            border: none;
            border-radius: 6px;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            padding: 10px 16px;
        }}
        button:hover {{ opacity: 0.92; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="status-badge">System Status: Standby</div>
        <h1>Service Temporarily Unavailable</h1>
        <p>The application server is undergoing maintenance or recovery. Please check back shortly.</p>
        <div class="divider"></div>
        <div class="admin-section">
            <span class="admin-label">Break-Glass Administrator Terminal Access</span>
            {alert_html}
            <form method="POST">
                <input type="hidden" name="action" value="status">
                <div class="input-group">
                    <input type="password" name="admin_token" placeholder="Enter Admin Secret / Key / PIN" autocomplete="off" required>
                    <button type="submit">Unlock Console</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>"""
    return html.encode("utf-8")


def generate_breakglass_dashboard_html(
    status_data: dict,
    active_tab: str = "diag",
    current_path: str = "",
    file_list: list = None,
    editor_file: str = "",
    editor_content: str = "",
    terminal_cmd: str = "",
    terminal_output: str = "",
    server_logs: str = "",
    alert_msg: str = "",
    alert_type: str = "info",
    admin_name: str = "Administrator",
    agy_output: str = ""
) -> bytes:
    """Generates the full Break-Glass Disaster Recovery & Management Web Dashboard."""
    file_list = file_list or []
    
    alert_html = ""
    if alert_msg:
        border_col = "#00e5ff" if alert_type == "success" else ("#ff0055" if alert_type == "error" else "#ffb703")
        bg_col = "rgba(0, 229, 255, 0.12)" if alert_type == "success" else ("rgba(255, 0, 85, 0.15)" if alert_type == "error" else "rgba(255, 183, 3, 0.12)")
        alert_html = f'''
        <div style="background:{bg_col}; border:1px solid {border_col}; color:#fff; padding:12px 18px; margin-bottom:20px; border-radius:6px; font-size:13px; font-weight:600; display:flex; justify-content:space-between; align-items:center;">
            <span>{alert_msg}</span>
            <span style="font-size:11px; opacity:0.8; text-transform:uppercase; letter-spacing:1px;">{alert_type}</span>
        </div>
        '''

    err = status_data.get("error_msg", "None")
    tb = status_data.get("traceback", "None")
    git_info = status_data.get("git", {})
    quota = status_data.get("quota", {})
    agy_info = status_data.get("agy", {})
    missing_pkgs = status_data.get("missing_packages", {})
    missing_files = status_data.get("missing_files", {})
    is_crashed = status_data.get("server_state") == "crashed"

    pkg_html = ""
    for p, s in missing_pkgs.items():
        cls = "missing" if "MISSING" in s else "found"
        pkg_html += f"<li class='{cls}'>[{s}] {p}</li>"
    if not pkg_html:
        pkg_html = "<li class='found'>All pre-flight packages verified.</li>"

    file_chk_html = ""
    for f, s in missing_files.items():
        cls = "missing" if "MISSING" in s else "found"
        file_chk_html += f"<li class='{cls}'>[{s}] {f}</li>"
    if not file_chk_html:
        file_chk_html = "<li class='found'>All pre-flight paths verified.</li>"

    norm_path = current_path.replace("\\", "/").strip("/")
    path_parts = norm_path.split("/") if norm_path else []
    breadcrumbs = '<a href="?action=ls&path=" class="breadcrumb-link">~ [root]</a>'
    accum = ""
    for part in path_parts:
        if part:
            accum += "/" + part
            breadcrumbs += f' / <a href="?action=ls&path={accum.lstrip("/")}" class="breadcrumb-link">{part}</a>'

    parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ("" if len(path_parts) == 1 else None)
    parent_row = ""
    if parent_path is not None:
        parent_row = f'''
        <tr>
            <td colspan="4" style="padding: 8px 12px; background: rgba(255,255,255,0.02);">
                <a href="?action=ls&path={parent_path}" style="color:var(--cyan); text-decoration:none; font-weight:bold;">📁 .. (Up to Parent Directory)</a>
            </td>
        </tr>
        '''

    file_rows = ""
    for item in file_list:
        name = item.get("name", "")
        rel = item.get("rel_path", "").replace("\\", "/")
        is_d = item.get("is_dir", False)
        sz = _format_size(item.get("size", 0)) if not is_d else "-"
        icon = "📁" if is_d else "📄"
        
        if is_d:
            action_link = f'<a href="?action=ls&path={rel}" style="color:var(--cyan); text-decoration:none; font-weight:600;">{name}/</a>'
            delete_btn = ""
        else:
            action_link = f'<a href="?action=cat&path={rel}" style="color:#f0f3f8; text-decoration:none;">{name}</a>'
            delete_btn = f'''
            <form method="POST" style="display:inline; margin:0;" onsubmit="return confirm('Permanently delete {name}?');">
                <input type="hidden" name="action" value="rm">
                <input type="hidden" name="path" value="{rel}">
                <button type="submit" class="btn-icon" title="Delete">🗑️</button>
            </form>
            '''

        file_rows += f'''
        <tr>
            <td style="padding: 6px 12px;">{icon} {action_link}</td>
            <td style="padding: 6px 12px; font-family:var(--mono); font-size:12px; color:var(--text-muted);">{sz}</td>
            <td style="padding: 6px 12px; font-family:var(--mono); font-size:12px; color:var(--text-muted);">{item.get("mtime_str", "-")}</td>
            <td style="padding: 6px 12px; text-align:right;">
                {f'<a href="?action=cat&path={rel}" class="btn-sm">Edit</a>' if not is_d else ''}
                {delete_btn}
            </td>
        </tr>
        '''
    if not file_rows and parent_row == "":
        file_rows = '<tr><td colspan="4" style="padding:14px; text-align:center; color:var(--text-muted);">Directory is empty.</td></tr>'

    editor_display = "none" if not editor_file else "block"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BREAK-GLASS | EMERGENCY CONSOLE</title>
    <style>
        :root {{
            --bg: #090a10;
            --panel: rgba(18, 20, 29, 0.95);
            --text-main: #f0f3f8;
            --text-muted: #8b949e;
            --cyan: #00e5ff;
            --magenta: #ff0055;
            --amber: #ffb703;
            --border: rgba(255, 255, 255, 0.08);
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: radial-gradient(circle at 50% 10%, #151928 0%, var(--bg) 90%);
            color: var(--text-main);
            font-family: var(--font);
            min-height: 100vh;
            padding: 24px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: var(--panel);
            border: 1px solid {'var(--magenta)' if is_crashed else 'var(--cyan)'};
            border-radius: 10px;
            padding: 28px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.7);
        }}
        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border);
            padding: 12px 18px;
            border-radius: 6px;
            margin-bottom: 22px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 700;
            font-size: 15px;
            letter-spacing: 0.5px;
        }}
        .status-pill {{
            padding: 4px 10px;
            border-radius: 999px;
            font-family: var(--mono);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            background: {'rgba(255, 0, 85, 0.15)' if is_crashed else 'rgba(0, 229, 255, 0.15)'};
            color: {'var(--magenta)' if is_crashed else 'var(--cyan)'};
            border: 1px solid {'var(--magenta)' if is_crashed else 'var(--cyan)'};
        }}
        .quick-actions {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .btn {{
            background: rgba(0, 229, 255, 0.12);
            border: 1px solid var(--cyan);
            color: var(--cyan);
            padding: 7px 14px;
            border-radius: 4px;
            font-family: var(--mono);
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn:hover {{ background: var(--cyan); color: #000; }}
        .btn-magenta {{
            background: rgba(255, 0, 85, 0.12);
            border-color: var(--magenta);
            color: var(--magenta);
        }}
        .btn-magenta:hover {{ background: var(--magenta); color: #fff; }}
        .btn-amber {{
            background: rgba(255, 183, 3, 0.12);
            border-color: var(--amber);
            color: var(--amber);
        }}
        .btn-amber:hover {{ background: var(--amber); color: #000; }}
        .btn-sm {{
            padding: 3px 8px;
            font-size: 11px;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid var(--border);
            color: var(--text-main);
            border-radius: 4px;
            text-decoration: none;
            cursor: pointer;
        }}
        .btn-sm:hover {{ border-color: var(--cyan); color: var(--cyan); }}
        .btn-icon {{
            background: none;
            border: none;
            cursor: pointer;
            padding: 2px 6px;
            opacity: 0.7;
        }}
        .btn-icon:hover {{ opacity: 1.0; }}
        .tabs {{
            display: flex;
            gap: 4px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }}
        .tab-btn {{
            padding: 10px 18px;
            background: none;
            border: none;
            border-bottom: 2px solid transparent;
            color: var(--text-muted);
            font-family: var(--mono);
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
        }}
        .tab-btn.active {{
            color: var(--cyan);
            border-bottom-color: var(--cyan);
            background: rgba(0, 229, 255, 0.04);
        }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .box {{
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 18px;
            margin-bottom: 20px;
        }}
        .box.error {{ border-color: var(--magenta); background: rgba(255, 0, 85, 0.05); }}
        h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: 1px; color: var(--cyan); margin-bottom: 12px; }}
        pre {{
            background: #050608;
            padding: 14px;
            border-radius: 4px;
            border: 1px solid #222;
            overflow-x: auto;
            color: #a3be8c;
            font-family: var(--mono);
            font-size: 12px;
            line-height: 1.45;
        }}
        .terminal-screen {{
            background: #030406;
            color: #5af78e;
            border: 1px solid #333;
            min-height: 240px;
            max-height: 500px;
            overflow-y: auto;
            padding: 16px;
            font-family: var(--mono);
            font-size: 13px;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            color: var(--text-muted);
            font-family: var(--mono);
            font-size: 11px;
            text-transform: uppercase;
        }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.03); }}
        .breadcrumbs {{
            padding: 8px 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 4px;
            margin-bottom: 14px;
            font-family: var(--mono);
            font-size: 13px;
        }}
        .breadcrumb-link {{ color: var(--cyan); text-decoration: none; }}
        .breadcrumb-link:hover {{ text-decoration: underline; }}
        textarea.editor {{
            width: 100%;
            height: 380px;
            background: #050608;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: #f0f3f8;
            font-family: var(--mono);
            font-size: 13px;
            line-height: 1.45;
            padding: 14px;
            outline: none;
            resize: vertical;
        }}
        textarea.editor:focus {{ border-color: var(--cyan); }}
        input[type="text"], input[type="file"] {{
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: #fff;
            font-family: var(--mono);
            font-size: 13px;
            padding: 8px 12px;
            outline: none;
        }}
        input[type="text"]:focus {{ border-color: var(--cyan); }}
        ul {{ list-style-type: square; padding-left: 20px; font-size: 13px; line-height: 1.6; }}
        li.missing {{ color: var(--magenta); }}
        li.found {{ color: var(--cyan); }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border);
            padding: 14px;
            border-radius: 6px;
        }}
        .metric-val {{ font-family: var(--mono); font-size: 16px; font-weight: 700; color: #fff; margin-top: 4px; }}
        .metric-label {{ font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <div class="brand">
                <span>🛡️ BREAK-GLASS RECOVERY CONSOLE</span>
                <span class="status-pill">{'SERVER CRASHED' if is_crashed else 'STANDBY / ACTIVE'}</span>
            </div>
            <div class="quick-actions">
                <form method="POST" style="margin:0;">
                    <input type="hidden" name="action" value="pull_and_restart">
                    <button type="submit" class="btn" title="Git Pull origin/main & Reload">⚡ 2-Way Git Sync</button>
                </form>
                <form method="POST" style="margin:0;">
                    <input type="hidden" name="action" value="agy_diagnose">
                    <input type="hidden" name="tab" value="agy">
                    <button type="submit" class="btn" style="border-color:var(--cyan); color:var(--cyan);" title="Run AI Diagnostics using AGY CLI">🤖 AGY Diagnose</button>
                </form>
                <form method="POST" style="margin:0;" onsubmit="return confirm('Rollback to HEAD~1 and reload?');">
                    <input type="hidden" name="action" value="rollback">
                    <button type="submit" class="btn btn-magenta" title="Instant Git Revert">⏪ Git Rollback (HEAD~1)</button>
                </form>
                <form method="POST" style="margin:0;">
                    <input type="hidden" name="action" value="cleanup">
                    <button type="submit" class="btn btn-amber" title="Free Disk Quota on PythonAnywhere">🧹 Quota Rescue</button>
                </form>
                <form method="POST" style="margin:0;">
                    <input type="hidden" name="action" value="reload">
                    <button type="submit" class="btn" title="Touch WSGI file to trigger fresh worker start">🔄 WSGI Reload</button>
                </form>
                <form method="POST" style="margin:0;">
                    <input type="hidden" name="action" value="logout">
                    <button type="submit" class="btn btn-magenta" title="Lock Console">🔒 Lock</button>
                </form>
            </div>
        </div>

        {alert_html}

        <div class="tabs">
            <a href="?action=status&tab=diag" class="tab-btn {'active' if active_tab == 'diag' else ''}">[01] DIAGNOSTICS</a>
            <a href="?action=ls&tab=files&path={norm_path}" class="tab-btn {'active' if active_tab == 'files' else ''}">[02] FILE EXPLORER & EDITOR</a>
            <a href="?action=status&tab=terminal" class="tab-btn {'active' if active_tab == 'terminal' else ''}">[03] EMERGENCY TERMINAL</a>
            <a href="?action=logs&tab=logs" class="tab-btn {'active' if active_tab == 'logs' else ''}">[04] RECOVERY LOGS</a>
            <a href="?action=agy_view&tab=agy" class="tab-btn {'active' if active_tab == 'agy' else ''}">[05] AGY AI COPILOT</a>
        </div>

        <!-- TAB 1: DIAGNOSTICS -->
        <div class="tab-content {'active' if active_tab == 'diag' else ''}">
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">Git Branch / Commit</div>
                    <div class="metric-val">{git_info.get("branch", "unknown")} @ {git_info.get("commit", "unknown")[:8]}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Disk Storage Quota</div>
                    <div class="metric-val">{quota.get("used_mb", 0)} MB / {quota.get("total_mb", 0)} MB ({quota.get("pct", 0)}%)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">AGY AI Copilot</div>
                    <div class="metric-val" style="color:{'var(--cyan)' if agy_info.get('installed') else 'var(--magenta)'};">
                        {'ONLINE (READY)' if agy_info.get('installed') else 'OFFLINE'}
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Operator Tier</div>
                    <div class="metric-val" style="color:var(--cyan);">{admin_name}</div>
                </div>
            </div>

            <div class="box {'error' if is_crashed else ''}">
                <h2>[01.1] Server Status</h2>
                <p style="font-size:14px; margin-bottom:12px;"><strong>Message:</strong> {err}</p>
                <h2>[01.2] Crash Traceback Log</h2>
                <pre>{tb}</pre>
            </div>

            <div class="box">
                <h2>[01.3] Dependency Integrity Check</h2>
                <ul>{pkg_html}</ul>
                <h2 style="margin-top:16px;">[01.4] File System Structure Check</h2>
                <ul>{file_chk_html}</ul>
            </div>
        </div>

        <!-- TAB 2: FILE EXPLORER & EDITOR -->
        <div class="tab-content {'active' if active_tab == 'files' else ''}">
            <div class="breadcrumbs">{breadcrumbs}</div>

            <!-- In-Browser Editor -->
            <div id="editor-panel" class="box" style="display:{editor_display};">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h2>Editing: <span style="color:#fff;">{editor_file}</span></h2>
                    <a href="?action=ls&path={norm_path}" class="btn-sm">Close Editor</a>
                </div>
                <form method="POST">
                    <input type="hidden" name="action" value="write">
                    <input type="hidden" name="path" value="{editor_file}">
                    <textarea name="content" class="editor" spellcheck="false">{editor_content}</textarea>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
                        <label style="font-size:12px; font-family:var(--mono); color:var(--text-muted); cursor:pointer;">
                            <input type="checkbox" name="reload" value="true" checked> Automatically touch WSGI configuration on save
                        </label>
                        <button type="submit" class="btn">💾 Save & Deploy File</button>
                    </div>
                </form>
            </div>

            <!-- File Table -->
            <div class="box">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px;">
                    <h2>Directory Contents</h2>
                    <!-- File Upload Form -->
                    <form method="POST" enctype="multipart/form-data" style="display:flex; gap:8px; align-items:center; margin:0;">
                        <input type="hidden" name="action" value="write">
                        <input type="hidden" name="path" value="{norm_path}">
                        <input type="file" name="upload_file" required style="font-size:11px;">
                        <button type="submit" class="btn-sm">Upload File</button>
                    </form>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Size</th>
                            <th>Modified</th>
                            <th style="text-align:right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {parent_row}
                        {file_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 3: EMERGENCY TERMINAL -->
        <div class="tab-content {'active' if active_tab == 'terminal' else ''}">
            <div class="box">
                <h2>Emergency Command Execution</h2>
                <form method="POST" style="margin-bottom:14px;">
                    <input type="hidden" name="action" value="exec">
                    <input type="hidden" name="tab" value="terminal">
                    <div style="display:flex; gap:8px;">
                        <input type="text" name="cmd" placeholder="e.g. git status -s, pip list, python3 server.py" value="{terminal_cmd}" style="flex:1;" required autocomplete="off">
                        <button type="submit" class="btn">Run Command</button>
                    </div>
                </form>

                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px;">
                    <span style="font-size:11px; color:var(--text-muted); align-self:center;">Quick Presets:</span>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="git status -s"><button type="submit" class="btn-sm">git status -s</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="git diff HEAD~1"><button type="submit" class="btn-sm">git diff HEAD~1</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="git log -n 5 --oneline"><button type="submit" class="btn-sm">git log -5</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="python3 -m pip list"><button type="submit" class="btn-sm">pip list</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="df -h ~"><button type="submit" class="btn-sm">df -h ~</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="python3 -c 'import server; print(\"server ok\")'"><button type="submit" class="btn-sm">test server.py</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="agy --help"><button type="submit" class="btn-sm" style="color:var(--cyan); border-color:var(--cyan);">agy --help</button></form>
                    <form method="POST" style="display:inline; margin:0;"><input type="hidden" name="action" value="exec"><input type="hidden" name="tab" value="terminal"><input type="hidden" name="cmd" value="agy --version"><button type="submit" class="btn-sm" style="color:var(--cyan); border-color:var(--cyan);">agy --version</button></form>
                </div>

                <div class="terminal-screen">{terminal_output or "$ Ready for emergency commands."}</div>
            </div>
        </div>

        <!-- TAB 4: RECOVERY LOGS -->
        <div class="tab-content {'active' if active_tab == 'logs' else ''}">
            <div class="box">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h2>System & WSGI Error Logs</h2>
                    <form method="POST" style="margin:0;"><input type="hidden" name="action" value="logs"><input type="hidden" name="tab" value="logs"><button type="submit" class="btn-sm">Refresh Logs</button></form>
                </div>
                <pre style="max-height: 500px; overflow-y: auto;">{server_logs or "No logs fetched yet. Click 'Refresh Logs' above."}</pre>
            </div>
        </div>

        <!-- TAB 5: AGY AI COPILOT & DIAGNOSTICS -->
        <div class="tab-content {'active' if active_tab == 'agy' else ''}">
            <div class="box">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                    <div>
                        <h2>🤖 Antigravity AI Copilot & Diagnostics (AGY)</h2>
                        <p style="font-size:12px; color:var(--text-muted); margin-top:3px;">
                            Autonomous diagnostic reasoning engine powered by Google Antigravity CLI binary.
                        </p>
                    </div>
                    <span class="status-pill" style="border-color:{'var(--cyan)' if agy_info.get('installed') else 'var(--magenta)'}; color:{'var(--cyan)' if agy_info.get('installed') else 'var(--magenta)'};">
                        {'● AGY ONLINE' if agy_info.get('installed') else '○ AGY OFFLINE'}
                    </span>
                </div>

                <div class="metric-grid" style="margin-bottom:16px;">
                    <div class="metric-card">
                        <div class="metric-label">AGY Binary Location</div>
                        <div class="metric-val" style="font-size:13px; word-break:break-all;">{agy_info.get('path', 'Not found')}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Binary Size / Executable</div>
                        <div class="metric-val">{agy_info.get('size_mb', 0.0)} MB / {'Yes (0755)' if agy_info.get('executable') else 'No'}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Engine Status</div>
                        <div class="metric-val" style="color:var(--cyan);">{agy_info.get('status_label', 'Ready')}</div>
                    </div>
                </div>

                <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border); border-radius:6px; padding:16px; margin-bottom:18px;">
                    <div style="font-size:12px; font-weight:700; text-transform:uppercase; color:var(--cyan); margin-bottom:10px;">One-Click AI Diagnostics</div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <form method="POST" style="margin:0;">
                            <input type="hidden" name="action" value="agy_diagnose">
                            <input type="hidden" name="tab" value="agy">
                            <button type="submit" class="btn" style="border-color:var(--cyan); color:var(--cyan);">🩺 Diagnose Server Crash</button>
                        </form>
                        <form method="POST" style="margin:0;">
                            <input type="hidden" name="action" value="agy_cmd">
                            <input type="hidden" name="tab" value="agy">
                            <input type="hidden" name="cmd" value="agy --help">
                            <button type="submit" class="btn-sm">agy --help</button>
                        </form>
                        <form method="POST" style="margin:0;">
                            <input type="hidden" name="action" value="agy_cmd">
                            <input type="hidden" name="tab" value="agy">
                            <input type="hidden" name="cmd" value="agy --version">
                            <button type="submit" class="btn-sm">agy --version</button>
                        </form>
                        <form method="POST" style="margin:0;">
                            <input type="hidden" name="action" value="agy_cmd">
                            <input type="hidden" name="tab" value="agy">
                            <input type="hidden" name="cmd" value="agy doctor">
                            <button type="submit" class="btn-sm">agy doctor</button>
                        </form>
                        <form method="POST" style="margin:0;">
                            <input type="hidden" name="action" value="agy_prompt">
                            <input type="hidden" name="tab" value="agy">
                            <input type="hidden" name="prompt" value="Inspect git status, recent commits, and storage quota. Recommend optimizations.">
                            <button type="submit" class="btn-sm">Audit Git & Storage</button>
                        </form>
                    </div>
                </div>

                <form method="POST" style="margin-bottom:16px;">
                    <input type="hidden" name="action" value="agy_prompt">
                    <input type="hidden" name="tab" value="agy">
                    <label style="display:block; font-size:12px; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:6px;">Custom AGY Diagnostic Prompt / Instruction</label>
                    <div style="display:flex; gap:8px;">
                        <input type="text" name="prompt" placeholder="Ask AGY to diagnose an error, inspect server code, or recommend a fix..." style="flex:1; background:rgba(0,0,0,0.5); border:1px solid var(--border); color:#fff; padding:10px 14px; border-radius:4px; font-size:13px;" required>
                        <button type="submit" class="btn" style="border-color:var(--cyan); color:var(--cyan); white-space:nowrap;">Run with AGY 🚀</button>
                    </div>
                </form>

                <div style="font-size:12px; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:6px;">AGY Execution Console Output</div>
                <div class="terminal-screen" style="white-space:pre-wrap; max-height:450px; overflow-y:auto;">{agy_output or "$ Antigravity Agent ready. Run a preset or submit an instruction above."}</div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html.encode("utf-8")


def render_bootstrap_response(
    environ,
    start_response,
    base_dir: Path,
    error_msg: str = "",
    traceback_str: str = "",
    missing_pkgs: dict = None,
    missing_files: dict = None,
    is_explicit_breakglass: bool = False
):
    """Guards break-glass operations behind administrator authentication with dual JSON API and Web UI."""
    global _FLASK_APP
    method, params, post_params, cookies = _parse_bootstrap_request(environ)
    
    # Detect JSON request
    accept_hdr = environ.get("HTTP_ACCEPT", "").lower()
    content_type_hdr = environ.get("CONTENT_TYPE", "").lower()
    is_json = (
        "application/json" in accept_hdr
        or "application/json" in content_type_hdr
        or (params.get("format") or [""])[0] == "json"
        or (post_params.get("format") or [""])[0] == "json"
    )

    action = (post_params.get("action") or params.get("action") or ["status"])[0].strip()
    tab = (post_params.get("tab") or params.get("tab") or ["diag"])[0].strip()

    # Handle Logout
    if action == "logout":
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Set-Cookie", "bootstrap_admin_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax")
        ]
        if is_json:
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Set-Cookie", "bootstrap_admin_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax")
            ]
            start_response("200 OK", headers)
            return [json.dumps({"status": "ok", "message": "Logged out successfully"}).encode("utf-8")]
        start_response("200 OK", headers)
        return [generate_secure_holding_html(alert_text="Session closed. Console locked.")]

    # Authenticate
    is_admin, admin_name, set_cookie_header = authenticate_bootstrap_admin(base_dir, params, post_params, cookies, environ)

    if not is_admin:
        token_attempted = bool(
            post_params.get("admin_token") or post_params.get("token") or post_params.get("secret") or post_params.get("key")
            or params.get("admin_token") or params.get("token") or params.get("secret") or params.get("key")
            or environ.get("HTTP_AUTHORIZATION")
        )
        if is_json:
            headers = [("Content-Type", "application/json; charset=utf-8")]
            start_response("401 Unauthorized", headers)
            return [json.dumps({
                "status": "error",
                "message": "Authentication required. Provide valid token via Authorization header or ?token=...",
                "code": 401
            }).encode("utf-8")]

        headers = [("Content-Type", "text/html; charset=utf-8")]
        start_response("200 OK", headers)
        return [generate_secure_holding_html(login_failed=token_attempted)]

    # Response headers for authenticated admin
    resp_headers = []
    if set_cookie_header:
        resp_headers.append(set_cookie_header)

    status_data = _gather_system_status(base_dir, error_msg, traceback_str, missing_pkgs, missing_files)

    # 1. Action: STATUS
    if action == "status":
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps(status_data).encode("utf-8")]
        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab=tab, admin_name=admin_name)]

    # 2. Action: LS (List Directory)
    elif action == "ls":
        req_path = (post_params.get("path") or params.get("path") or [""])[0].strip()
        target, err_path = _safe_resolve_path(base_dir, req_path)
        if not target or not target.exists():
            msg = err_path or f"Path does not exist: {req_path}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("404 Not Found", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="error", admin_name=admin_name)]

        if target.is_file():
            action = "cat"
        else:
            entries = []
            try:
                for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    is_d = item.is_dir()
                    sz = item.stat().st_size if not is_d else 0
                    mtime = int(item.stat().st_mtime)
                    mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    try:
                        rel = str(item.relative_to(base_dir)).replace("\\", "/")
                    except Exception:
                        rel = str(item).replace("\\", "/")
                    entries.append({
                        "name": item.name,
                        "rel_path": rel,
                        "is_dir": is_d,
                        "size": sz,
                        "size_human": _format_size(sz) if not is_d else "-",
                        "mtime": mtime,
                        "mtime_str": mtime_str
                    })
            except Exception:
                pass

            curr_rel = str(target.relative_to(base_dir)).replace("\\", "/") if base_dir in target.parents else ""
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("200 OK", resp_headers)
                return [json.dumps({"status": "ok", "path": curr_rel, "entries": entries}).encode("utf-8")]

            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", current_path=curr_rel, file_list=entries, admin_name=admin_name)]

    # 3. Action: CAT / READ / VIEW
    if action in ["cat", "read", "view"]:
        req_path = (post_params.get("path") or params.get("path") or [""])[0].strip()
        target, err_path = _safe_resolve_path(base_dir, req_path)
        if not target or not target.is_file():
            msg = err_path or f"File not found: {req_path}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("404 Not Found", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="error", admin_name=admin_name)]

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as read_err:
            content = f"[Error reading file: {read_err}]"

        rel = str(target.relative_to(base_dir)).replace("\\", "/") if base_dir in target.parents else str(target)
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok", "path": rel, "size": len(content), "content": content}).encode("utf-8")]

        parent_dir = target.parent
        dir_entries = []
        try:
            for item in sorted(parent_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                is_d = item.is_dir()
                sz = item.stat().st_size if not is_d else 0
                mtime_str = datetime.datetime.fromtimestamp(int(item.stat().st_mtime)).strftime("%Y-%m-%d %H:%M")
                try:
                    r_p = str(item.relative_to(base_dir)).replace("\\", "/")
                except Exception:
                    r_p = str(item).replace("\\", "/")
                dir_entries.append({
                    "name": item.name, "rel_path": r_p, "is_dir": is_d,
                    "size": sz, "size_human": _format_size(sz) if not is_d else "-", "mtime_str": mtime_str
                })
        except Exception:
            pass

        parent_rel = str(parent_dir.relative_to(base_dir)).replace("\\", "/") if base_dir in parent_dir.parents else ""
        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(
            status_data, active_tab="files", current_path=parent_rel, file_list=dir_entries,
            editor_file=rel, editor_content=content, admin_name=admin_name
        )]

    # 4. Action: WRITE / PUT / SAVE
    elif action in ["write", "put", "save"]:
        req_path = (post_params.get("path") or params.get("path") or [""])[0].strip()
        upload_fname = (post_params.get("upload_filename") or [""])[0].strip()
        content = (post_params.get("upload_content") or post_params.get("content") or [""])[0]

        if upload_fname:
            req_path = f"{req_path.rstrip('/')}/{upload_fname}" if req_path else upload_fname

        target, err_path = _safe_resolve_path(base_dir, req_path)
        if not target:
            msg = err_path or "Invalid target destination"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("403 Forbidden", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="error", admin_name=admin_name)]

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            backed_up = False
            if target.is_file():
                bak_dir = base_dir / "backups" / "break_glass"
                bak_dir.mkdir(parents=True, exist_ok=True)
                bak_file = bak_dir / f"{target.name}.{int(time.time())}.bak"
                shutil.copy2(target, bak_file)
                backed_up = True

            tmp_target = target.with_suffix(f".tmp.{os.getpid()}")
            tmp_target.write_text(content, encoding="utf-8")
            tmp_target.replace(target)

            reload_req = (post_params.get("reload") or params.get("reload") or ["false"])[0].lower() in ["true", "1"]
            reloaded = False
            if reload_req or target.suffix == ".py":
                wsgi_dir = Path("/var/www/")
                if wsgi_dir.exists():
                    for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                        try:
                            wsgi_file.touch()
                            reloaded = True
                        except Exception:
                            pass
                _FLASK_APP = None

            rel = str(target.relative_to(base_dir)).replace("\\", "/") if base_dir in target.parents else str(target)
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("200 OK", resp_headers)
                return [json.dumps({
                    "status": "ok", "message": f"Successfully written {len(content)} bytes to {rel}",
                    "path": rel, "bytes": len(content), "backed_up": backed_up, "reloaded": reloaded
                }).encode("utf-8")]

            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(
                status_data, active_tab="files", current_path=str(target.parent.relative_to(base_dir)).replace("\\", "/"),
                editor_file=rel, editor_content=content, alert_msg=f"Successfully updated and deployed {rel}",
                alert_type="success", admin_name=admin_name
            )]
        except Exception as write_err:
            msg = f"Failed to write file: {write_err}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("500 Internal Error", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="error", admin_name=admin_name)]

    # 5. Action: RM / DELETE
    elif action in ["rm", "delete"]:
        req_path = (post_params.get("path") or params.get("path") or [""])[0].strip()
        target, err_path = _safe_resolve_path(base_dir, req_path)
        if not target or not target.exists():
            msg = err_path or f"Target does not exist: {req_path}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("404 Not Found", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="error", admin_name=admin_name)]

        try:
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            msg = f"Successfully removed {target.name}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("200 OK", resp_headers)
                return [json.dumps({"status": "ok", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="success", admin_name=admin_name)]
        except Exception as rm_err:
            msg = f"Failed to remove target: {rm_err}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("500 Internal Error", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="files", alert_msg=msg, alert_type="error", admin_name=admin_name)]

    # 6. Action: EXEC / CMD
    elif action in ["exec", "cmd"]:
        cmd = (post_params.get("cmd") or params.get("cmd") or [""])[0].strip()
        if not cmd:
            msg = "No command provided to execute."
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("400 Bad Request", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="terminal", alert_msg=msg, alert_type="error", admin_name=admin_name)]

        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        if "PATH" in env and local_bin not in env["PATH"]:
            env["PATH"] = f"{local_bin}:{env['PATH']}"
        elif "PATH" not in env:
            env["PATH"] = local_bin

        cmd_to_run = cmd.strip()
        if cmd_to_run.startswith("agy ") or cmd_to_run == "agy":
            parts = cmd_to_run.split(maxsplit=1)
            sub_arg = parts[1].strip() if len(parts) > 1 else ""
            std_cmds = {"agent", "agents", "models", "mcp", "plugin", "plugins", "help", "--help", "-h", "version", "--version", "update", "changelog", "doctor"}
            if sub_arg and not sub_arg.startswith("-") and sub_arg.split()[0] not in std_cmds:
                cmd_to_run = f"agy --dangerously-skip-permissions --print {shlex.quote(sub_arg)}"
            elif not sub_arg:
                cmd_to_run = "agy --help"

        try:
            res = subprocess.run(cmd_to_run, shell=True, cwd=str(base_dir), capture_output=True, text=True, timeout=60, env=env)
            out = f"$ {cmd}\n[Exit Code: {res.returncode}]\n"
            if res.stdout:
                out += f"--- STDOUT ---\n{res.stdout}\n"
            if res.stderr:
                out += f"--- STDERR ---\n{res.stderr}\n"

            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("200 OK", resp_headers)
                return [json.dumps({
                    "status": "ok", "cmd": cmd, "returncode": res.returncode,
                    "stdout": res.stdout, "stderr": res.stderr
                }).encode("utf-8")]

            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(
                status_data, active_tab="terminal", terminal_cmd=cmd, terminal_output=out, admin_name=admin_name
            )]
        except Exception as exec_err:
            msg = f"Command failed: {exec_err}"
            if is_json:
                resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
                start_response("500 Internal Error", resp_headers)
                return [json.dumps({"status": "error", "message": msg}).encode("utf-8")]
            resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [generate_breakglass_dashboard_html(status_data, active_tab="terminal", terminal_cmd=cmd, terminal_output=msg, alert_msg=msg, alert_type="error", admin_name=admin_name)]

    # 7. Action: ROLLBACK
    elif action == "rollback":
        git_bin = shutil.which("git") or "/usr/bin/git"
        g_dir = base_dir / ".git"
        if g_dir.is_dir():
            for lk in g_dir.rglob("*.lock"):
                try: lk.unlink(missing_ok=True)
                except Exception: pass
        res = subprocess.run([git_bin, "reset", "--hard", "HEAD~1"], cwd=str(base_dir), capture_output=True, text=True, timeout=25)
        
        wsgi_dir = Path("/var/www/")
        if wsgi_dir.exists():
            for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                try: wsgi_file.touch()
                except Exception: pass
        _FLASK_APP = None

        out = res.stdout + res.stderr
        status_data = _gather_system_status(base_dir, error_msg, traceback_str, missing_pkgs, missing_files)
        msg = f"Git rollback completed. Rolled back 1 commit to {status_data['git']['commit'][:8]}."
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok", "message": msg, "output": out, "git": status_data["git"]}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="diag", alert_msg=msg, alert_type="success", admin_name=admin_name)]

    # 8. Action: SYNC / PULL_AND_RESTART
    elif action in ["pull_and_restart", "sync"]:
        auto_sync_git(base_dir, force=True)
        try:
            import importlib
            if "server" in sys.modules:
                importlib.reload(sys.modules["server"])
            from server import app as flask_app
            _FLASK_APP = flask_app
            if not is_json and not is_explicit_breakglass:
                return flask_app(environ, start_response)
        except Exception as retry_err:
            error_msg = f"Post-pull reload failed: {retry_err}"
            traceback_str = traceback.format_exc()

        status_data = _gather_system_status(base_dir, error_msg, traceback_str, missing_pkgs, missing_files)
        msg = "Git 2-way synchronization executed."
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok", "message": msg, "error": error_msg, "git": status_data["git"]}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="diag", alert_msg=msg, alert_type="success" if not error_msg else "error", admin_name=admin_name)]

    # 9. Action: CLEANUP
    elif action == "cleanup":
        report = cleanup_storage(base_dir, verbose=False)
        status_data = _gather_system_status(base_dir, error_msg, traceback_str, missing_pkgs, missing_files)
        msg = f"Storage cleanup complete. Freed disk quota. Current used: {status_data['quota']['used_mb']} MB ({status_data['quota']['pct']}%)"
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok", "message": msg, "report": report, "quota": status_data["quota"]}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="diag", alert_msg=msg, alert_type="success", admin_name=admin_name)]

    # 10. Action: RELOAD
    elif action == "reload":
        wsgi_dir = Path("/var/www/")
        touched = 0
        if wsgi_dir.exists():
            for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                try:
                    wsgi_file.touch()
                    touched += 1
                except Exception:
                    pass
        _FLASK_APP = None
        msg = f"WSGI server reload triggered ({touched} configuration files touched)."
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok", "message": msg, "touched": touched}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="diag", alert_msg=msg, alert_type="success", admin_name=admin_name)]

    # 11. Action: LOGS
    elif action == "logs":
        logs_content = _read_server_logs(base_dir)
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok", "logs": logs_content}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="logs", server_logs=logs_content, admin_name=admin_name)]

    # 12. Action: AGY VIEW
    elif action == "agy_view":
        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="agy", admin_name=admin_name)]

    # 13. Action: AGY DIAGNOSE
    elif action == "agy_diagnose":
        crash_summary = (
            f"Server State: {status_data.get('server_state')}\n"
            f"Error: {status_data.get('error_msg')}\n"
            f"Traceback:\n{status_data.get('traceback')}\n"
            f"Git Branch/Commit: {status_data.get('git', {}).get('branch')} @ {status_data.get('git', {}).get('commit')}\n"
            f"Quota: {status_data.get('quota', {}).get('used_mb')}MB used ({status_data.get('quota', {}).get('pct')}%)\n"
            f"Missing Packages: {status_data.get('missing_packages')}\n"
            f"Missing Files: {status_data.get('missing_files')}"
        )
        prompt = (
            f"You are the Antigravity Diagnostic Agent for Michael Robberts' portfolio server running on PythonAnywhere.\n"
            f"The server is in Break-Glass recovery mode with the following diagnostics:\n"
            f"```\n{crash_summary}\n```\n"
            f"Analyze the root cause and provide:\n"
            f"1. Clear explanation of why the crash occurred.\n"
            f"2. Precise file and code corrections needed.\n"
            f"3. Concrete commands to restore normal operation."
        )
        code, stdout, stderr = _run_agy_command(base_dir, ["--print", prompt], timeout=90)
        out = stdout or stderr or f"[AGY returned code {code} with no output]"
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok" if code == 0 else "error", "output": out, "exit_code": code}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="agy", agy_output=out, admin_name=admin_name)]

    # 14. Action: AGY RUN COMMAND
    elif action == "agy_cmd":
        cmd_str = (post_params.get("cmd") or params.get("cmd") or ["agy --help"])[0].strip()
        code, stdout, stderr = _run_agy_command(base_dir, cmd_str, timeout=60)
        out = f"$ {cmd_str}\n[Exit Code: {code}]\n"
        if stdout: out += f"--- STDOUT ---\n{stdout}\n"
        if stderr: out += f"--- STDERR ---\n{stderr}\n"
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok" if code == 0 else "error", "output": out, "exit_code": code}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="agy", agy_output=out, admin_name=admin_name)]

    # 15. Action: AGY PROMPT
    elif action == "agy_prompt":
        user_prompt = (post_params.get("prompt") or params.get("prompt") or [""])[0].strip()
        if not user_prompt:
            user_prompt = "Diagnose system health and recommend any optimizations."
        code, stdout, stderr = _run_agy_command(base_dir, ["--print", user_prompt], timeout=90)
        out = f"$ agy --print \"{user_prompt}\"\n[Exit Code: {code}]\n\n"
        out += (stdout or stderr or "[No output returned from agy]")
        if is_json:
            resp_headers.append(("Content-Type", "application/json; charset=utf-8"))
            start_response("200 OK", resp_headers)
            return [json.dumps({"status": "ok" if code == 0 else "error", "output": out, "exit_code": code}).encode("utf-8")]

        resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
        start_response("200 OK", resp_headers)
        return [generate_breakglass_dashboard_html(status_data, active_tab="agy", agy_output=out, admin_name=admin_name)]

    # Fallback to status
    resp_headers.append(("Content-Type", "text/html; charset=utf-8"))
    start_response("200 OK", resp_headers)
    return [generate_breakglass_dashboard_html(status_data, active_tab="diag", admin_name=admin_name)]

# The main WSGI application entry point
def application(environ, start_response):
    global _FLASK_APP
    try:
        # Step 1: Set working directory and prioritize path
        BASE_DIR = Path(__file__).resolve().parent
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        os.chdir(str(BASE_DIR))

        # Enforce storage limits and prevent quota bloat at startup
        auto_enforce_storage_limits(BASE_DIR)

        # Step 1.5: Break-Glass Emergency Interceptor (accessible anytime on demand)
        req_path = environ.get("PATH_INFO", "")
        req_query = environ.get("QUERY_STRING", "")
        if req_path in ["/__breakglass__", "/__emergency__", "/emergency"] or "breakglass=1" in req_query:
            return render_bootstrap_response(
                environ, start_response, BASE_DIR,
                "", "", {}, {}, is_explicit_breakglass=True
            )
        # Fast path: Serve healthy Flask app immediately with zero filesystem overhead
        if _FLASK_APP is None:
            try:
                import sync_mod
                from server import app as flask_app
                _FLASK_APP = flask_app
            except Exception:
                pass

        if _FLASK_APP is not None:
            trigger_background_sync(BASE_DIR)
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

            auto_enforce_storage_limits(BASE_DIR, force=True)
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
    parser.add_argument('--cleanup', '--quota-rescue', action='store_true', help='Execute storage cleanup and quota recovery')
    parser.add_argument('--sync', '--pull', action='store_true', help='Force git sync and quota optimization')
    parser.add_argument('--status', action='store_true', help='Print disk quota and dependency health status')
    args = parser.parse_args()

    BASE_DIR = Path(__file__).resolve().parent

    if args.cleanup:
        print("🚀 Starting automated storage recovery and quota optimization...")
        res = cleanup_storage(BASE_DIR, verbose=True)
        print("✅ Storage optimization completed.")
        sys.exit(0)

    if args.sync:
        print("🚀 Forcing git sync and storage optimization...")
        print("1. Freeing disk quota before pull...")
        cleanup_storage(BASE_DIR, verbose=True)
        print("2. Pulling repository updates...")
        auto_sync_git(BASE_DIR, force=True)
        print("3. Finalizing storage state...")
        cleanup_storage(BASE_DIR, verbose=False)
        print("✅ Sync and cleanup completed successfully.")
        sys.exit(0)

    if args.status:
        home = Path.home()
        try:
            usage = shutil.disk_usage(str(home))
            used_mb = (usage.total - usage.free) / (1024 * 1024)
            total_mb = usage.total / (1024 * 1024)
            print(f"📊 Disk Usage: {used_mb:.1f} MB / {total_mb:.1f} MB ({(used_mb/total_mb)*100:.1f}%)")
        except Exception as e:
            print(f"Could not read disk usage: {e}")
        sys.exit(0)

    if args.undo:
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
        
    print("This is a WSGI bootstrap file. Use --cleanup to recover quota, --sync to pull updates, or --undo to rollback renames.")
