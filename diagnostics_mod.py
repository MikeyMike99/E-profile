import os
import sys
import time
import shutil
import platform
import subprocess
from pathlib import Path
from flask import Blueprint, session, jsonify, request, flash, redirect, url_for

diagnostics_bp = Blueprint('diagnostics', __name__)

_DIAGNOSTICS_CACHE = {
    "timestamp": 0,
    "data": None
}
CACHE_TTL_SECONDS = 60

def _get_dir_size_mb(path, timeout=2.0):
    try:
        p_str = str(path)
        res = subprocess.run(["du", "-sm", p_str], capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.split()[0])
    except Exception:
        pass
    
    # Python fallback if du fails or is unavailable
    try:
        total_bytes = 0
        file_count = 0
        for root, _, files in os.walk(path):
            for f in files:
                file_count += 1
                if file_count > 500:
                    break
                fp = os.path.join(root, f)
                try:
                    total_bytes += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    continue
            if file_count > 500:
                break
        return round(total_bytes / (1024 * 1024), 2)
    except Exception:
        return 0.0

def _scan_largest_files(home_dir, limit=12, max_depth=3):
    large_files = []
    scanned_count = 0
    skip_dirs = {'.git', 'node_modules', '__pycache__'}
    
    try:
        for root, dirs, files in os.walk(home_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            try:
                rel_parts = Path(root).relative_to(home_dir).parts
                if len(rel_parts) > max_depth:
                    dirs.clear()
                    continue
            except ValueError:
                continue

            for f in files:
                scanned_count += 1
                if scanned_count > 1500:
                    break
                fp = Path(root) / f
                try:
                    if not fp.is_symlink():
                        st = fp.stat()
                        sz_mb = st.st_size / (1024 * 1024)
                        if sz_mb >= 1.0:
                            large_files.append({
                                "name": f,
                                "rel_path": str(fp.relative_to(home_dir)),
                                "size_mb": round(sz_mb, 2),
                                "mtime": time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))
                            })
                except (PermissionError, FileNotFoundError, OSError):
                    continue
            if scanned_count > 1500:
                break
    except Exception:
        pass

    large_files.sort(key=lambda x: x["size_mb"], reverse=True)
    return large_files[:limit]

def get_system_diagnostic_summary(force_refresh=False):
    now = time.time()
    if not force_refresh and _DIAGNOSTICS_CACHE["data"] and (now - _DIAGNOSTICS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return _DIAGNOSTICS_CACHE["data"]

    home_dir = Path.home()
    root_dir = Path(__file__).resolve().parent

    # 1. Host Quota & Filesystem Usage
    try:
        disk_stats = shutil.disk_usage(home_dir)
        disk_total_mb = round(disk_stats.total / (1024 * 1024), 1)
        disk_used_mb = round(disk_stats.used / (1024 * 1024), 1)
        disk_free_mb = round(disk_stats.free / (1024 * 1024), 1)
        disk_pct = round((disk_stats.used / disk_stats.total) * 100, 1) if disk_stats.total > 0 else 0.0
    except Exception:
        disk_total_mb, disk_used_mb, disk_free_mb, disk_pct = 0.0, 0.0, 0.0, 0.0

    # 2. Top Directories in User Home
    top_dirs = []
    total_home_scanned_mb = 0.0
    try:
        for item in home_dir.iterdir():
            if item.is_dir() and not item.is_symlink():
                sz = _get_dir_size_mb(item, timeout=1.5)
                if sz >= 0.1:
                    top_dirs.append({
                        "name": item.name,
                        "path": str(item),
                        "size_mb": round(sz, 1)
                    })
                    total_home_scanned_mb += sz
        top_dirs.sort(key=lambda x: x["size_mb"], reverse=True)
    except Exception:
        pass

    # 3. Cache Sub-Breakdown
    pip_cache_path = home_dir / ".cache" / "pip"
    pip_cache_mb = _get_dir_size_mb(pip_cache_path, timeout=1.0) if pip_cache_path.exists() else 0.0

    venv_path = home_dir / ".virtualenvs"
    venv_mb = _get_dir_size_mb(venv_path, timeout=1.0) if venv_path.exists() else 0.0

    git_path = root_dir / ".git"
    git_mb = _get_dir_size_mb(git_path, timeout=1.0) if git_path.exists() else 0.0

    # 4. Top Largest Files
    largest_files = _scan_largest_files(home_dir, limit=10, max_depth=3)

    # 5. Antigravity CLI (agy) Detection
    checked_paths = [
        "PATH (which agy)",
        str(home_dir / ".local" / "bin" / "agy"),
        "/usr/local/bin/agy",
        str(home_dir / ".local" / "bin" / "agy_real")
    ]
    agy_path = shutil.which("agy")
    if not agy_path:
        for p in [home_dir / ".local" / "bin" / "agy", Path("/usr/local/bin/agy"), home_dir / ".local" / "bin" / "agy_real"]:
            if p.exists() and os.access(str(p), os.X_OK):
                agy_path = str(p)
                break

    agy_version = None
    if agy_path:
        try:
            res = subprocess.run([agy_path, "--version"], capture_output=True, text=True, timeout=2.0)
            agy_version = res.stdout.strip() or res.stderr.strip()
        except Exception as e:
            agy_version = f"Error querying version: {e}"

    # 6. Installed Python Packages (via importlib.metadata)
    packages = []
    has_antigravity_pkg = False
    try:
        from importlib.metadata import distributions
        for d in distributions():
            pkg_name = d.metadata.get("Name")
            if pkg_name:
                low_name = pkg_name.lower()
                if "antigravity" in low_name:
                    has_antigravity_pkg = True
                packages.append({
                    "name": pkg_name,
                    "version": d.version or "Unknown",
                    "summary": (d.metadata.get("Summary") or "").strip()
                })
        packages.sort(key=lambda x: x["name"].lower())
    except Exception:
        # Fallback to pip list if importlib.metadata fails
        try:
            res = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                import json
                raw_pkgs = json.loads(res.stdout)
                for rp in raw_pkgs:
                    pname = rp.get("name", "")
                    if "antigravity" in pname.lower():
                        has_antigravity_pkg = True
                    packages.append({
                        "name": pname,
                        "version": rp.get("version", ""),
                        "summary": ""
                    })
        except Exception:
            pass

    # 7. System Info
    is_venv = (sys.prefix != sys.base_prefix)
    sys_info = {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "is_virtualenv": is_venv,
        "os_platform": f"{platform.system()} {platform.release()}",
        "home_directory": str(home_dir),
        "last_scanned": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
    }

    result = {
        "storage": {
            "home_dir": str(home_dir),
            "disk_total_mb": disk_total_mb,
            "disk_used_mb": disk_used_mb,
            "disk_free_mb": disk_free_mb,
            "disk_pct": disk_pct,
            "home_consumed_mb": round(total_home_scanned_mb, 1),
            "top_directories": top_dirs,
            "cache_breakdown": {
                "pip_cache_mb": pip_cache_mb,
                "virtualenvs_mb": venv_mb,
                "git_repo_mb": git_mb
            },
            "largest_files": largest_files
        },
        "agy": {
            "installed": bool(agy_path),
            "binary_path": agy_path,
            "version": agy_version,
            "has_pip_package": has_antigravity_pkg,
            "checked_paths": checked_paths
        },
        "packages": {
            "count": len(packages),
            "pkg_list": packages,
            "has_antigravity": has_antigravity_pkg
        },
        "system": sys_info
    }

    _DIAGNOSTICS_CACHE["timestamp"] = now
    _DIAGNOSTICS_CACHE["data"] = result
    return result

def purge_pip_cache():
    home_dir = Path.home()
    pip_dir = home_dir / ".cache" / "pip"
    freed_mb = 0.0

    if pip_dir.exists():
        freed_mb = _get_dir_size_mb(pip_dir, timeout=1.0)
        try:
            shutil.rmtree(pip_dir, ignore_errors=True)
        except Exception as e:
            return False, f"Failed to delete directory: {e}", 0.0

    # Also try native pip cache purge
    try:
        subprocess.run([sys.executable, "-m", "pip", "cache", "purge"], capture_output=True, timeout=3.0)
    except Exception:
        pass

    # Invalidate cache
    _DIAGNOSTICS_CACHE["timestamp"] = 0
    _DIAGNOSTICS_CACHE["data"] = None

    return True, f"Successfully purged pip cache. Reclaimed approximately {freed_mb} MB.", freed_mb

# --- BLUEPRINT ROUTES ---

@diagnostics_bp.route('/admin/api/diagnostics', methods=['GET'])
def api_diagnostics():
    if not session.get('admin', False):
        return jsonify({"error": "Unauthorized"}), 403
    force = request.args.get('refresh', '').lower() in ('1', 'true', 'yes')
    data = get_system_diagnostic_summary(force_refresh=force)
    return jsonify(data)

@diagnostics_bp.route('/admin/api/purge_pip_cache', methods=['POST'])
def api_purge_pip():
    if not session.get('admin', False):
        return jsonify({"error": "Unauthorized"}), 403
    success, msg, freed_mb = purge_pip_cache()
    return jsonify({
        "success": success,
        "message": msg,
        "freed_mb": freed_mb
    })
