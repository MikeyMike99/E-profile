import json
import re
import markdown
from flask import Blueprint, render_template, session, abort, request, jsonify, redirect, url_for
from config import Config

config = Config()
# This "Blueprint" acts like a sub-module that plugs into your app
blog_bp = Blueprint('blog', __name__)

# --- SHARED UTILITY (Copied for isolation) ---
def get_slug(text):
    slug = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[\s-]+', '_', slug)

# --- THE BLOG DATA HANDLER ---
def get_blog_data():
    from flask import current_app
    import traceback
    
    blog_dir = config.CONTENT_DIR / "blog"
    content_dir = blog_dir / "content"
    order_file = blog_dir / "order.json"
    
    diagnostic_logs = []
    
    def log_diag(msg, level="INFO"):
        # Strictly read-only to avoid triggering Flask reloader loops
        diagnostic_logs.append(f"[{level}] {msg}")
        
    log_diag(f"Starting blog scan at absolute path: {content_dir.absolute()}")
    
    order_data = {}
    latest_filename = ""
    if order_file.exists():
        try: 
            import json
            order_data = json.loads(order_file.read_text())
            latest_filename = order_data.get('latest_filename', '')
        except Exception as e: 
            log_diag(f"Failed to load order.json: {e}", "WARNING")
    
    if not content_dir.exists():
        log_diag("CRITICAL: Directory does not exist!", "ERROR")
        return [], diagnostic_logs
        
    all_files = []
    for f in content_dir.iterdir():
        if not f.is_file(): continue
        if f.name.startswith('.') or f.name.startswith('~') or f.name == '__pycache__': continue
        if 'copy' in f.name.lower() or 'temp' in f.name.lower(): continue
        if f.suffix.lower() in ['.md', '.html']:
            all_files.append(f)
            
    log_diag(f"Found {len(all_files)} valid .md/.html files.")
    
    if not all_files: return [], diagnostic_logs
    
    sorted_files = sorted(all_files, key=lambda x: (int(order_data.get(x.name, 999)), x.name))
    
    processed = []
    for post in sorted_files:
        try:
            try:
                raw = post.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                log_diag(f"UnicodeDecodeError: {post.name} is not valid UTF-8. Skipping.", "WARNING")
                continue
                
            lines = raw.split('\n')
            title = lines[0].replace('#', '').strip() if lines and lines[0].startswith('#') else post.stem
            
            import bleach
            import markdown
            raw_html = markdown.markdown("\n".join(lines[1:]), extensions=['fenced_code', 'tables', 'nl2br']) if lines and lines[0].startswith('#') else markdown.markdown("\n".join(lines), extensions=['fenced_code', 'tables', 'nl2br'])
            allowed_tags = ['a', 'b', 'i', 'strong', 'em', 'p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'br', 'span', 'div', 'img', 'iframe']
            allowed_attrs = {'*': ['class', 'id', 'style'], 'a': ['href', 'target'], 'img': ['src', 'alt'], 'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']}
            safe_html = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs)
            
            processed.append({
                'filename': post.name,
                'id': post.stem.replace(".", "_").replace(" ", "_"),
                'title': title,
                'content': safe_html,
                'priority': int(order_data.get(post.name, 999)),
                'is_latest': (post.name == latest_filename)
            })
            log_diag(f"Successfully parsed: {post.name}")
        except Exception as e: 
            err_trace = traceback.format_exc()
            log_diag(f"FAILED to parse {post.name}: {e}\n{err_trace}", "ERROR")
            
    log_diag(f"Total processed blogs returning to frontend: {len(processed)}")
    return processed, diagnostic_logs

# --- BLOG ROUTES ---
@blog_bp.route("/set_blog_priority", methods=["POST"])
def set_blog_priority():
    if not session.get('is_admin'): return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    target_file = data['filename']
    new_priority = int(float(data['priority']))
    blog_dir = config.CONTENT_DIR / "blog"
    content_dir = blog_dir / "content"
    order_file = blog_dir / "order.json"
    order_data = {}
    if order_file.exists():
        try: order_data = json.loads(order_file.read_text())
        except: pass
        
    all_posts = []
    if content_dir.exists():
        for f in content_dir.iterdir():
            if f.is_file() and not (f.name.startswith('.') or f.name.startswith('~') or f.name == '__pycache__' or 'copy' in f.name.lower() or 'temp' in f.name.lower()):
                if f.suffix.lower() in ['.md', '.html']:
                    all_posts.append(f.name)
                    
    current_sequence = sorted(all_posts, key=lambda x: int(order_data.get(x, 999)))
    if target_file in current_sequence: current_sequence.remove(target_file)
    target_idx = max(0, min(new_priority - 1, len(current_sequence)))
    current_sequence.insert(target_idx, target_file)
    new_order = {filename: i + 1 for i, filename in enumerate(current_sequence)}
    if 'latest_filename' in order_data: new_order['latest_filename'] = order_data['latest_filename']
    order_file.write_text(json.dumps(new_order, indent=4))
    return jsonify({"status": "success"})

@blog_bp.route("/save_blog", methods=["POST"])
def save_blog():
    if not session.get('is_admin'): return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    filename = f"{get_slug(data['title'])}.md"
    path = config.CONTENT_DIR / "blog" / "content" / filename
    
    try:
        path.write_text(f"# {data['title']}\n\n{data['body']}", encoding="utf-8")
        order_file = config.CONTENT_DIR / "blog" / "order.json"
        order_data = {}
        if order_file.exists():
            try: order_data = json.loads(order_file.read_text())
            except: pass
        order_data['latest_filename'] = filename
        order_file.write_text(json.dumps(order_data, indent=4))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": f"FILE_WRITE_ERROR: {str(e)}"}), 500

@blog_bp.route("/delete_blog/<filename>", methods=["POST"])
def delete_blog(filename):
    if not session.get('is_admin'): return jsonify({"error": "Unauthorized"}), 403
    blog_dir = config.CONTENT_DIR / "blog"
    path = blog_dir / "content" / filename
    if path.exists(): 
        try:
            path.unlink()
            order_file = blog_dir / "order.json"
            if order_file.exists():
                try:
                    order_data = json.loads(order_file.read_text())
                    if order_data.get('latest_filename') == filename:
                        order_data['latest_filename'] = ""
                        order_file.write_text(json.dumps(order_data, indent=4))
                except: pass
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": f"FILE_DELETE_ERROR: {str(e)}"}), 500
    return jsonify({"status": "error", "message": "FILE_NOT_FOUND"}), 404