import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, session, abort, request, redirect, url_for
import markdown

# --- 1. CONFIG & MODULE IMPORTS ---
from config import Config
from blog_mod import blog_bp, get_blog_data
from projects_mod import projects_bp, get_projects_data 
from surgery import surgery_bp  # Or wherever your surgery.py is located
from cert_mod import cert_bp, get_certifications_data

# --- 2. APP INITIALIZATION ---
config = Config()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "SECURE_KEY_2026_PROTOTYPE")

# --- 3. BLUEPRINT REGISTRATION ---
app.register_blueprint(blog_bp)
app.register_blueprint(projects_bp, url_prefix='/api/projects')
app.register_blueprint(surgery_bp, url_prefix='/api/projects/surgery')
app.register_blueprint(cert_bp)

class SystemLogger:
    def __init__(self):
        self.logs = []
    def log(self, type, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.logs.append({'time': timestamp, 'type': type, 'msg': msg})
    def error(self, msg): self.log("ERROR", msg)
    def info(self, msg): self.log("INFO", msg)

sys_log = SystemLogger()

@app.before_request
def restrict_access():
    """Security Layer: Handles handshake keys and session verification."""
    public_endpoints = ['login', 'static', 'certifications.get_cert_file']
    if request.endpoint in public_endpoints:
        return

    url_key = request.args.get('access')
    if url_key:
        if url_key == config.EMPLOYER_KEY:
            session['is_admin'] = False
            session['is_employer'] = True
            sys_log.info("Handshake: Employer session set.")
            return redirect(request.path)
        elif url_key == config.ADMIN_KEY:
            session['is_admin'] = True
            session['is_employer'] = False
            sys_log.info("Handshake: Admin session set.")
            return redirect(request.path)

    is_admin = session.get('is_admin', False)
    is_employer = session.get('is_employer', False)

    if not is_admin and not is_employer:
        if request.endpoint != 'login':
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
        is_employer=session.get('is_employer', False),
        is_admin=session.get('is_admin', False)
    )

# --- 5. PRIMARY ROUTING ---

@app.route('/', defaults={'path': 'home'})
@app.route('/<path:path>')
def dynamic_route(path):
    # CRITICAL: Prevents this route from stealing API calls meant for Surgery/Explorer
    if path.startswith('api'):
        # This tells Flask "Don't load a Markdown file, check the Blueprints!"
        abort(404)

    if path not in config.TABS: 
        abort(404)
    
    posts_data = None
    projects_list = None
    certs_data = None
    latest_shortcut = None

    if path == 'blog':
        posts_data = get_blog_data()
        latest_shortcut = next((p for p in posts_data if p.get('is_latest')), None) if posts_data else None
    elif path == 'projects':
        projects_list = get_projects_data()
    elif path == 'certifications':
        certs_data = get_certifications_data()

    if path == 'blog':
        template = 'blog.html'
    elif path == 'projects':
        template = 'projects.html'
    elif path == 'certifications':
        template = 'certifications.html'
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
        posts=posts_data, 
        projects=projects_list,
        certs=certs_data,
        latest_post=latest_shortcut
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        key_input = request.form.get('cyber_key')
        if key_input == config.ADMIN_KEY:
            session['is_admin'] = True
            session['is_employer'] = False
            return redirect(url_for('dynamic_route', path='home'))
        elif key_input == config.EMPLOYER_KEY:
            session['is_admin'] = False
            session['is_employer'] = True
            return redirect(url_for('dynamic_route', path='home'))
        elif key_input == config.USER_KEY:
            session['is_admin'] = False
            session['is_employer'] = False
            return redirect(url_for('dynamic_route', path='home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', active_tab='error', content="<h2>404 - Page Not Found</h2>"), 404

if __name__ == '__main__':
    app.run(debug=True)