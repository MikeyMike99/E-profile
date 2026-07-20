#every thing is working perfectperfectly. we will just change look of things later on
import os, shutil, csv, markdown
from pathlib import Path
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, jsonify, send_from_directory
import subprocess 
import json
from logger import LOGG
from werkzeug.security import generate_password_hash, check_password_hash

# 1. DEFINE APP FIRST (Set static_folder=None to allow our custom home/static route)
app = Flask(__name__, static_folder=None)
app.secret_key = "echos_lab_2026_key"

# -----------------------------
# Configuration & Auto-Provisioning
# -----------------------------
USER_NAME = "Mike"
ADMIN_HASH = generate_password_hash("Mike") 
NAV_TABS = ["home", "bio", "projects", "courses", "certifications", "blog"]

BASE_DIR = Path(__file__).parent
CONTENT_DIR = BASE_DIR / "content"
PROJECTS_DIR = CONTENT_DIR / "projects"
FEEDBACK_FILE = CONTENT_DIR / "feedback.csv"

# 2. NOW DEFINE YOUR ROUTES AND FUNCTIONS
def provision_system():
    """Ensures folders exist for every tab and sub-folders for assets."""
    for folder in [CONTENT_DIR, PROJECTS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    
    for tab in NAV_TABS:
        tab_path = CONTENT_DIR / tab
        tab_path.mkdir(parents=True, exist_ok=True)
        
        # Creates the side-by-side folders for your sound engine / web assets
        (tab_path / "audio").mkdir(exist_ok=True)
        (tab_path / "video").mkdir(exist_ok=True)
        (tab_path / "static").mkdir(exist_ok=True)
        
        index_md = tab_path / "index.md"
        if not index_md.exists():
            index_md.write_text(f"# {tab.upper()}\nDefault content for {tab}.")

# 3. FIX THE STATIC ROUTE (Use this version to find E:\e_profile\content\home\static)
@app.route('/static/<path:filename>')
def custom_static(filename):
    # Dynamically builds the path to your home static folder
    target_dir = os.path.abspath(CONTENT_DIR / "home" / "static")
    return send_from_directory(target_dir, filename)

@app.before_request
def check_login():
    provision_system()
    # Ensure custom_static is allowed so images load on the login page
    allowed_endpoints = ['login', 'static', 'custom_static']
    if not session.get('admin') and request.endpoint not in allowed_endpoints:
        return redirect(url_for('login'))

# -----------------------------
# Project Feedback Logic (Custom Function)
# -----------------------------
def get_projects_html():

    voted_projects = session.get('voted_projects', [])
    is_admin = session.get('admin', False)
    
    order_file = PROJECTS_DIR / "order.json"
    order_data = {}
    if order_file.exists():
        try:
            order_data = json.loads(order_file.read_text())
        except: order_data = {}

    html = f"""
    <style>
        .project-card:focus {{ border: 3px solid #00ffff !important; background: #f0fdff; outline: none; }}
        .split-view {{ display: flex; gap: 20px; align-items: start; }}
        .left-pane {{ flex: 2; }}
        .right-pane {{ flex: 1; border-left: 1px solid #ddd; padding-left: 20px; min-width: 200px; }}
        .thumbs button {{ font-size: 1.5rem; cursor: pointer; margin-right: 10px; background: white; border: 1px solid #ccc; padding: 5px 10px; border-radius: 5px; }}
        /* Search Bar Styling */
        .search-wrapper {{ margin-bottom: 25px; }}
        #project-search {{ 
            width: 100%; padding: 15px; border: 2px solid #007bff; 
            border-radius: 8px; font-size: 1.1rem; box-sizing: border-box;
        }}
    </style>

    <div class="search-wrapper">
        <label for="project-search" style="font-weight:bold; display:block; margin-bottom:8px;">SEARCH ENGINES:</label>
        <input type="text" id="project-search" placeholder="Type to filter engines..." oninput="filterProjects()">
        <div id="search-results-announcer" aria-live="polite" style="position:absolute; left:-9999px;"></div>
    </div>

    <div class="admin-controls">
        <button id="main-build-btn" class="main-cta" onclick="toggleBuilder(true)">+ Build New Project</button>
        <div id="project-builder" class="builder-box" style="display:none;">
            <input type="text" id="new-proj-name" placeholder="New Project Name...">
            <div style="display:flex; gap:10px;">
                <button class="btn-confirm" onclick="submitNewProject()">Initialize</button>
                <button class="btn-cancel" onclick="toggleBuilder(false)">Cancel</button>
            </div>
        </div>
    </div>
    
    <div id="project-list-container">
    """

    all_folders = [f for f in PROJECTS_DIR.iterdir() if f.is_dir()]
    folders = sorted(all_folders, key=lambda x: (int(order_data.get(x.name, 999)), x.name))

    for index, proj in enumerate(folders):
        p_name = proj.name
        is_locked = p_name in voted_projects
        disabled_attr = "disabled" if is_locked else ""
        
        index_md = proj / "content" / "index.md"
        if not index_md.exists():
            (proj / "content").mkdir(parents=True, exist_ok=True)
            index_md.write_text(f"# {p_name.upper()}")
        
        md_content = markdown.markdown(index_md.read_text(encoding="utf-8"))
        prev_name = folders[index-1].name if index > 0 else ""
        next_name = folders[index+1].name if index < len(folders)-1 else ""

        html += f"""
        <article class="project-card" id="card-{p_name}" 
             tabindex="0" 
             onkeydown="handleSwap(event, '{p_name}', '{prev_name}', '{next_name}')"
             style="border: 2px solid {'#007bff' if is_admin else '#e2e8f0'}; margin-bottom:15px; background: white; padding:10px;">
             
            <div class="project-header" onclick="toggleProject('{p_name}')" style="cursor:pointer; display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:1.1rem;">📦 {p_name.upper()} (Pos {index + 1})</strong>
                <span id="icon-{p_name}" style="font-size:1.5rem; font-weight:bold;">+</span>
            </div>
            
            <div id="details-{p_name}" class="project-details" style="display:none; padding-top:15px; border-top:1px solid #eee; margin-top:10px;">
                <div class="split-view">
                    <div class="left-pane">
                        <div class="markdown-body">{md_content}</div>
                        <br>
                        <button class="btn-delete" onclick="confirmDelete('{p_name}')" style="background:#fee2e2; color:#b91c1c; border:1px solid #f87171; padding:5px 10px; border-radius:4px; cursor:pointer;">Delete Engine</button>
                    </div>
                    
                    <div class="right-pane" id="feedback-area-{p_name}">
                        <p style="font-weight:bold; font-size:0.75rem; color:#666; margin-bottom:10px; text-transform:uppercase;">Rate Performance</p>
                        <div class="thumbs">
                            <button id="up-{p_name}" {disabled_attr} onclick="prepVote('{p_name}', 'Positive')">👍</button>
                            <button id="down-{p_name}" {disabled_attr} onclick="prepVote('{p_name}', 'Negative')">👎</button>
                        </div>
                        <div id="input-zone-{p_name}" style="display:none; margin-top:15px;">
                            <input type="hidden" id="val-{p_name}">
                            <textarea id="txt-{p_name}" placeholder="Add comment & press Enter..." style="width:100%; height:80px; padding:8px; border:1px solid #ccc; border-radius:4px;" onkeydown="checkEnter(event, '{p_name}')"></textarea>
                        </div>
                        <div id="msg-{p_name}" style="display:{'block' if is_locked else 'none'}; color:#16a34a; font-weight:bold; margin-top:10px; font-size:0.9rem;">
                            ✓ FEEDBACK LOGGED
                        </div>
                    </div>
                </div>
            </div>
        </article>"""
    
    return html + "</div>" + get_project_scripts()

def get_project_scripts():
    return """
    <script>
    function toggleProject(name) {
        const details = document.getElementById('details-' + name);
        const icon = document.getElementById('icon-' + name);
        if (details.style.display === 'none') {
            details.style.display = 'block';
            icon.innerText = '-';
        } else {
            details.style.display = 'none';
            icon.innerText = '+';
        }
    }

    function filterProjects() {
        const query = document.getElementById('project-search').value.toLowerCase();
        const cards = document.querySelectorAll('.project-card');
        const announcer = document.getElementById('search-results-announcer');
        let visibleCount = 0;

        cards.forEach(card => {
            // Checks title and markdown content
            const text = card.innerText.toLowerCase();
            if (text.includes(query)) {
                card.style.display = "block";
                visibleCount++;
            } else {
                card.style.display = "none";
            }
        });

        if (query.length > 0) {
            announcer.innerText = visibleCount + " projects matching " + query;
        } else {
            announcer.innerText = "";
        }
    }

    async function handleSwap(e, current, prev, next) {
        if (!e.ctrlKey || !e.altKey) return;
        let target = (e.key === "ArrowUp") ? prev : (e.key === "ArrowDown") ? next : "";
        if (target) {
            e.preventDefault();
            await fetch('/swap_projects', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({itemA: current, itemB: target})
            });
            sessionStorage.setItem('focusedProject', 'card-' + current);
            location.reload();
        }
    }

    window.addEventListener('load', () => {
        const lastFocused = sessionStorage.getItem('focusedProject');
        if (lastFocused) {
            const el = document.getElementById(lastFocused);
            if (el) el.focus();
            sessionStorage.removeItem('focusedProject');
        }
    });

    function prepVote(name, val) {
        document.getElementById('input-zone-'+name).style.display = 'block';
        document.getElementById('val-'+name).value = val;
        document.getElementById('txt-'+name).focus();
    }

    function checkEnter(e, name) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitVote(name);
        }
    }

    async function submitVote(name) {
        const val = document.getElementById('val-'+name).value;
        const txt = document.getElementById('txt-'+name).value;
        const res = await fetch('/log_feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({project: name, rating: val, comment: txt})
        });
        if (res.ok) {
            location.reload();
        }
    }
    </script>
    """
# -----------------------------
def wrap_html(title, content, is_login=False):
    nav_links = "".join([f'<a href="/{t if t != "home" else ""}" class="{"active" if t == title.lower() else ""}">{t.upper()}</a>' for t in NAV_TABS]) if not is_login else ""

    return f"""
    <html>
    <head>
        <title>{title} | {USER_NAME}</title>
        <style>
            body {{ margin: 0; font-family: Arial, sans-serif; background: #f8fafc; }}
            
            /* --- RESTORED HERO (45vh) --- */
            .hero {{
                height: 45vh; 
                background-image: linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)), url('/static/texture.png');
                background-size: cover; 
                background-position: center;
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: center; 
                color: white;
                position: relative;
            }}
            .logout-container {{ position: absolute; top: 20px; right: 20px; }}
            .btn-real-logout {{
                background: #e11d48; color: white; border: none; 
                padding: 10px 20px; border-radius: 6px; font-size: 11px; 
                font-weight: bold; cursor: pointer;
            }}
            .profile-pic {{ 
                width: 180px; 
                height: 220px; 
                border-radius: 50% / 40%; 
                border: 4px solid #00ffff; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
                object-fit: cover; 
            }}
            .name {{ 
                font-family: 'Arial Black', sans-serif; 
                font-size: 2.5rem; 
                margin-top: 1rem; 
                text-shadow: 2px 2px 5px rgba(0,0,0,0.7); 
            }}

            /* --- RESTORED BLUE NAV BUTTONS --- */
            nav {{ display: flex; justify-content: center; margin: 20px 0; gap: 15px; }}
            nav a {{ 
                padding: 12px 25px; 
                background: #007bff; 
                color: white; 
                text-decoration: none; 
                font-weight: bold; 
                border-radius: 8px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                transition: transform 0.2s, background 0.2s; 
            }}
            nav a:hover, nav a.active {{ background: #0056b3; transform: translateY(-3px); }}

            /* --- ESSENTIAL ENGINE STYLES (DO NOT REMOVE) --- */
            .main-content {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; background: white; min-height: 80vh; }}
            .project-card {{ border: 1px solid #e2e8f0; margin-bottom: 12px; border-radius: 8px; background: white; overflow:hidden; }}
            .project-header {{ padding: 18px; cursor: pointer; font-weight: bold; display: flex; justify-content: space-between; }}
            .project-details {{ padding: 25px; border-top: 1px solid #f1f5f9; background: #fafafa; }}
            .split-view {{ display: grid; grid-template-columns: 1fr 250px; gap: 20px; }}
            .thumbs button {{ font-size: 20px; padding: 10px; cursor: pointer; background: white; border: 1px solid #ddd; border-radius: 4px; width: 45%; }}
            textarea {{ width: 100%; height: 80px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; resize: none; }}
            .voted-msg {{ background: #10b981; color: white; padding: 10px; font-weight: bold; text-align: center; border-radius: 4px; font-size: 12px; }}
            .main-cta {{ background: #0f172a; color: white; padding: 15px; width: 100%; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-bottom: 20px; }}
            .builder-box {{ background:white; padding:20px; border:1px solid #007bff; margin-bottom:20px; border-radius:6px; }}
            .btn-confirm {{ background: #007bff; color:white; border:none; padding:10px; flex:1; border-radius:4px; cursor:pointer; }}
            .btn-cancel {{ background: #eee; border:none; padding:10px; flex:1; border-radius:4px; cursor:pointer; }}
            .btn-delete {{ color: #e11d48; background: none; border: 1px solid #e11d48; padding: 5px 10px; border-radius: 4px; cursor: pointer; margin-top: 15px; }}
            #test-btn {{ 
                display:none; position:fixed; bottom:40px; right:40px; 
                width:70px; height:70px; border-radius:50%; background:#e11d48; 
                color:white; border:none; cursor:pointer; font-weight:bold; 
                box-shadow: 0 10px 25px rgba(225,29,72,0.4); z-index: 2000;
            }}
            
            footer {{ 
                text-align: center; color: #888; font-size: 0.9rem; 
                margin: 4rem 0; border-top: 1px solid #ccc; padding-top: 1rem; 
            }}
        </style>
    </head>
    <body>
        {"" if is_login else f'''
        <div class="hero">
            <div class="logout-container">
                <button onclick="window.location.href='/logout'" class="btn-real-logout">LOGOUT</button>
            </div>
            <img src="/static/profile.jpg" alt="Profile" class="profile-pic">
            <div class="name">{USER_NAME}</div>
            <nav>{nav_links}</nav>
        </div>
        '''}
        <div class="main-content">{content}</div>
        <button id="test-btn" onclick="launchTest()">TEST</button>

        <footer>&copy; Copyright<br>your.email@example.com<br>South Africa</footer>

        <script>
            let currentProj = "";
            function toggleProject(name) {{
                const d = document.getElementById('details-' + name);
                const icon = document.getElementById('icon-' + name);
                const isOpen = d.style.display === 'block';
                document.querySelectorAll('.project-details').forEach(el => el.style.display = 'none');
                document.querySelectorAll('.project-header span[id^="icon-"]').forEach(el => el.innerText = '+');
                if(!isOpen) {{
                    d.style.display = 'block';
                    if(icon) icon.innerText = '-';
                    document.getElementById('test-btn').style.display = 'block';
                    currentProj = name;
                }} else {{
                    d.style.display = 'none';
                    if(icon) icon.innerText = '+';
                    document.getElementById('test-btn').style.display = 'none';
                    currentProj = "";
                }}
            }}
            function launchTest() {{ if(currentProj) window.open('/execute/' + currentProj, '_blank'); }}
            function prepVote(name, val) {{
                document.getElementById('val-' + name).value = val;
                document.getElementById('input-zone-' + name).style.display = 'block';
                document.getElementById('txt-' + name).focus();
            }}
            function checkEnter(e, name) {{ if(e.key === "Enter" && !e.shiftKey) {{ e.preventDefault(); sendFeedback(name); }} }}
            async function sendFeedback(name) {{
                const comment = document.getElementById('txt-' + name).value.trim();
                const rating = document.getElementById('val-' + name).value;
                if(!comment) return;
                const res = await fetch('/log_feedback', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{project: name, rating: rating, comment: comment}})
                }});
                if(res.ok) {{
                    document.getElementById('up-' + name).disabled = true;
                    document.getElementById('down-' + name).disabled = true;
                    document.getElementById('input-zone-' + name).style.display = 'none';
                    document.getElementById('msg-' + name).style.display = 'block';
                }}
            }}
            function toggleBuilder(show) {{
                document.getElementById('project-builder').style.display = show ? 'block' : 'none';
                document.getElementById('main-build-btn').style.display = show ? 'none' : 'block';
            }}
            async function submitNewProject() {{
                const name = document.getElementById('new-proj-name').value.trim();
                if(!name) return;
                let formData = new FormData();
                formData.append('proj_name', name);
                await fetch('/create_project', {{ method: 'POST', body: formData }});
                location.reload();
            }}
            function confirmDelete(name) {{ if(confirm("Delete engine " + name + "?")) window.location.href = "/delete_project/" + name; }}
        </script>
    </body>
    </html>
    """

# -----------------------------
# Routes
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if check_password_hash(ADMIN_HASH, request.form.get("password")):
            session['admin'] = True
            return redirect(url_for('home'))
    return wrap_html("Login", '<div style="max-width:350px; margin: 120px auto; text-align:center;"><form method="post"><input type="password" name="password" placeholder="Passkey" autofocus><button>UNLOCK</button></form></div>', True)

@app.route("/")
def home():
    return dynamic_tab("home")

@app.route("/log_feedback", methods=["POST"])
def log_feedback():
    data = request.json
    p = data['project']
    if 'voted_projects' not in session: session['voted_projects'] = []
    if p not in session['voted_projects']:
        v = session['voted_projects']
        v.append(p)
        session['voted_projects'] = v
        session.modified = True
        with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.now(), p, data['rating'], data['comment']])
    return jsonify({"status": "ok"})


@app.route("/swap_projects", methods=["POST"])
def swap_projects():
    if not session.get('admin'): return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    itemA = data.get('itemA')
    itemB = data.get('itemB')
    
    order_file = PROJECTS_DIR / "order.json"
    order_data = {}
    if order_file.exists():
        try:
            order_data = json.loads(order_file.read_text())
        except: order_data = {}

    # Get current priorities or assign based on index if missing
    # This ensures we always have a number to swap
    all_folders = sorted([f.name for f in PROJECTS_DIR.iterdir() if f.is_dir()])
    for i, name in enumerate(all_folders):
        if name not in order_data:
            order_data[name] = (i + 1) * 10

    # Swap the values
    valA = order_data.get(itemA)
    valB = order_data.get(itemB)
    
    order_data[itemA] = valB
    order_data[itemB] = valA
    
    order_file.write_text(json.dumps(order_data))
    return jsonify({"status": "ok"})

@app.route("/create_project", methods=["POST"])
def create_project():
    name = request.form.get("proj_name").strip().replace(" ", "_").lower()
    p = PROJECTS_DIR / name
    (p / "content").mkdir(parents=True, exist_ok=True)
    (p / "content" / "index.md").write_text(f"# {name.upper()}")
    return redirect(url_for('dynamic_tab', page_name='projects'))

@app.route("/delete_project/<name>")
def delete_project(name):
    shutil.rmtree(PROJECTS_DIR / name, ignore_errors=True)
    return redirect(url_for('dynamic_tab', page_name='projects'))



@app.route("/execute/<name>")
def execute(name):
    # Define the project path and the files we are looking for
    project_path = PROJECTS_DIR / name
    possible_entry_points = ["main.py", "app.py"]
    
    executable_file = None
    
    # 1. Search for the entry point file
    for filename in possible_entry_points:
        if (project_path / filename).exists():
            executable_file = project_path / filename
            break

    # 2. Try to run the file if found
    if executable_file:
        try:
            # Launch the process in the background
            # cwd ensures sound_api.py and assets load from the correct folder
            subprocess.Popen(["python", str(executable_file)], cwd=str(project_path))
            return f"<h1>Launching {name}...</h1><p>The engine is starting. You may close this tab.</p>"
        except Exception:
            # If the program crashes on startup or cannot run
            return "<h1>This program is under maintenance</h1>"
    
    # 3. If no main.py or app.py exists at all
    return "<h1>This program is under maintenance</h1>"
@app.route("/<page_name>")
def dynamic_tab(page_name):
    if page_name not in NAV_TABS: return "404", 404
    func_name = f"get_{page_name}_html"
    if func_name in globals():
        content = globals()[func_name]()
        return wrap_html(page_name.title(), content)
    file_path = CONTENT_DIR / page_name / "index.md"
    if file_path.exists():
        md_content = markdown.markdown(file_path.read_text(encoding="utf-8"))
        return wrap_html(page_name.title(), md_content)
    return wrap_html(page_name.title(), f"<h1>{page_name.title()}</h1><p>Content missing.</p>")

import json

import json

def get_blog_scripts():
    return """
    <script>
    async function changePos(filename, newPriority) {
        await fetch('/set_blog_priority', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename, priority: parseInt(newPriority)})
        });
        location.reload(); 
    }

    function toggleBlog(id) {
        const el = document.getElementById('blog-content-' + id);
        el.style.display = (el.style.display === 'none') ? 'block' : 'none';
    }

    async function saveBlogPost() {
        const title = document.getElementById('blog-title').value;
        const body = document.getElementById('blog-body').value;
        await fetch('/save_blog', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: title, body: body})
        });
        location.reload();
    }

    async function deleteBlogPost(filename) {
        if(confirm("Delete post?")) {
            await fetch('/delete_blog/' + filename, {method: 'POST'});
            location.reload();
        }
    }
    </script>
    """

def get_blog_html():
    blog_dir = CONTENT_DIR / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    
    order_file = blog_dir / "order.json"
    order_data = {}
    if order_file.exists():
        try:
            order_data = json.loads(order_file.read_text())
        except: order_data = {}

    is_admin = session.get('admin', False)
    all_files = [f for f in blog_dir.glob("*.md") if f.name != "index.md"]
    
    # We sort by the saved number. If a file isn't in the list, it goes to the bottom (999).
    posts = sorted(all_files, key=lambda x: (int(order_data.get(x.name, 999)), x.name))
    
    html = """
    <div class="builder-box">
        <h3>Create New Blog Update</h3>
        <input type="text" id="blog-title" placeholder="Title" style="width:100%; margin-bottom:10px;">
        <textarea id="blog-body" placeholder="Content" style="height:100px; width:100%;"></textarea>
        <button class="main-cta" onclick="saveBlogPost()">Publish Update</button>
    </div>
    <div id="announcer" aria-live="assertive" style="position:absolute; left:-9999px;"></div>
    <hr>
    <div id="blog-posts">
    """
    
    for index, post in enumerate(posts):
        post_id = post.stem.replace(".", "_")
        raw_text = post.read_text(encoding="utf-8")
        title = raw_text.split('\n')[0].replace('#', '').strip()
        
        # This is the "Truth": The actual priority the computer is using
        current_priority = order_data.get(post.name, index + 1)

        html += f"""
        <article class="project-card" style="margin-bottom:20px; border:2px solid #444;">
            <div style="background:#f8fafc; padding:10px; display:flex; gap:10px; align-items:center; border-bottom:1px solid #ccc;">
                <strong>Post {index + 1} (Priority {current_priority}): {title}</strong>
                {f'''
                <div style="margin-left:auto; display:flex; gap:5px;">
                    <button onclick="changePos('{post.name}', {int(current_priority) - 1})">▲</button>
                    <button onclick="changePos('{post.name}', {int(current_priority) + 1})">▼</button>
                    <input type="number" id="num-{post_id}" value="{current_priority}" style="width:50px;">
                    <button onclick="let v = document.getElementById('num-{post_id}').value; changePos('{post.name}', v)">Set</button>
                </div>
                ''' if is_admin else ""}
            </div>
            <div class="project-header" onclick="toggleBlog('{post_id}')" style="padding:15px; cursor:pointer;">
                <span>Read Content</span>
            </div>
            <div id="blog-content-{post_id}" class="project-details" style="display:none; padding:20px;">
                {markdown.markdown(raw_text)}
                <button class="btn-delete" onclick="deleteBlogPost('{post.name}')" style="color:red;">Delete</button>
            </div>
        </article>
        """
    return html + "</div>" + get_blog_scripts()

@app.route("/set_blog_priority", methods=["POST"])
def set_blog_priority():
    if not session.get('admin'): return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    filename = data.get('filename')
    try:
        priority = int(float(data.get('priority', 999)))
    except:
        priority = 999
    
    blog_dir = CONTENT_DIR / "blog"
    order_file = blog_dir / "order.json"
    
    order_data = {}
    if order_file.exists():
        try:
            order_data = json.loads(order_file.read_text())
            if isinstance(order_data, list): order_data = {f: i+1 for i, f in enumerate(order_data)}
        except: order_data = {}

    order_data[filename] = priority
    order_file.write_text(json.dumps(order_data))
    return jsonify({"status": "ok"})

provision_system()
if __name__ == "__main__":
    app.run(debug=True, port=5000)
