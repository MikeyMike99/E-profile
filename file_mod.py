import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from config import Config

config = Config()
# Prefix: /api/projects/explorer
file_manager_bp = Blueprint('file_manager', __name__)

BASE_SAFE_ZONE = config.CONTENT_DIR.resolve() 

def get_safe_path(project_name, subpath=""):
    """Ensures file operations stay within the project 'jail'."""
    if project_name == "root":
        jail_root = Path.cwd().resolve()
    else:
        jail_root = (BASE_SAFE_ZONE / "engines" / project_name).resolve()
    
    if not jail_root.exists():
        jail_root.mkdir(parents=True, exist_ok=True)

    clean_subpath = subpath.lstrip('/')
    requested_path = (jail_root / clean_subpath).resolve()
    
    # Path Traversal Protection
    if jail_root not in requested_path.parents and requested_path != jail_root:
        return jail_root, jail_root
    
    return requested_path, jail_root

# --- ROUTES ---

@file_manager_bp.route('/<name>/') # Added trailing slash to prevent redirect 404s
def explorer_view(name):
    """Matches: /api/projects/explorer/<name>/"""
    return render_template('file_manager.html', project_name=name)

@file_manager_bp.route('/get_structure', methods=['GET'])
def get_structure():
    """Fetches directory tree and metadata for the UI."""
    project_name = request.args.get('project', 'root')
    subpath = request.args.get('path', '')
    
    target, _ = get_safe_path(project_name, subpath)
    
    if not target.exists():
        return jsonify({"error": "PATH_OFFLINE", "tabs": [], "nodes": []}), 404

    try:
        items = list(target.iterdir())
        tabs = [i.name for i in items if i.is_dir() and i.name not in ["__pycache__", ".git", "venv"]]
        
        nodes = []
        for i in items:
            if i.is_file():
                stats = i.stat()
                loc = 0
                if i.suffix in ['.py', '.js', '.html', '.css', '.txt', '.md']:
                    try:
                        if stats.st_size < 1024 * 1024:
                            with open(i, 'rb') as f:
                                loc = sum(1 for _ in f)
                    except:
                        loc = "ERR"

                nodes.append({
                    "name": i.name,
                    "ext": i.suffix.lower(),
                    "size": f"{stats.st_size / 1024:.1f} KB",
                    "modified": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    "loc": loc
                })
        
        return jsonify({
            "project": project_name,
            "current_path": subpath,
            "tabs": sorted(tabs),
            "nodes": sorted(nodes, key=lambda x: x['name'])
        })
    except Exception as e:
        return jsonify({"error": str(e), "tabs": [], "nodes": []}), 500

@file_manager_bp.route('/terminal', methods=['POST'])
def terminal_command():
    """Executes specifically whitelisted deployment commands."""
    if not session.get('is_admin'):
        return jsonify({"output": "ACCESS_DENIED"}), 403

    data = request.get_json() or {}
    raw_cmd = data.get('command', '').strip()
    project = data.get('project', 'root')
    path = data.get('path', '')

    target, _ = get_safe_path(project, path)
    output_log = ""
    
    # Load token for auto-auth
    token = ""
    token_file = config.ROOT_DIR / "gethub_token.txt"
    if token_file.exists():
        token = token_file.read_text().strip()
        
    remote_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/ECHOS_OF_THE_WORLD.git" if token else "origin"

    def run_safe_cmd(cmd_list):
        nonlocal output_log
        try:
            exe_path = shutil.which(cmd_list[0])
            if exe_path:
                cmd_list[0] = exe_path
            
            process = subprocess.run(
                cmd_list,
                cwd=str(target),
                capture_output=True,
                text=True,
                timeout=30
            )
            # Mask token in output
            safe_cmd_list = [c.replace(token, '***') if token else c for c in cmd_list]
            output_log += f"$ {' '.join(safe_cmd_list)}\n"
            
            stdout = process.stdout.replace(token, '***') if process.stdout and token else process.stdout
            stderr = process.stderr.replace(token, '***') if process.stderr and token else process.stderr
            
            if stdout: output_log += stdout + "\n"
            if stderr: output_log += stderr + "\n"
            return process.returncode == 0
        except Exception as e:
            err_msg = str(e).replace(token, '***') if token else str(e)
            output_log += f"EXCEPTION: {err_msg}\n"
            return False

    if raw_cmd == 'setup -get':
        success = run_safe_cmd(['git', 'pull', remote_url, 'main'])
        if success:
            output_log += "\n[System] Pull successful. Attempting to reload PythonAnywhere server...\n"
            try:
                wsgi_dir = Path("/var/www/")
                if wsgi_dir.exists():
                    reloaded = False
                    for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                        wsgi_file.touch()
                        output_log += f"[System] Touched {wsgi_file.name}\n"
                        reloaded = True
                    if not reloaded:
                        output_log += "[System] Warning: No *_wsgi.py files found in /var/www/\n"
                else:
                    output_log += "[System] Warning: /var/www/ not found. Are you on PythonAnywhere?\n"
            except Exception as e:
                output_log += f"[System] Error touching WSGI: {e}\n"
        
        return jsonify({"output": output_log})

    elif raw_cmd.startswith('setup -get new'):
        parts = raw_cmd.split()
        repo = "MikeyMike99/ECHOS_OF_THE_WORLD"
        if len(parts) > 3:
            repo = parts[3]
            
        repo_url = f"https://github.com/{repo}.git"
        output_log += f"[System] Configuring new repository origin: {repo_url}\n"
        
        # 1. Update remote (remove existing if present, then add new)
        run_safe_cmd(['git', 'remote', 'remove', 'origin'])
        run_safe_cmd(['git', 'remote', 'add', 'origin', repo_url])
        
        # 2. Fetch and Pull
        run_safe_cmd(['git', 'fetch', 'origin'])
        run_safe_cmd(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'])
        
        return jsonify({"output": output_log})

    # Catch-all for non-whitelisted commands
    return jsonify({
        "output": f"\n[SECURITY LOCKDOWN ACTIVE]\nUnrecognized command: '{raw_cmd}'.\nOnly 'setup -get' and 'setup -get new [repo]' are allowed in production.\n"
    })

@file_manager_bp.route('/git_sync', methods=['POST'])
def git_sync():
    """Two-way sync: Guaranteed token injection for pull and push."""
    if not session.get('is_admin'):
        return jsonify({"output": "ACCESS_DENIED"}), 403

    target = config.ROOT_DIR
    output_log = "[System] Starting 2-Way Git Sync...\n"
    
    # Load token for auto-auth
    token = ""
    token_file = target / "gethub_token.txt"
    if token_file.exists():
        token = token_file.read_text().strip()
        
    remote_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/ECHOS_OF_THE_WORLD.git" if token else "origin"

    def run_safe_cmd(cmd_list):
        nonlocal output_log
        try:
            exe_path = shutil.which(cmd_list[0])
            if exe_path:
                cmd_list[0] = exe_path
            
            process = subprocess.run(
                cmd_list,
                cwd=str(target),
                capture_output=True,
                text=True,
                timeout=45
            )
            # Mask token in output logs
            safe_cmd_list = [c.replace(token, '***') if token else c for c in cmd_list]
            output_log += f"$ {' '.join(safe_cmd_list)}\n"
            
            stdout = process.stdout.replace(token, '***') if process.stdout and token else process.stdout
            stderr = process.stderr.replace(token, '***') if process.stderr and token else process.stderr
            
            if stdout: output_log += stdout + "\n"
            if stderr: output_log += stderr + "\n"
            return process.returncode == 0
        except Exception as e:
            err_msg = str(e).replace(token, '***') if token else str(e)
            output_log += f"EXCEPTION: {err_msg}\n"
            return False

    # 0. Ensure local git identity is configured
    run_safe_cmd(['git', 'config', 'user.name', 'MikeyMike99'])
    run_safe_cmd(['git', 'config', 'user.email', 'mikeymike@server.local'])

    # 0.5 Detect active local branch
    branch_process = subprocess.run(['git', 'branch', '--show-current'], cwd=str(target), capture_output=True, text=True)
    current_branch = branch_process.stdout.strip() or 'master'

    # 1. PULL FIRST using remote_url (Injects token properly)
    run_safe_cmd(['git', 'pull', remote_url, current_branch, '--no-edit', '--allow-unrelated-histories'])

    # 2. Add local changes
    run_safe_cmd(['git', 'add', '.'])
    
    # 3. Commit local changes
    run_safe_cmd(['git', 'commit', '-m', 'Auto-sync update'])
    
    # 4. PUSH using remote_url (Injects token properly)
    run_safe_cmd(['git', 'push', remote_url, current_branch])
    
    # 5. Reload Server if PythonAnywhere
    if os.name == 'nt':
        output_log += "\n[System] Local Windows environment detected. Skipping WSGI reload.\n"
    else:
        output_log += "\n[System] Sync complete. Attempting to reload PythonAnywhere server...\n"
        try:
            wsgi_dir = Path("/var/www/")
            if wsgi_dir.exists():
                reloaded = False
                for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                    wsgi_file.touch()
                    output_log += f"[System] Touched {wsgi_file.name}\n"
                    reloaded = True
                if not reloaded:
                    output_log += "[System] Warning: No *_wsgi.py files found in /var/www/\n"
            else:
                output_log += "[System] Warning: /var/www/ not found.\n"
        except Exception as e:
            output_log += f"[System] Error touching WSGI: {e}\n"

    return jsonify({"output": output_log})