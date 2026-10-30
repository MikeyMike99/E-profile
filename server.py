import os
import json
import hashlib
import uuid
import time
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, session, abort, request, redirect, url_for, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import markdown

# --- 1. CONFIG & MODULE IMPORTS ---
from config import Config
from blog_mod import blog_bp
from projects_mod import projects_bp, get_projects_data 
from surgery import surgery_bp  # Or wherever your surgery.py is located
from cert_mod import cert_bp, get_certifications_data
from echos_mod import echos_bp
from docs_mod import docs_bp

# --- 2. APP INITIALIZATION ---
config = Config()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "SECURE_KEY_2026_PROTOTYPE")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1)
)

# --- GLOBAL CONTEXT PROCESSOR ---
@app.context_processor
def inject_global_blogs():
    try:
        from blog_mod import get_blog_data
        blogs, logs = get_blog_data()
        return dict(global_blogs=blogs, global_blog_logs=logs)
    except Exception as e:
        app.logger.error(f"Context Processor Error: {e}")
        return dict(global_blogs=[], global_blog_logs=[f"CRITICAL ERROR in Context Processor: {e}"])

# --- 3. BLUEPRINT REGISTRATION ---
app.register_blueprint(blog_bp)
app.register_blueprint(projects_bp, url_prefix='/api/projects')
app.register_blueprint(surgery_bp, url_prefix='/api/projects/surgery')
app.register_blueprint(cert_bp)

from sync_mod import sync_bp
app.register_blueprint(sync_bp, url_prefix='/api')

app.register_blueprint(echos_bp)
app.register_blueprint(docs_bp)

from audio_suite_mod import audio_suite_bp
app.register_blueprint(audio_suite_bp)

from newsletter_mod import newsletter_bp
app.register_blueprint(newsletter_bp)

from diagnostics_mod import diagnostics_bp, get_system_diagnostic_summary
app.register_blueprint(diagnostics_bp)
import sys
_app_dir = Path(__file__).resolve().parent
_ai_candidates = [
    _app_dir / "content" / "projects" / "engines" / "antigravity_agent",
    _app_dir.parent / "DevCore",
]
ai_path = str(next((p for p in _ai_candidates if (p / "ai_plugin.py").is_file()), _ai_candidates[0]))
if ai_path not in sys.path:
    sys.path.insert(0, ai_path)

try:
    from ai_plugin import ai_bp
    app.register_blueprint(ai_bp, url_prefix='/ai_agent')
except Exception as e:
    app.logger.error(f"Failed to load AI Blueprint: {e}")

class SystemLogger:
    def __init__(self):
        self.logs = []
    def log(self, type, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.logs.append({'time': timestamp, 'type': type, 'msg': msg})
        if len(self.logs) > 50: self.logs.pop(0)

    def error(self, msg): self.log("ERROR", msg)
    def info(self, msg): self.log("INFO", msg)
    def warning(self, msg): self.log("WARNING", msg)

sys_log = SystemLogger()

# --- NATIVE ANALYTICS ENGINE (Zero-Cookie, Privacy-First) ---
ANALYTICS_FILE = config.ROOT_DIR / "traffic_metrics.json"

def get_analytics():
    if not ANALYTICS_FILE.exists():
        return {"total_views": 0, "unique_visitors": [], "paths": {}}
    try:
        data = json.loads(ANALYTICS_FILE.read_text())
        return data
    except Exception:
        return {"total_views": 0, "unique_visitors": [], "paths": {}}

def save_analytics(data):
    try:
        ANALYTICS_FILE.write_text(json.dumps(data, indent=4))
    except Exception:
        pass

@app.before_request
def log_traffic():
    # Skip tracking for assets, api, and admin routes
    if request.path.startswith('/static') or request.path.startswith('/api') or request.path.startswith('/admin'):
        return
        
    # Generate daily anonymous hash for unique visitor counting (No cookies used)
    raw_id = f"{request.remote_addr}-{request.user_agent.string}-{datetime.now().strftime('%Y-%m-%d')}"
    visitor_hash = hashlib.md5(raw_id.encode()).hexdigest()
    
    data = get_analytics()
    data["total_views"] = data.get("total_views", 0) + 1
    
    if visitor_hash not in data["unique_visitors"]:
        data["unique_visitors"].append(visitor_hash)
        
    # Trim visitor list to prevent infinite growth (keep last 1000)
    if len(data["unique_visitors"]) > 1000:
        data["unique_visitors"].pop(0)
        
    path_key = request.path
    if path_key not in data["paths"]:
        data["paths"][path_key] = 0
    data["paths"][path_key] += 1
    
    
    save_analytics(data)

sys_log = SystemLogger()

# --- PROFILE MANAGEMENT ---
import data_migrator

PROFILES_FILE = config.ROOT_DIR / "profiles.json"

def load_profiles():
    envelope = data_migrator.verify_and_migrate_profiles(PROFILES_FILE, sys_log)
    return envelope.get('data', {})

def save_profiles(profiles):
    envelope = {
        "metadata": {
            "schema_version": data_migrator.TARGET_SCHEMA_VERSION,
            "last_migrated": datetime.now().isoformat()
        },
        "data": profiles
    }
    PROFILES_FILE.write_text(json.dumps(envelope, indent=4), encoding='utf-8')

@app.before_request
def restrict_access():
    """Security Layer: Handles handshake keys and session verification."""
    public_endpoints = ['login', 'static', 'certifications.get_cert_file', 'dynamic_route']
    if request.endpoint in public_endpoints:
        return

    perms = session.get('permissions', [])

    # If they are trying to access admin panel without being admin
    if request.endpoint == 'admin' and not session.get('admin', False):
        return redirect(url_for('login'))

def initialize_environment():
    """Ensures all OS directories exist on boot."""
    for path in config.get_all_required_paths():
        Path(path).mkdir(parents=True, exist_ok=True)
    for tab in config.TABS:
        tab_dir = config.CONTENT_DIR / tab
        tab_dir.mkdir(parents=True, exist_ok=True)
        if tab == 'blog': (tab_dir / "content").mkdir(exist_ok=True)
        if tab == 'projects': (tab_dir / "engines").mkdir(exist_ok=True)
        
        f = tab_dir / f"{tab}.md"
        if not f.exists():
            f.write_text(f"# {tab.upper()}\nInitialized.")

initialize_environment()

@app.template_filter('clean_text')
def clean_text_filter(s):
    if isinstance(s, str):
        return s.replace('_', ' ').title()
    return s

@app.context_processor
def inject_system():
    return dict(
        config=config, 
        theme=config.THEME, 
        sys_logs=sys_log.logs[-5:],
        label=session.get('label', 'Guest'),
        username=session.get('username', 'Guest'),
        permissions=session.get('permissions', []),
        is_admin=session.get('admin', False)
    )

# --- 5. PRIMARY ROUTING ---

@app.route('/', defaults={'path': 'home'})
@app.route('/<path:path>')
def dynamic_route(path):
    # CRITICAL: Prevents this route from stealing API or AI Agent calls
    if path.startswith('api') or path.startswith('ai_agent'):
        abort(404)

    if path not in config.TABS: 
        parts = path.split('/')
        if parts[0] in config.TABS:
            flash(f"The requested content may have been relocated. Redirecting to {parts[0]}.", "info")
            return redirect(url_for('dynamic_route', path=parts[0]))
        return redirect(url_for('dynamic_route', path='home'))
        
    perms = session.get('permissions', [])
    if path not in ['home', 'newsletter', 'docs', 'bio', 'downloads', 'usage'] and not session.get('admin', False) and not session.get('is_employer', False):
        has_access = (
            f'view:tab:{path}' in perms
            or ('master:view_tabs' in perms and f'exclude:tab:{path}' not in perms)
        )
        if not has_access:
            return render_template(
                'clearance_required.html',
                active_tab=path,
                requested_tab=path,
                is_admin=False,
                is_employer=False,
                permissions=perms
            )
    
    # Retrieve content sections
    projects_list = get_projects_data() if path in ['projects', 'home'] else []
    certs_data = get_certifications_data() if path in ['certifications', 'home'] else []
    
    # Load Blog Data explicitly
    blog_list = []
    latest_shortcut = None
    if path in ['blog', 'home']:
        from blog_mod import get_blog_data
        blog_list, _ = get_blog_data()
        latest = next((b for b in blog_list if b.get('is_latest')), None)
        if latest:
            latest_shortcut = latest

    if path == 'blog':
        template = 'blog.html'
    elif path == 'projects':
        template = 'projects.html'
    elif path == 'certifications':
        template = 'certifications.html'
    elif path == 'home':
        template = 'home.html'
    elif path == 'bio':
        template = 'bio.html'
    elif path == 'downloads':
        from audio_suite_mod import render_downloads_page
        return render_downloads_page()
    elif path in ['usage', 'telemetry']:
        from audio_suite_mod import render_usage_page
        return render_usage_page()
    else:
        template = 'base.html'

    html_content = ""
    if path not in ['blog', 'projects', 'certifications']:
        file_path = config.CONTENT_DIR / path / f"{path}.md"
        if file_path.exists():
            html_content = markdown.markdown(file_path.read_text(), extensions=['fenced_code', 'tables', 'nl2br'])

    return render_template(
        template, 
        active_tab=path, 
        content=html_content, 
        blogs=blog_list,
        projects=projects_list,
        certs=certs_data,
        latest_post=latest_shortcut,
        is_admin=session.get('admin', False),
        is_employer=session.get('is_employer', False),
        permissions=session.get('permissions', [])
    )

def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

@app.route('/access/<uuid_token>')
def magic_link(uuid_token):
    profiles = load_profiles()
    for hashed_token, user_data in profiles.items():
        if user_data.get('uuid') == uuid_token.strip():
            if not user_data.get('bypass_enabled', False):
                flash("Bypass link access is currently disabled for this profile.", "error")
                sys_log.warning(f"Attempted use of disabled Magic Link for {user_data.get('username')}")
                return redirect(url_for('login'))
                
            label = user_data.get('label', 'Guest')
            username = user_data.get('username', 'Unknown')
            perms = user_data.get('permissions', [])
            is_admin = user_data.get('is_admin', False)
            is_employer = user_data.get('is_employer', False)
            session.permanent = True
            session['label'] = label
            session['username'] = username
            session['permissions'] = perms
            session['admin'] = is_admin
            session['is_admin'] = is_admin
            session['is_employer'] = is_employer
            sys_log.info(f"Magic Link login success: {username} ({label})")
            
            return redirect(url_for('dynamic_route', path='home'))
                
    flash("Invalid or expired Magic Link.", "error")
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    profiles = load_profiles()
    # Setup mode is active if NO admin exists
    has_admin = any(p.get('is_admin', False) for p in profiles.values())
    is_setup = not has_admin

    if session.get('admin', False) and not is_setup and request.method == 'GET':
        return redirect(url_for('admin'))

    if request.method == 'POST':
        action = request.form.get('action', 'login')
        token = request.form.get('token', '').strip()
        next_url = request.form.get('next', '').strip()

        if not token:
            return render_template('login.html', error="TOKEN_REQUIRED", is_setup=is_setup)

        hashed_token = hash_token(token)

        if is_setup and action == 'setup':
            # Create the initial account with chosen role
            username = request.form.get('username', 'Admin').strip()
            label = request.form.get('label', 'Root Admin')
            profiles[hashed_token] = {
                "username": username,
                "label": label,
                "uuid": str(uuid.uuid4()),
                "permissions": ['view:real_name'],
                "is_admin": True,
                "is_employer": False,
                "bypass_enabled": False
            }
            save_profiles(profiles)
            
            # Log them in automatically
            session.permanent = True
            session['label'] = label
            session['username'] = username
            session['permissions'] = profiles[hashed_token]['permissions']
            session['admin'] = True
            session['is_admin'] = True
            session['is_employer'] = False
            sys_log.info(f"System Initialized. Profile '{username}' created as {label}.")
            return redirect(url_for('admin'))
            
        elif action == 'login':
            # Normal login
            user_data = profiles.get(hashed_token)
            if user_data:
                label = user_data.get('label', 'Guest')
                username = user_data.get('username', 'Unknown')
                perms = user_data.get('permissions', [])
                is_admin = user_data.get('is_admin', False)
                is_employer = user_data.get('is_employer', False)
                
                session.permanent = True
                session['label'] = label
                session['username'] = username
                session['permissions'] = perms
                session['admin'] = is_admin
                session['is_admin'] = is_admin
                session['is_employer'] = is_employer
                sys_log.info(f"Login success: {username} ({label})")
                
                if is_admin:
                    return redirect(url_for('admin'))
                elif next_url and next_url.startswith('/') and not next_url.startswith('//'):
                    return redirect(next_url)
                else:
                    return redirect(url_for('dynamic_route', path='home'))
            
            sys_log.error(f"Failed login attempt with invalid token.")
            return render_template('login.html', error="ACCESS_DENIED", is_setup=is_setup)

    return render_template('login.html', is_setup=is_setup)

@app.route('/logout')
def logout():
    # If impersonating, destroy the master admin session completely
    if session.get('impersonator_token'):
        session.clear()
        flash("Admin master session destroyed securely.", "info")
    else:
        session.clear()
        flash("Session terminated securely.", "info")
    return redirect(url_for('dynamic_route', path='home'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin', False):
        return redirect(url_for('login'))
        
    profiles = load_profiles()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            username = request.form.get('username', '').strip()
            token = request.form.get('token', '').strip()
            label = request.form.get('label', 'Guest Profile')
            permissions = request.form.getlist('permissions')
            is_admin = request.form.get('is_admin') == 'on'
            is_employer = request.form.get('is_employer') == 'on'
            
            if username and token:
                hashed_token = hash_token(token)
                profiles[hashed_token] = {
                    "username": username,
                    "label": label,
                    "uuid": str(uuid.uuid4()),
                    "permissions": permissions,
                    "bypass_enabled": request.form.get('bypass_enabled') == 'on',
                    "is_admin": is_admin,
                    "is_employer": is_employer
                }
                save_profiles(profiles)
                sys_log.info(f"Profile created: {username}")
                
        return redirect(url_for('admin'))
        
    dyn_tabs = config.TABS
    from blog_mod import get_blog_data
    all_blogs, _ = get_blog_data()
    dyn_blogs = [b['title'] for b in all_blogs]
    dyn_certs = [c['name'] for c in get_certifications_data()]
    dyn_projects = [p['name'] for p in get_projects_data()]

    # SYSTEM HEALTH & GIT LOGIC
    import json
    blog_dir = config.CONTENT_DIR / "blog" / "content"
    order_file = config.CONTENT_DIR / "blog" / "order.json"
    
    unindexed = get_unindexed_changes(blog_dir, order_file)
    git_status = get_git_status(config.ROOT_DIR)
    cert_health = get_cert_health()

    # Restore Quarantine Logic
    quarantined_files = {}
    quarantine_log_file = config.ROOT_DIR / ".backup" / "quarantine_log.json"
    if quarantine_log_file.exists():
        try: quarantined_files = json.loads(quarantine_log_file.read_text())
        except: pass

    analytics_data = get_analytics()
    diagnostics_data = get_system_diagnostic_summary()

    return render_template('manage_profiles.html', 
        profiles=profiles,
        dyn_tabs=dyn_tabs,
        dyn_blogs=dyn_blogs,
        dyn_certs=dyn_certs,
        dyn_projects=dyn_projects,
        unindexed=unindexed,
        git_status=git_status,
        cert_health=cert_health,
        system_logs=sys_log.logs,
        quarantined_files=quarantined_files,
        analytics_data=analytics_data,
        diagnostics_data=diagnostics_data,
        is_admin=session.get('admin', False)
    )

def restore_from_history():
    history_file = config.ROOT_DIR / "rename_history.json"
    cert_dir = config.CONTENT_DIR / "certifications" / "digital badges and certificates"
    
    if not history_file.exists():
        return False, "No rename_history.json found."
        
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
    except Exception as e:
        return False, f"Error reading history file: {e}"
        
    success_count = 0
    errors = []
    
    for old_rel, new_rel in reversed(history):
        old_abs = cert_dir / old_rel
        new_abs = cert_dir / new_rel
        
        if not new_abs.exists():
            errors.append(f"Target file not found: {new_rel}")
            continue
            
        if old_abs.exists():
            errors.append(f"Original path already exists (avoiding overwrite): {old_rel}")
            continue
            
        try:
            old_abs.parent.mkdir(parents=True, exist_ok=True)
            new_abs.rename(old_abs)
            success_count += 1
        except Exception as e:
            errors.append(f"Could not revert {new_rel}: {e}")
            
    if success_count == len(history):
        history_file.unlink(missing_ok=True)
        return True, f"Rollback complete. Successfully restored all {success_count} items."
    else:
        return False, f"Restored {success_count}/{len(history)} items. Errors: {'; '.join(errors)}"

def get_cert_health():
    from cert_mod import CERT_DIR, ORDER_FILE
    order_data = []
    if ORDER_FILE.exists():
        try: order_data = json.loads(ORDER_FILE.read_text())
        except Exception: pass
        
    current_files = []
    if CERT_DIR.exists():
        for path in CERT_DIR.rglob('*'):
            if path.is_file() and path.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.docx']:
                rel_path = path.relative_to(CERT_DIR)
                current_files.append(str(rel_path).replace('\\', '/'))
                
    missing_files = [f for f in order_data if f not in current_files]
    
    history_file = config.ROOT_DIR / "rename_history.json"
    rollback_available = history_file.exists()
    
    return {
        "missing_files": missing_files,
        "rollback_available": rollback_available,
        "has_issues": len(missing_files) > 0 or rollback_available
    }

# --- SYSTEM HEALTH & GIT ROUTES ---
def get_unindexed_changes(blog_dir: Path, order_file: Path):
    untracked_files = []
    missing_files = []
    order_data = {}
    if order_file.exists():
        try: order_data = json.loads(order_file.read_text())
        except Exception: pass

    existing_files = set()
    if blog_dir.exists():
        existing_files = {f.name for f in blog_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.md', '.html', '.json']}
        
    indexed_files = {fname for fname in order_data.keys() if fname != 'latest_filename'}
    untracked_files = list(existing_files - indexed_files)
    missing_files = list(indexed_files - existing_files)
    
    return {
        "untracked": untracked_files,
        "missing": missing_files,
        "total_mismatches": len(untracked_files) + len(missing_files)
    }

def reindex_disk_state(blog_dir: Path, order_file: Path):
    if not blog_dir.exists(): return False
    existing_order = {}
    if order_file.exists():
        try: existing_order = json.loads(order_file.read_text())
        except Exception: pass
            
    new_order = {}
    current_files = [f for f in blog_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.md', '.html', '.json']]
    current_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    for i, f in enumerate(current_files):
        old_val = existing_order.get(f.name, i)
        if isinstance(old_val, dict):
            old_priority = old_val.get("priority", i)
        else:
            old_priority = old_val
            
        new_order[f.name] = int(old_priority)
        
    if current_files:
        new_order['latest_filename'] = current_files[0].name
        
    order_file.write_text(json.dumps(new_order, indent=4))
    return True

def get_git_status(repo_dir: Path):
    import subprocess
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], cwd=str(repo_dir), capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        modified_added = []
        deleted = []
        for line in lines:
            if len(line) < 3: continue
            status = line[:2]
            filename = line[3:].strip('"')
            if 'D' in status: deleted.append(filename)
            else: modified_added.append(filename)
        return {
            "modified_ready": modified_added,
            "deleted_ready": deleted,
            "has_changes": len(modified_added) > 0 or len(deleted) > 0,
            "error": None
        }
    except subprocess.CalledProcessError:
        return {"error": "Git repository not initialized or inaccessible.", "has_changes": False}
    except FileNotFoundError:
        return {"error": "Git executable not found on the system.", "has_changes": False}

@app.route('/admin/rollback_renames', methods=['POST'])
def admin_rollback_renames():
    if not session.get('admin', False): return jsonify({"error": "Unauthorized"}), 403
    success, msg = restore_from_history()
    sys_log.info(f"Rollback result: {msg}")
    return redirect(url_for('admin'))

@app.route('/admin/reindex', methods=['POST'])
def handle_reindex():
    if not session.get('admin', False): return jsonify({"error": "Unauthorized"}), 403
    blog_dir = config.CONTENT_DIR / "blog" / "content"
    order_file = config.CONTENT_DIR / "blog" / "order.json"
    if reindex_disk_state(blog_dir, order_file):
        flash("Successfully reindexed disk state. Agent changes accepted.", "success")
    else:
        flash("Failed to reindex. Blog directory not found.", "error")
    return redirect(url_for('admin'))

@app.route('/admin/git_push', methods=['POST'])
def handle_git_push():
    if not session.get('admin', False): return jsonify({"error": "Unauthorized"}), 403
    try:
        import subprocess
        blog_dir = config.CONTENT_DIR / "blog" / "content"
        order_file = config.CONTENT_DIR / "blog" / "order.json"
        reindex_disk_state(blog_dir, order_file)
        repo_dir = str(config.ROOT_DIR)
        subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True)
        subprocess.run(['git', 'commit', '-m', 'Agent Auto-Sync: Accepted Local Disk Changes'], cwd=repo_dir, check=True)
        subprocess.run(['git', 'push'], cwd=repo_dir, check=True)
        flash("Successfully committed and pushed to GitHub.", "success")
    except Exception as e:
        flash(f"Git Push Failed: {e}", "error")
    return redirect(url_for('admin'))

@app.route('/admin/git_pull', methods=['POST'])
def handle_git_pull():
    if not session.get('admin', False): return jsonify({"error": "Unauthorized"}), 403
    try:
        import subprocess
        repo_dir = str(config.ROOT_DIR)
        subprocess.run(['git', 'fetch', 'origin'], cwd=repo_dir, check=True)
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], cwd=repo_dir, check=True)
        flash("Successfully pulled from GitHub. Local changes overwritten.", "info")
    except Exception as e:
        flash(f"Git Pull Failed: {e}", "error")
    return redirect(url_for('admin'))

@app.route('/quarantine/restore', methods=['POST'])
def restore_quarantine():
    if not session.get('admin', False): return jsonify({"error": "Unauthorized"}), 403
    q_id = request.form.get('q_id')
    
    import json, shutil
    quarantine_log_file = config.ROOT_DIR / ".backup" / "quarantine_log.json"
    if quarantine_log_file.exists():
        try:
            quarantine_data = json.loads(quarantine_log_file.read_text())
            if q_id in quarantine_data:
                file_info = quarantine_data[q_id]
                backup_path = config.ROOT_DIR / ".backup" / file_info['backup_name']
                original_path = Path(file_info['original_path'])
                
                if backup_path.exists():
                    shutil.move(str(backup_path), str(original_path))
                    del quarantine_data[q_id]
                    quarantine_log_file.write_text(json.dumps(quarantine_data, indent=4))
                    flash(f"Restored {file_info['original_name']}", "success")
                else:
                    flash("Backup file not found on disk.", "error")
        except Exception as e:
            flash(f"Error restoring file: {e}", "error")
            
    return redirect(url_for('admin'))

@app.route('/quarantine/delete', methods=['POST'])
def delete_quarantine():
    if not session.get('admin', False): return jsonify({"error": "Unauthorized"}), 403
    q_id = request.form.get('q_id')
    
    import json
    quarantine_log_file = config.ROOT_DIR / ".backup" / "quarantine_log.json"
    if quarantine_log_file.exists():
        try:
            quarantine_data = json.loads(quarantine_log_file.read_text())
            if q_id in quarantine_data:
                file_info = quarantine_data[q_id]
                backup_path = config.ROOT_DIR / ".backup" / file_info['backup_name']
                
                if backup_path.exists():
                    backup_path.unlink()
                
                del quarantine_data[q_id]
                quarantine_log_file.write_text(json.dumps(quarantine_data, indent=4))
                flash(f"Permanently deleted {file_info['original_name']}", "info")
        except Exception as e:
            flash(f"Error deleting file: {e}", "error")
            
    return redirect(url_for('admin'))

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if not session.get('admin', False): 
        return jsonify({"error": "Unauthorized"}), 403
        
    token_hash = request.form.get('token_hash', '').strip()
    profiles = load_profiles()
    
    if not token_hash or token_hash not in profiles:
        flash("Target profile not found for deletion.", "error")
        return redirect(url_for('admin'))

    target_name = profiles[token_hash].get('username', 'Unknown')
    if target_name == session.get('username'):
        flash("Safety rule enforced: You cannot terminate your own active administrator profile.", "error")
        return redirect(url_for('admin'))

    del profiles[token_hash]
    save_profiles(profiles)
    sys_log.info(f"Terminated profile: {target_name}")
    flash(f"Profile {target_name} permanently terminated.", "info")
    return redirect(url_for('admin'))

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if not session.get('admin', False): 
        return jsonify({"error": "Unauthorized"}), 403
        
    token_hash = request.form.get('token_hash', '').strip()
    profiles = load_profiles()
    
    if token_hash not in profiles:
        flash("Target profile was not found.", "error")
        return redirect(url_for('admin'))

    target_profile = profiles[token_hash]
    target_profile['username'] = request.form.get('username', target_profile.get('username', '')).strip()
    target_profile['label'] = request.form.get('label', target_profile.get('label', '')).strip()
    target_profile['permissions'] = request.form.getlist('permissions')
    target_profile['is_admin'] = request.form.get('is_admin') == 'on'
    target_profile['is_employer'] = request.form.get('is_employer') == 'on'
    target_profile['bypass_enabled'] = request.form.get('bypass_enabled') == 'on'
    
    new_token = request.form.get('token', '').strip()
    if new_token:
        if len(new_token) < 4:
            flash("New PIN / Access Token must be at least 4 characters long.", "error")
            return redirect(url_for('admin'))
        new_token_hash = hash_token(new_token)
        if new_token_hash in profiles and new_token_hash != token_hash:
            flash("This PIN / Token is already assigned to another profile. Choose a unique PIN.", "error")
            return redirect(url_for('admin'))
        profiles.pop(token_hash)
        profiles[new_token_hash] = target_profile
        sys_log.info(f"Admin updated identity & reset credentials for: {target_profile['username']}")
        flash(f"Profile {target_profile['username']} and PIN updated successfully.", "success")
    else:
        sys_log.info(f"Admin updated identity: {target_profile['username']}")
        flash(f"Profile {target_profile['username']} updated successfully.", "success")
        
    save_profiles(profiles)
    return redirect(url_for('admin'))

@app.route('/reset_pin', methods=['POST'])
def reset_pin():
    if not session.get('admin', False): 
        return jsonify({"error": "Unauthorized"}), 403
        
    old_token_hash = request.form.get('token_hash', '').strip()
    new_token = request.form.get('new_token', '').strip()
    confirm_token = request.form.get('confirm_token', '').strip()
    profiles = load_profiles()
    
    if not old_token_hash or old_token_hash not in profiles:
        flash("Target profile was not found.", "error")
        return redirect(url_for('admin'))

    if not new_token:
        flash("New PIN / Access Token cannot be empty.", "error")
        return redirect(url_for('admin'))

    if len(new_token) < 4:
        flash("New PIN / Access Token must be at least 4 characters long.", "error")
        return redirect(url_for('admin'))

    if confirm_token and new_token != confirm_token:
        flash("New PIN and confirmation PIN do not match.", "error")
        return redirect(url_for('admin'))

    new_token_hash = hash_token(new_token)
    if new_token_hash in profiles and new_token_hash != old_token_hash:
        flash("This PIN / Token is already assigned to another profile. Choose a unique PIN.", "error")
        return redirect(url_for('admin'))

    user_data = profiles.pop(old_token_hash)
    profiles[new_token_hash] = user_data
    save_profiles(profiles)

    target_name = user_data.get('username', 'User')
    sys_log.info(f"Admin reset PIN for profile: {target_name}")
    flash(f"PIN/Password successfully reset for {target_name}.", "success")
    return redirect(url_for('admin'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not session.get('admin', False):
        flash("Password and PIN resets are restricted to the Admin Panel.", "error")
        return redirect(url_for('login'))
    flash("Password and credential resets are managed directly within the Admin Panel.", "info")
    return redirect(url_for('admin'))

@app.route('/admin_impersonate/<token_hash>', methods=['POST'])
def admin_impersonate(token_hash):
    if not session.get('admin', False):
        return redirect(url_for('login'))
        
    profiles = load_profiles()
    target = profiles.get(token_hash)
    if not target:
        flash("Target profile not found.", "error")
        return redirect(url_for('admin'))
        
    session['impersonator_token'] = 'admin_active'
    session['label'] = target.get('label', 'Guest')
    session['username'] = target.get('username', 'Unknown')
    session['permissions'] = target.get('permissions', [])
    session['admin'] = target.get('is_admin', False)
    session['impersonated_hash'] = token_hash
    
    sys_log.info(f"Admin impersonating {target.get('username')}")
    flash(f"Impersonating {target.get('username')}.", "info")
    return redirect(url_for('dynamic_route', path='home'))

@app.route('/api/toggle_exclusion', methods=['POST'])
def toggle_exclusion():
    if not session.get('impersonator_token'):
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.json
    target_hash = session.get('impersonated_hash')
    perm_to_toggle = data.get('permission')
    
    profiles = load_profiles()
    if target_hash in profiles:
        perms = profiles[target_hash].get('permissions', [])
        if perm_to_toggle in perms:
            perms.remove(perm_to_toggle)
            state = "removed"
        else:
            perms.append(perm_to_toggle)
            state = "added"
            
        profiles[target_hash]['permissions'] = perms
        save_profiles(profiles)
        
        session['permissions'] = perms
        sys_log.info(f"Admin toggled {perm_to_toggle} for {profiles[target_hash]['username']} to {state}")
        return jsonify({"success": True, "state": state, "permission": perm_to_toggle})
        
    return jsonify({"error": "Profile not found"}), 404

AUDIO_SUITE_LICENSES_FILE = config.CONTENT_DIR / "audio_suite_licenses.json"
LATEST_AUDIO_SUITE_VERSION = "1.0.0"
AUDIO_SUITE_DOWNLOAD_URL = "https://github.com/MikeyMike99/JOSHY-downloads"
AUDIO_SUITE_CHANGELOG = "Audio Playback Suite update featuring dual-layer hardware license hardening and automated cloud attestation."


def is_newer_version(latest: str, current: str) -> bool:
    """Evaluates semantic version strings to determine if an update is available."""
    try:
        def parse_ver(v):
            return [int(x) for x in re.sub(r"[^0-9.]", "", v).split(".") if x]
        return parse_ver(latest) > parse_ver(current)
    except Exception:
        return False


@app.route('/api/audio_suite/handshake', methods=['GET', 'POST'])
def audio_suite_handshake():
    """Validates hardware trial attestation and provides application update metadata."""
    releases = {}
    active_is_released = True
    try:
        from audio_suite_mod import get_releases_data, is_release_publicly_visible
        releases = get_releases_data()
        active_is_released = is_release_publicly_visible(releases)
    except Exception:
        pass
    active_version = releases.get('version', LATEST_AUDIO_SUITE_VERSION)
    active_download_url = releases.get('download_url', AUDIO_SUITE_DOWNLOAD_URL)
    active_changelog = releases.get('changelog', AUDIO_SUITE_CHANGELOG)

    if request.method == 'GET':
        return jsonify({
            'service': 'Audio Playback Suite Attestation & Update Service',
            'status': 'ONLINE',
            'latest_version': active_version,
            'download_url': active_download_url,
        })

    data = request.get_json(silent=True) or {}
    hwid = data.get('hwid')
    if not hwid:
        return jsonify({'error': 'Missing hardware identifier'}), 400

    hwid = str(hwid).strip()
    app_version = str(data.get('app_version', '1.0.0')).strip()
    local_first_run = data.get('local_first_run')
    if isinstance(local_first_run, (int, float)):
        local_first_run = int(local_first_run)
    else:
        local_first_run = None

    licenses = {}
    if AUDIO_SUITE_LICENSES_FILE.exists():
        try:
            licenses = json.loads(AUDIO_SUITE_LICENSES_FILE.read_text(encoding='utf-8'))
        except Exception as exc:
            sys_log.warning(f"Audio suite license store read error: {exc}")
            licenses = {}

    server_now = int(time.time())
    record = licenses.get(hwid)

    if not record:
        inception = local_first_run if local_first_run and 0 < local_first_run <= server_now else server_now
        record = {
            'hwid': hwid,
            'first_run': inception,
            'last_seen': server_now,
            'duration_days': 14,
            'app_version': app_version,
            'remote_revoked': False,
        }
        licenses[hwid] = record
    else:
        server_first_run = record.get('first_run', server_now)
        if local_first_run and 0 < local_first_run < server_first_run:
            record['first_run'] = local_first_run
        record['last_seen'] = server_now
        record['app_version'] = app_version

    first_run = record.get('first_run', server_now)
    duration_days = record.get('duration_days', 14)
    expires_at = first_run + (duration_days * 86400)
    is_revoked = record.get('remote_revoked', False)

    if is_revoked:
        status = 'REVOKED'
    elif server_now >= expires_at:
        status = 'EXPIRED'
    else:
        status = 'ACTIVE'

    record['status'] = status

    try:
        AUDIO_SUITE_LICENSES_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUDIO_SUITE_LICENSES_FILE.write_text(json.dumps(licenses, indent=2), encoding='utf-8')
    except Exception as exc:
        sys_log.error(f"Failed to persist audio suite licenses: {exc}")

    update_available = is_newer_version(active_version, app_version) if active_is_released else False
    days_remaining = max(0, int(math.ceil((expires_at - server_now) / 86400))) if status == 'ACTIVE' else 0

    return jsonify({
        'status': status,
        'hwid': hwid,
        'server_time': server_now,
        'first_run': first_run,
        'expires_at': expires_at,
        'duration_days': duration_days,
        'days_remaining': days_remaining,
        'remote_revoked': is_revoked,
        'update_available': update_available,
        'latest_version': active_version,
        'download_url': active_download_url,
        'changelog': active_changelog,
    })


AUDIO_SUITE_FEEDBACK_FILE = config.CONTENT_DIR / "audio_suite_feedback.json"


@app.route('/api/audio_suite/feedback', methods=['GET', 'POST'])
def audio_suite_feedback():
    """Collects and stores in-app bug reports and feature suggestions from Audio Playback Suite."""
    if request.method == 'GET':
        return jsonify({
            'service': 'Audio Playback Suite Feedback Service',
            'status': 'ONLINE',
        })

    data = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()
    if not message:
        return jsonify({'error': 'Message content is required'}), 400

    hwid = str(data.get('hwid', 'UNKNOWN')).strip()
    feedback_type = str(data.get('type', 'bug')).strip().lower()
    if feedback_type not in ('bug', 'suggestion', 'general'):
        feedback_type = 'general'
    subject = str(data.get('subject', 'Untitled Report')).strip()
    app_version = str(data.get('app_version', '1.0.0')).strip()
    server_now = int(time.time())

    item = {
        'id': str(uuid.uuid4())[:8],
        'hwid': hwid,
        'type': feedback_type,
        'subject': subject,
        'message': message,
        'app_version': app_version,
        'timestamp': server_now,
        'formatted_time': datetime.fromtimestamp(server_now).strftime('%Y-%m-%d %H:%M:%S'),
        'remote_addr': request.remote_addr or '',
    }

    feedback_list = []
    if AUDIO_SUITE_FEEDBACK_FILE.exists():
        try:
            feedback_list = json.loads(AUDIO_SUITE_FEEDBACK_FILE.read_text(encoding='utf-8'))
            if not isinstance(feedback_list, list):
                feedback_list = []
        except Exception as exc:
            sys_log.warning(f"Audio suite feedback read error: {exc}")
            feedback_list = []

    feedback_list.append(item)

    try:
        AUDIO_SUITE_FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUDIO_SUITE_FEEDBACK_FILE.write_text(json.dumps(feedback_list, indent=2), encoding='utf-8')
        sys_log.info(f"Received {feedback_type} feedback from HWID {hwid[:8]}...")
        # Automated alert to Admin via Hybrid Email Engine
        try:
            from email_engine import send_email, build_email_template
            email_body = f"<p><strong>Type:</strong> {feedback_type.upper()}</p><p><strong>HWID:</strong> {hwid}</p><p><strong>Subject:</strong> {subject}</p><p><strong>Message:</strong></p><blockquote style='background:#1a1a24;padding:12px;border-left:3px solid #00f3ff;'>{message}</blockquote>"
            html_msg = build_email_template(f"Audio Suite Alert: {subject}", email_body)
            send_email(
                to_address="admin@eprofile.local",
                subject=f"[Audio Suite Feedback] {subject}",
                html_content=html_msg
            )
        except Exception as mail_err:
            sys_log.warning(f"Could not dispatch email alert for feedback: {mail_err}")
        return jsonify({'success': True, 'id': item['id'], 'status': 'RECEIVED'})
    except Exception as exc:
        sys_log.error(f"Failed to persist audio suite feedback: {exc}")
        return jsonify({'error': 'Failed to save feedback on server'}), 500


# --- EMAIL ENGINE & ADMIN MAILBOX ROUTES ---
@app.route('/admin/mailbox', methods=['GET'])
def admin_mailbox():
    if not session.get('admin', False):
        flash("Admin authentication required to access the Mailbox.", "error")
        return redirect(url_for('login'))

    from email_engine import load_local_mailbox
    emails = load_local_mailbox(limit=100)
    has_google_json = (config.ROOT_DIR / ".google_credentials.json").exists()
    return render_template(
        'admin_mailbox.html',
        emails=emails,
        mail_backend=config.MAIL_BACKEND,
        mail_server=config.MAIL_SERVER,
        mail_port=config.MAIL_PORT,
        mail_username=config.MAIL_USERNAME,
        mail_password=config.MAIL_PASSWORD,
        mail_use_tls=config.MAIL_USE_TLS,
        default_sender=config.MAIL_DEFAULT_SENDER,
        has_google_json=has_google_json
    )


@app.route('/admin/mailbox/save_settings', methods=['POST'])
def admin_save_mailbox_settings():
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    if not session.get('admin', False):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        flash("Unauthorized", "error")
        return redirect(url_for('login'))

    data = request.get_json(silent=True) or request.form
    backend = data.get('backend', 'local').strip().lower()
    server_host = data.get('server', '').strip()
    port_str = str(data.get('port', '587')).strip()
    use_tls_val = data.get('use_tls')
    use_tls = use_tls_val in (True, '1', 'True', 'true', 'on')
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    default_sender = data.get('default_sender', '').strip()

    try:
        server_port = int(port_str)
    except ValueError:
        server_port = 587

    # Retain existing password if unchanged and field empty
    if not password and config.MAIL_PASSWORD and backend == 'smtp':
        password = config.MAIL_PASSWORD

    from email_engine import apply_gateway_settings, test_smtp_connection
    success, msg = apply_gateway_settings(
        backend=backend,
        server_host=server_host,
        server_port=server_port,
        use_tls=use_tls,
        username=username,
        password=password,
        default_sender=default_sender
    )

    conn_ok = True
    conn_msg = ""
    if success:
        sys_log.info(f"Admin updated email credentials for backend '{backend}'")
        if backend == 'smtp':
            conn_ok, conn_msg = test_smtp_connection()
            status_text = f"Settings saved! Gateway verified: {conn_msg}" if conn_ok else f"Settings saved, but gateway warning: {conn_msg}"
        else:
            status_text = "Settings saved! Email engine running in Local Mock Mode."

        if is_ajax:
            return jsonify({
                'success': True,
                'message': status_text,
                'conn_ok': conn_ok,
                'conn_msg': conn_msg,
                'backend': backend,
                'server': server_host,
                'port': server_port,
                'username': username,
                'default_sender': default_sender,
                'has_password': bool(password)
            })
        else:
            flash(status_text, "success" if conn_ok else "error")
    else:
        err_text = f"Error saving settings: {msg}"
        if is_ajax:
            return jsonify({'success': False, 'message': err_text}), 400
        else:
            flash(err_text, "error")

    return redirect(url_for('admin_mailbox'))


@app.route('/admin/mailbox/upload_google_json', methods=['POST'])
def admin_upload_google_json():
    if not session.get('admin', False):
        flash("Unauthorized", "error")
        return redirect(url_for('login'))

    raw_json = request.form.get('google_json', '').strip()
    uploaded_file = request.files.get('google_json_file')

    if uploaded_file and uploaded_file.filename:
        try:
            raw_json = uploaded_file.read().decode('utf-8')
        except Exception as e:
            flash(f"Failed to read uploaded file: {e}", "error")
            return redirect(url_for('admin_mailbox'))

    if not raw_json:
        flash("Please paste Google JSON content or select a JSON file.", "error")
        return redirect(url_for('admin_mailbox'))

    from email_engine import apply_google_service_json
    success, msg, meta = apply_google_service_json(raw_json)
    if success:
        sys_log.info(f"Admin saved Google credentials JSON: {meta.get('client_email')}")
        flash(f"{msg}", "success")
    else:
        flash(f"Failed to process Google JSON: {msg}", "error")

    return redirect(url_for('admin_mailbox'))


@app.route('/admin/mailbox/send_test', methods=['POST'])
def admin_send_test_email():
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    if not session.get('admin', False):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        flash("Unauthorized", "error")
        return redirect(url_for('login'))

    data = request.get_json(silent=True) or request.form
    to_address = data.get('to_address', '').strip()
    subject = data.get('subject', '').strip()
    message = data.get('message', '').strip()
    action_url = data.get('action_url', '').strip() or None

    if not to_address or not subject or not message:
        err_msg = "All fields (Recipient, Subject, Message) are required."
        if is_ajax:
            return jsonify({'success': False, 'message': err_msg}), 400
        flash(err_msg, "error")
        return redirect(url_for('admin_mailbox'))

    from email_engine import send_email, build_email_template
    formatted_body = f"<p>{message}</p>"
    html_msg = build_email_template(
        title=subject,
        body_html=formatted_body,
        action_url=action_url,
        action_label="Review Action" if action_url else None
    )

    success, msg, record = send_email(to_address=to_address, subject=subject, html_content=html_msg)
    if success:
        sys_log.info(f"Admin transmitted test email to {to_address} via {record.get('backend')}")
        if is_ajax:
            return jsonify({'success': True, 'message': f"Test dispatch succeeded: {msg}", 'record': record})
        flash(f"Test dispatch succeeded: {msg}", "success")
    else:
        sys_log.error(f"Failed email transmission to {to_address}: {msg}")
        if is_ajax:
            return jsonify({'success': False, 'message': f"Test dispatch failed: {msg}", 'record': record}), 400
        flash(f"Test dispatch failed: {msg}", "error")

    return redirect(url_for('admin_mailbox'))


@app.route('/admin/mailbox/clear', methods=['POST'])
def admin_clear_mailbox():
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    if not session.get('admin', False):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        return redirect(url_for('login'))

    from email_engine import clear_local_mailbox
    if clear_local_mailbox():
        sys_log.info("Admin purged local mailbox cache.")
        if is_ajax:
            return jsonify({'success': True, 'message': "Local mailbox cache cleared successfully."})
        flash("Local mailbox cache cleared successfully.", "success")
    else:
        if is_ajax:
            return jsonify({'success': False, 'message': "Failed to clear local mailbox cache."}), 500
        flash("Failed to clear local mailbox cache.", "error")

    return redirect(url_for('admin_mailbox'))


@app.route('/admin/mailbox/test_connection', methods=['POST'])
def admin_test_smtp_connection():
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    if not session.get('admin', False):
        if is_ajax:
            return jsonify({'success': False, 'message': 'Admin authentication required.'}), 403
        flash("Admin authentication required.", "error")
        return redirect(url_for('login'))

    from email_engine import test_smtp_connection
    success, msg = test_smtp_connection()
    if is_ajax:
        return jsonify({'success': success, 'message': msg})

    if success:
        flash(f"Gateway Attestation: {msg}", "success")
    else:
        flash(f"Gateway Attestation Warning: {msg}", "error")

    return redirect(url_for('admin_mailbox'))


@app.route('/api/admin/mailbox/<email_id>', methods=['GET'])
def api_admin_get_email(email_id):
    if not session.get('admin', False):
        return jsonify({'error': 'Unauthorized'}), 403

    from email_engine import get_email_by_id
    item = get_email_by_id(email_id)
    if not item:
        return jsonify({'error': 'Email not found'}), 404
    return jsonify(item)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', active_tab='error', content="<h2>404 - Page Not Found</h2>"), 404


if __name__ == '__main__':
    # Only run the local development server if NOT on PythonAnywhere
    import os
    if 'PYTHONANYWHERE_DOMAIN' not in os.environ:
        app.run(debug=True)