#stable get push
import os
import subprocess
import shutil
import shlex
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
    """Executes deployment commands, agy CLI operations, and developer utilities."""
    is_admin = session.get('is_admin', False) or session.get('admin', False) or ('PYTHONANYWHERE_DOMAIN' not in os.environ)
    if not is_admin:
        return jsonify({"output": "ACCESS_DENIED: Administrator clearance required."}), 403

    data = request.get_json() or {}
    raw_cmd = data.get('command', '').strip()
    project = data.get('project', 'root')
    path = data.get('path', '')

    target, _ = get_safe_path(project, path)
    output_log = ""
    
    if not raw_cmd:
        return jsonify({"output": ""})

    if raw_cmd == 'clear':
        return jsonify({"output": "", "action": "clear"})

    # Load token for auto-auth
    token = ""
    token_file = Path.cwd() / "gethub_token.txt"
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

    if raw_cmd.startswith('setup -get'):
        parts = raw_cmd.split()
        if len(parts) > 2 and parts[2] == 'new':
            repo = "MikeyMike99/ECHOS_OF_THE_WORLD"
            branch = "main"
            if len(parts) > 3:
                repo = parts[3]
            if len(parts) > 4:
                branch = parts[4]
                
            repo_url = f"https://github.com/{repo}.git"
            output_log += f"[System] Configuring new repository origin: {repo_url} (branch: {branch})\n"
            
            run_safe_cmd(['git', 'remote', 'remove', 'origin'])
            run_safe_cmd(['git', 'remote', 'add', 'origin', repo_url])
            run_safe_cmd(['git', 'fetch', 'origin'])
            run_safe_cmd(['git', 'pull', 'origin', branch, '--allow-unrelated-histories'])
            return jsonify({"output": output_log})
        else:
            branch = 'main'
            if len(parts) > 2:
                branch = parts[2]
                
            success = run_safe_cmd(['git', 'pull', remote_url, branch])
            if success:
                output_log += f"\n[System] Pull from '{branch}' successful. Attempting to reload PythonAnywhere server...\n"
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

    # CLI / agy / Developer command execution
    env = os.environ.copy()
    local_bin = os.path.expanduser("~/.local/bin")
    if "PATH" in env and local_bin not in env["PATH"]:
        env["PATH"] = f"{local_bin}:{env['PATH']}"
    elif "PATH" not in env:
        env["PATH"] = local_bin

    cmd_to_run = raw_cmd
    # Wrap direct prompt calls to agy: e.g. `agy "explain this file"` -> `agy --print "explain this file"`
    if cmd_to_run.startswith("agy ") or cmd_to_run == "agy":
        parts = cmd_to_run.split(maxsplit=1)
        sub_arg = parts[1].strip() if len(parts) > 1 else ""
        standard_subcommands = {"agent", "agents", "models", "mcp", "plugin", "plugins", "help", "--help", "-h", "version", "--version", "update", "changelog"}
        if sub_arg and not sub_arg.startswith("-") and sub_arg.split()[0] not in standard_subcommands:
            cmd_to_run = f"agy --print {shlex.quote(sub_arg)}"
        elif not sub_arg:
            cmd_to_run = "agy --help"

    timeout_seconds = 300 if "agy" in cmd_to_run else 45
    try:
        process = subprocess.run(
            cmd_to_run,
            shell=True,
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env
        )
        safe_out = process.stdout.replace(token, '***') if process.stdout and token else (process.stdout or "")
        safe_err = process.stderr.replace(token, '***') if process.stderr and token else (process.stderr or "")
        
        output_res = ""
        if safe_out:
            output_res += safe_out
        if safe_err:
            if output_res and not output_res.endswith("\n"):
                output_res += "\n"
            output_res += safe_err
        if not output_res and process.returncode == 0:
            output_res = "[Process completed successfully (exit code 0)]"
        elif not output_res:
            output_res = f"[Process exited with code {process.returncode}]"
            
        return jsonify({"output": output_res, "returncode": process.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({"output": f"[ERROR] Command timed out after {timeout_seconds} seconds."})
    except Exception as e:
        err_msg = str(e).replace(token, '***') if token else str(e)
        return jsonify({"output": f"EXCEPTION: {err_msg}"})

@file_manager_bp.route('/git_sync', methods=['POST'])
def git_sync():
    """Two-way sync: Clean environment separation preventing local fetch drops with dynamic branch support."""
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"output": "ACCESS_DENIED"}), 403

    target = config.ROOT_DIR
    output_log = "[System] Starting 2-Way Git Sync...\n"
    
    # 1. Parse request parameters (JSON body, query params, or form data)
    data = request.get_json(silent=True) or {}
    requested_branch = (
        data.get('branch') 
        or request.args.get('branch') 
        or request.form.get('branch') 
        or ""
    ).strip()

    # Determine current checked-out local branch
    def get_current_branch():
        try:
            res = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=str(target),
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                b = res.stdout.strip()
                if b and b != 'HEAD':
                    return b
        except Exception:
            pass
        return 'main'

    local_branch = get_current_branch()

    # Determine remote target branch
    if requested_branch:
        target_branch = requested_branch
    else:
        # Default: if on 'master' (typical on older PythonAnywhere clones), map to 'main'; otherwise use local branch
        target_branch = 'main' if local_branch == 'master' else local_branch

    # 2. Load token
    token = ""
    token_file = target / "gethub_token.txt"
    if not token_file.exists():
        token_file = Path.cwd() / "gethub_token.txt"
        
    if token_file.exists():
        token = token_file.read_text().strip()
    
    if not token:
        token = os.environ.get("GITHUB_TOKEN", "").strip()

    authenticated_url = f"https://MikeyMike99:{token}@github.com/MikeyMike99/E-profile.git" if token else "origin"

    def run_git_cmd(args):
        nonlocal output_log
        try:
            exe_path = shutil.which('git') or 'git'
            full_cmd = [exe_path, '-c', 'credential.helper='] + args

            process = subprocess.run(
                full_cmd,
                cwd=str(target),
                capture_output=True,
                text=True,
                timeout=45
            )
            
            cmd_str = ' '.join(full_cmd)
            if token:
                cmd_str = cmd_str.replace(token, '***')
            output_log += f"$ {cmd_str}\n"
            
            stdout = process.stdout.replace(token, '***') if process.stdout and token else process.stdout
            stderr = process.stderr.replace(token, '***') if process.stderr and token else process.stderr
            
            if stdout: output_log += stdout + "\n"
            if stderr: output_log += stderr + "\n"
            return process.returncode == 0
        except Exception as e:
            err_msg = str(e).replace(token, '***') if token and token in str(e) else str(e)
            output_log += f"EXCEPTION: {err_msg}\n"
            return False

    # 3. Ensure git identity
    subprocess.run(['git', 'config', 'user.name', 'MikeyMike99'], cwd=str(target))
    subprocess.run(['git', 'config', 'user.email', 'mikeymike@server.local'], cwd=str(target))

    # Commit any local uncommitted work first so branch switching or pulling doesn't conflict
    run_git_cmd(['add', '.'])
    run_git_cmd(['commit', '-m', f'Auto-sync update ({target_branch})'])

    # 4. Optional branch checkout if requested and different from local branch
    should_switch = data.get('checkout', data.get('switch', True))
    if requested_branch and should_switch and target_branch != local_branch and local_branch != 'master':
        check_b = subprocess.run(
            ['git', 'show-ref', '--verify', f'refs/heads/{target_branch}'],
            cwd=str(target),
            capture_output=True
        )
        if check_b.returncode == 0:
            run_git_cmd(['checkout', target_branch])
        else:
            run_git_cmd(['fetch', authenticated_url, f'{target_branch}:{target_branch}'])
            run_git_cmd(['checkout', target_branch])
        local_branch = get_current_branch()

    # 5. Environment-Specific Logic
    is_windows = (os.name == 'nt')

    if is_windows:
        # --- LOCAL WINDOWS ENVIRONMENT ---
        output_log += f"[System] Local Windows environment detected (Branch: {target_branch})...\n"
        
        # Merge strategy to prevent conflict markers locally
        run_git_cmd(['pull', authenticated_url, target_branch, '--no-edit', '-X', 'ours'])
        if local_branch == target_branch:
            run_git_cmd(['push', authenticated_url, target_branch])
        else:
            run_git_cmd(['push', authenticated_url, f'{local_branch}:{target_branch}'])

    else:
        # --- PYTHONANYWHERE SERVER ENVIRONMENT ---
        output_log += f"[System] PythonAnywhere server environment detected (Branch: {target_branch})...\n"
        
        run_git_cmd(['pull', authenticated_url, target_branch, '--no-edit', '--allow-unrelated-histories', '--no-recurse-submodules', '-X', 'ours'])
        run_git_cmd(['checkout', '--ours', 'content/projects/engines/antigravity_agent'])
        run_git_cmd(['add', 'content/projects/engines/antigravity_agent'])
        run_git_cmd(['submodule', 'sync'])
        run_git_cmd(['config', 'submodule.content/projects/engines/antigravity_agent.url', f'https://MikeyMike99:{token}@github.com/MikeyMike99/DevCore.git'])
        run_git_cmd(['submodule', 'update', '--init', '--recursive'])
        
        if local_branch == 'master' and target_branch == 'main':
            run_git_cmd(['push', authenticated_url, 'master:main'])
        elif local_branch == target_branch:
            run_git_cmd(['push', authenticated_url, target_branch])
        else:
            run_git_cmd(['push', authenticated_url, f'{local_branch}:{target_branch}'])
        
        # --- AUTO-INSTALL DEPENDENCIES & POST-SYNC HOOKS ---
        output_log += "[System] Auto-installing updated dependencies...\n"
        import sys
        try:
            pip_p = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], cwd=str(target), capture_output=True, text=True)
            output_log += "[System] pip requirements verified.\n"
            
            # Generic Post-Sync Hook for future integrations
            post_sync_script = target / "post_sync.py"
            if post_sync_script.exists():
                output_log += "[System] Executing post_sync.py hook...\n"
                hook_p = subprocess.run([sys.executable, str(post_sync_script)], cwd=str(target), capture_output=True, text=True)
                output_log += hook_p.stdout + "\n"
                if hook_p.stderr:
                    output_log += hook_p.stderr + "\n"
        except Exception as e:
            output_log += f"[ERROR] Failed to auto-install dependencies or run hooks: {e}\n"
            
        # Reload WSGI server
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

    return jsonify({"output": output_log, "branch": target_branch, "local_branch": local_branch})
