import os
import json
import hashlib
import uuid
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

class SystemLogger:
    def __init__(self):
        self.logs = []
    def log(self, type, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.logs.append({'time': timestamp, 'type': type, 'msg': msg})
    def error(self, msg): self.log("ERROR", msg)
    def info(self, msg): self.log("INFO", msg)
    def warning(self, msg): self.log("WARNING", msg)

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
    # CRITICAL: Prevents this route from stealing API calls meant for Surgery/Explorer
    if path.startswith('api'):
        abort(404)

    if path not in config.TABS: 
        parts = path.split('/')
        if parts[0] in config.TABS:
            flash(f"The requested content may have been relocated. Redirecting to {parts[0]}.", "info")
            return redirect(url_for('dynamic_route', path=parts[0]))
        return redirect(url_for('dynamic_route', path='home'))
        
    perms = session.get('permissions', [])
    if path != 'home' and not session.get('admin', False) and not session.get('is_employer', False):
        if f'view:tab:{path}' not in perms:
            flash("ACCESS DENIED: You lack permissions to view this section.", "error")
            return redirect(url_for('login'))
    
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
    else:
        template = 'base.html'

    html_content = ""
    if path not in ['blog', 'projects', 'certifications']:
        file_path = config.CONTENT_DIR / path / f"{path}.md"
        if file_path.exists():
            html_content = markdown.markdown(file_path.read_text())

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
        if user_data.get('uuid') == uuid_token:
            if user_data.get('require_click_only'):
                sec_fetch_site = request.headers.get('Sec-Fetch-Site', 'none')
                if sec_fetch_site == 'none':
                    flash("Access blocked: Magic Link must be clicked from an external source, not pasted directly.", "error")
                    sys_log.error(f"Pasted Magic Link rejected for {user_data.get('username')}")
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
            
            if is_admin:
                return redirect(url_for('admin'))
            else:
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
                "require_click_only": False
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
            require_click_only = request.form.get('require_click_only') == 'on'
            is_admin = request.form.get('is_admin') == 'on'
            is_employer = request.form.get('is_employer') == 'on'
            
            if username and token:
                hashed_token = hash_token(token)
                profiles[hashed_token] = {
                    "username": username,
                    "label": label,
                    "uuid": str(uuid.uuid4()),
                    "permissions": permissions,
                    "require_click_only": require_click_only,
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

    # Restore Quarantine Logic
    quarantined_files = {}
    quarantine_log_file = config.ROOT_DIR / ".backup" / "quarantine_log.json"
    if quarantine_log_file.exists():
        try: quarantined_files = json.loads(quarantine_log_file.read_text())
        except: pass

    return render_template('manage_profiles.html', 
        profiles=profiles,
        dyn_tabs=dyn_tabs,
        dyn_blogs=dyn_blogs,
        dyn_certs=dyn_certs,
        dyn_projects=dyn_projects,
        unindexed=unindexed,
        git_status=git_status,
        quarantined_files=quarantined_files,
        is_admin=session.get('admin', False)
    )

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
        
    token_hash = request.form.get('token_hash', '')
    profiles = load_profiles()
    
    if token_hash in profiles:
        # Failsafe: Prevent the active system admin from deleting themselves
        if profiles[token_hash].get('username') != session.get('username'):
            del profiles[token_hash]
            save_profiles(profiles)
            flash("Profile successfully terminated.", "info")
            
    return redirect(url_for('admin'))

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if not session.get('admin', False): 
        return jsonify({"error": "Unauthorized"}), 403
        
    token_hash = request.form.get('token_hash', '')
    profiles = load_profiles()
    
    if token_hash in profiles:
        # Update user configuration
        profiles[token_hash]['username'] = request.form.get('username', profiles[token_hash]['username']).strip()
        profiles[token_hash]['label'] = request.form.get('label', profiles[token_hash]['label']).strip()
        profiles[token_hash]['permissions'] = request.form.getlist('permissions')
        profiles[token_hash]['is_admin'] = request.form.get('is_admin') == 'on'
        profiles[token_hash]['is_employer'] = request.form.get('is_employer') == 'on'
        profiles[token_hash]['require_click_only'] = request.form.get('require_click_only') == 'on'
        
        save_profiles(profiles)
        flash("Profile identity and permissions updated.", "success")
        
    return redirect(url_for('admin'))

@app.route('/reset_pin', methods=['POST'])
def reset_pin():
    if not session.get('admin', False): 
        return jsonify({"error": "Unauthorized"}), 403
        
    old_token_hash = request.form.get('token_hash', '')
    new_token = request.form.get('new_token', '').strip()
    profiles = load_profiles()
    
    if old_token_hash in profiles and new_token:
        # Migrate data to new hash
        user_data = profiles.pop(old_token_hash)
        new_token_hash = hash_token(new_token)
        profiles[new_token_hash] = user_data
        
        save_profiles(profiles)
        flash(f"PIN successfully reset for {user_data.get('username')}.", "success")
        
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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', active_tab='error', content="<h2>404 - Page Not Found</h2>"), 404

if __name__ == '__main__':
    # Only run the local development server if NOT on PythonAnywhere
    import os
    if 'PYTHONANYWHERE_DOMAIN' not in os.environ:
        app.run(debug=True)