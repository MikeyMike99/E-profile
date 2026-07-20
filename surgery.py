import os
import textwrap
import libcst as cst
import re
from pathlib import Path
from flask import Blueprint, request, jsonify, session
from config import Config

# --- BLUEPRINT INITIALIZATION ---
surgery_bp = Blueprint('surgery', __name__)
config = Config()
PROJECTS_DIR = config.CONTENT_DIR / "projects" / "engines"

def get_project_path(project_name):
    """Resolves the physical path for a project node securely."""
    name = str(project_name).strip().lower()

    if name in ['root', 'system_core']:
        # This points to the e_profile_v2 folder where app.py lives
        base = Path(__file__).resolve().parent 
    else:
        # Prevent traversal in the project name itself
        clean_name = Path(name).name
        base = PROJECTS_DIR / clean_name
        
    return base.resolve()

# --- CLASS 1: THE SURGICAL TRANSFORMER ---
class SurgicalTransformer(cst.CSTTransformer):
    def __init__(self, target_label, new_code_str):
        self.target_label = target_label.upper().replace("START_", "").replace("END_", "")
        self.new_statements = []
        
        cleaned_code = textwrap.dedent(new_code_str).strip()
        try:
            parsed = cst.parse_module(cleaned_code)
            self.new_statements = list(parsed.body)
        except Exception:
            self.new_statements = [cst.parse_statement(cleaned_code)]

        self.in_target_block = False
        self.patch_applied = False

    def _is_marker(self, node, prefix):
        code_str = cst.Module([]).code_for_node(node).strip()
        expected = f"{prefix}_{self.target_label}"
        return expected in code_str and ("#" in code_str or '"' in code_str or "'" in code_str)

    def leave_Module(self, original_node, updated_node):
        new_body = []
        for stmt in updated_node.body:
            if self._is_marker(stmt, "START"):
                new_body.append(stmt)
                new_body.extend(self.new_statements)
                self.in_target_block = True
                self.patch_applied = True
            elif self._is_marker(stmt, "END"):
                self.in_target_block = False
                new_body.append(stmt)
            elif not self.in_target_block:
                new_body.append(stmt)
        
        return updated_node.with_changes(body=new_body)

# --- API ROUTES ---

@surgery_bp.route('/get_block_source')
def get_block_source():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "FORBIDDEN"}), 403

    project = request.args.get('project')
    filename = request.args.get('file', 'app.py')
    target = request.args.get('target')
    
    path_root = get_project_path(project)
    
    # Path Traversal Protection for the filename
    clean_filename = Path(filename).name
    path = (path_root / clean_filename).resolve()
    
    if path_root not in path.parents and path != path_root:
         return jsonify({"status": "error", "message": "PATH_TRAVERSAL_DETECTED"}), 403

    if not path.exists():
        return jsonify({"status": "error", "message": f"PATH_NOT_FOUND: {path}"}), 404

    try:
        source = path.read_text(encoding='utf-8')
    except Exception as e:
        return jsonify({"status": "error", "message": f"FILE_READ_ERROR: {str(e)}"}), 500

    if target:
        pattern = rf"(['\"]?# START_{target}['\"]?).*?\n(.*?)\n\s*(['\"]?# END_{target}['\"]?)"
        match = re.search(pattern, source, re.DOTALL)
        if match:
            return jsonify({
                "code": textwrap.dedent(match.group(2)).strip(), 
                "status": "success"
            })
        return jsonify({"status": "error", "message": f"BLOCK {target} NOT FOUND"}), 404

    blocks = re.findall(r'START_(BLOCK_[A-Z_0-9]+)', source)
    valid_exts = ['.py', '.html', '.js', '.css', '.json', '.md', '.txt']
    
    try:
        files = [f.name for f in path_root.iterdir() if f.suffix in valid_exts]
    except Exception:
        files = [filename]
        
    return jsonify({
        "blocks": sorted(list(set(blocks))), 
        "files": sorted(files), 
        "status": "success"
    })

@surgery_bp.route('/get_raw_file')
def get_raw_file():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "FORBIDDEN"}), 403

    project = request.args.get('project')
    filename = request.args.get('file')
    
    path_root = get_project_path(project)
    clean_filename = Path(filename).name
    path = (path_root / clean_filename).resolve()
    
    if path_root not in path.parents and path != path_root:
         return jsonify({"status": "error", "message": "PATH_TRAVERSAL_DETECTED"}), 403

    if not path.exists():
        return jsonify({"status": "error", "message": "FILE_NOT_FOUND"}), 404
        
    try:
        content = path.read_text(encoding='utf-8')
        return jsonify({"status": "success", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": f"FILE_READ_ERROR: {str(e)}"}), 500

@surgery_bp.route('/apply_patch', methods=['POST'])
def apply_patch():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "FORBIDDEN"}), 403
    data = request.json or {}
    project = data.get('project')
    filename = data.get('file', 'app.py')
    target = data.get('target')
    new_code = data.get('code')
    path = get_project_path(project) / filename
    try:
        source_code = path.read_text(encoding='utf-8')
        if not target:
            path.write_text(new_code, encoding='utf-8')
            return jsonify({"status": "success", "message": "FULL_FILE_REWRITTEN"})
        source_tree = cst.parse_module(source_code)
        transformer = SurgicalTransformer(target, new_code)
        modified_tree = source_tree.visit(transformer)
        if transformer.patch_applied:
            path.write_text(modified_tree.code, encoding='utf-8')
            return jsonify({"status": "success", "message": "RECONSTRUCTION_COMPLETE"})
        else:
            return jsonify({"status": "error", "message": "MARKER_NOT_FOUND"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
# --- HEART DRAFT SYSTEM (Ported from V1) ---

USERS_DIR = Path("USERS")

def ensure_user_space(username):
    """Initializes the OS-style file system for a specific user recovery."""
    user_root = USERS_DIR / username
    
    # Define the structure required for the Heart's draft system
    folders = [
        user_root / "config",
        user_root / "temp" / "drafts", # Targeted by Heart Sync API
        user_root / "temp" / "logs"
    ]
    
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    
    return user_root

@surgery_bp.route("/heart/commit_surgery", methods=["POST"])
def commit_surgery():
    """Finalizes the surgery: Moves draft to the real project folder and clears temp."""
    if not session.get('is_admin'): return jsonify({"status": "unauthorized"}), 403
    
    data = request.json
    username = session.get('username', 'default_user')
    project = data.get('project')
    filename = data.get('filename')
    
    draft_path = USERS_DIR / username / "temp" / "drafts" / project / "${filename}.tmp"
    real_path = get_project_path(project) / filename
    
    try:
        if draft_path.exists():
            # The Final Stitch: Overwrite real file with the draft
            content = draft_path.read_text(encoding="utf-8")
            real_path.write_text(content, encoding="utf-8")
            
            # Post-Op: Remove the draft after successful commit
            draft_path.unlink()
            return jsonify({"status": "success", "message": "Surgery Committed."})
        else:
            return jsonify({"status": "error", "message": "No draft found to commit."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@surgery_bp.route("/heart/sync_draft", methods=["POST"])
def sync_draft():
    """Silently saves the current editor state to the user's temp space."""
    if not session.get('is_admin'): return jsonify({"status": "unauthorized"}), 403
    
    data = request.json
    username = session.get('username', 'default_user')
    project = data.get('project')
    filename = data.get('filename')
    code = data.get('code')
    
    ensure_user_space(username)
    draft_path = USERS_DIR / username / "temp" / "drafts" / project / "${filename}.tmp"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        draft_path.write_text(code, encoding="utf-8")
        return jsonify({"status": "synced"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@surgery_bp.route("/heart/check_draft")
def check_draft():
    """Checks if a recovery draft exists for the selected file."""
    username = session.get('username', 'default_user')
    project = request.args.get('project')
    filename = request.args.get('filename')
    
    draft_path = USERS_DIR / username / "temp" / "drafts" / project / "${filename}.tmp"
    
    if draft_path.exists():
        return jsonify({"exists": True, "content": draft_path.read_text(encoding="utf-8")})
    return jsonify({"exists": False})

