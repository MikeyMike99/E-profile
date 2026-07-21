import json
import shutil
import subprocess
import os
import markdown
from pathlib import Path
from flask import Blueprint, session, request, jsonify, redirect, url_for, render_template
from config import Config

# --- 1. MODULE IMPORTS ---
# We import get_project_path to ensure both modules look in the same place
from surgery import surgery_bp, get_project_path 
from file_mod import file_manager_bp

# --- 2. BLUEPRINT INITIALIZATION ---
projects_bp = Blueprint('projects', __name__)

# --- 3. NESTED LOGIC REGISTRATION ---
projects_bp.register_blueprint(surgery_bp, url_prefix='/surgery_logic')
projects_bp.register_blueprint(file_manager_bp, url_prefix='/explorer_logic')

# --- 4. INTERFACE ACTIVATORS (THE BUTTON TARGETS) ---

@projects_bp.route('/surgery/interface/<name>')
def open_surgery_interface(name):
    """
    Renders the Surgical Tray UI with Dynamic File Discovery.
    This fixes the issue where content wouldn't load if main.py was missing.
    """
    if not session.get('is_admin'):
        return "UNAUTHORIZED_ACCESS", 403

    # 1. Resolve Path
    target_name = 'root' if name.lower() in ['root', 'system_core'] else name
    path_root = get_project_path(target_name)

    # 2. Discovery: Find what files actually exist in this project/root
    valid_exts = ['.py', '.html', '.js', '.css', '.json', '.md', '.txt']
    try:
        all_files = [f.name for f in path_root.iterdir() if f.suffix in valid_exts]
    except Exception as e:
        return f"FS_ERROR: Cannot access {path_root}. {str(e)}", 500

    # 3. Smart Selection: Pick the best file to show first
    initial_file = request.args.get('file')
    if not initial_file or not (path_root / initial_file).exists():
        if "server.py" in all_files: initial_file = "server.py"
        elif "main.py" in all_files: initial_file = "main.py"
        elif all_files: initial_file = all_files[0]
        else: initial_file = "README.md"

    # 4. Pre-Load Content
    target_path = path_root / initial_file
    content = ""
    if target_path.exists():
        try:
            content = target_path.read_text(encoding='utf-8')
        except Exception as e:
            content = f"# ERROR_READING_FILE: {str(e)}"
    else:
        content = f"# FILE_OFFLINE\n# Checked Path: {target_path}"

    return render_template('surgical_tray.html', 
                           project_name=target_name, 
                           initial_file=initial_file,
                           initial_content=content)

@projects_bp.route('/explorer/<name>')
def open_explorer_interface(name):
    """Renders the File Manager UI."""
    target = 'root' if name.lower() in ['root', 'system_core'] else name
    return render_template('file_manager.html', project_name=target)

# --- 5. SYSTEM UTILS ---
config = Config()
PROJECTS_DIR = config.CONTENT_DIR / "projects" / "engines"
INTERNAL_FORBIDDEN = ["audio", "video", "static", "images", "content", "USERS"]

def get_projects_data():
    if not PROJECTS_DIR.exists():
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    order_file = PROJECTS_DIR.parent / "order.json"
    order_data = {}
    if order_file.exists():
        try: order_data = json.loads(order_file.read_text())
        except: order_data = {}

    is_admin = session.get('is_admin', False)
    is_employer = session.get('is_employer', False)
    tested_list = session.get('engines_tested', [])

    projects = []
    all_dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir() and d.name not in INTERNAL_FORBIDDEN]
    
    current_max = max(order_data.values()) if order_data else 0
    sorted_dirs = sorted(all_dirs, key=lambda x: (int(order_data.get(x.name, current_max + 1)), x.name))

    for d in sorted_dirs:
        is_ready = (d / "main.py").exists() or (d / "server.py").exists()
        desc_path = d / "content" / "index.md"
        description = "<p>[NODE_READY_FOR_DATA_STREAM]</p>"
        preview = "CLICK_TO_EXPAND_NODE_DETAILS"
        
        if desc_path.exists():
            raw_content = desc_path.read_text(encoding="utf-8")
            description = markdown.markdown(raw_content)
            lines = raw_content.splitlines()
            if lines:
                first_line = next((line.strip() for line in lines if line.strip()), "")
                preview = first_line.lstrip('#').strip()

        status, label, icon = "active", "LAUNCH_DEMO", "🔓"

        if not (is_admin or is_employer):
            if (d / "maintenance.txt").exists(): status, label, icon = "maintenance", "UNDER_MAINTENANCE", "🛠️"
            elif (d / "token_required.txt").exists(): status, label, icon = "token_needed", "TOKEN_REQUIRED", "🔑"
            elif not is_ready: status, label, icon = "coming_soon", "COMING_SOON", "⏳"
            elif d.name in tested_list: status, label, icon = "locked", "DEMO_DEPLETED", "🔒"

        projects.append({
            'name': d.name, 'is_ready': is_ready, 'description': description,
            'preview': preview, 'priority': order_data.get(d.name, current_max + 1),
            'status': status, 'label': label, 'icon': icon
        })
    return projects

# --- 6. CORE API ACTIONS ---

@projects_bp.route('/build_project', methods=['POST'])
def build_project():
    if not session.get('is_admin'): return jsonify({"status": "error", "message": "UNAUTHORIZED"}), 403
    name = (request.get_json() or {}).get('name', '').strip().replace(" ", "_")
    if not name: return jsonify({"status": "error", "message": "INVALID_NAME"}), 400
        
    new_dir = PROJECTS_DIR / name
    if not new_dir.exists():
        new_dir.mkdir(parents=True)
        for folder in ["content"] + INTERNAL_FORBIDDEN: (new_dir / folder).mkdir(exist_ok=True)
        (new_dir / "content" / "index.md").write_text(f"# {name}\n\n[NODE_DESCRIPTION_REQUIRED]", encoding="utf-8")
        (new_dir / "main.py").write_text("print('Node active.')", encoding="utf-8")
        return jsonify({"status": "success", "message": "CONSTRUCTION_COMPLETE"})
    return jsonify({"status": "error", "message": "NODE_EXISTS"}), 400

@projects_bp.route('/delete_project/<name>', methods=['POST'])
def delete_project(name):
    if not session.get('is_admin'): return jsonify({"status": "error", "message": "UNAUTHORIZED"}), 403
    target_dir = PROJECTS_DIR / name
    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        return jsonify({"status": "success", "message": "NODE_DELETED"})
    return jsonify({"status": "error", "message": "NODE_NOT_FOUND"}), 404

@projects_bp.route('/reorder_projects', methods=['POST'])
def reorder_projects():
    if not session.get('is_admin'): return jsonify({"status": "error", "message": "UNAUTHORIZED"}), 403
    order_list = (request.get_json() or {}).get('order', [])
    order_file = PROJECTS_DIR.parent / "order.json"
    order_file.write_text(json.dumps({name: i for i, name in enumerate(order_list)}, indent=4))
    return jsonify({"status": "success"})

@projects_bp.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    return jsonify({"status": "success", "message": "FEEDBACK_CACHED"})

@projects_bp.route('/execute/<name>')
def execute_project(name):
    proj_path = PROJECTS_DIR / name
    executable = next((proj_path / f for f in ["main.py", "server.py"] if (proj_path / f).exists()), None)
    if executable:
        subprocess.Popen(["python", str(executable)], cwd=str(proj_path))
        return f"INITIALIZED: {name}"
    return "NOT_FOUND", 404