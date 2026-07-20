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
    blog_dir = config.CONTENT_DIR / "blog"
    content_dir = blog_dir / "content"
    order_file = blog_dir / "order.json"
    
    order_data = {}
    latest_filename = ""
    if order_file.exists():
        try: 
            order_data = json.loads(order_file.read_text())
            latest_filename = order_data.get('latest_filename', '')
        except: pass
    
    all_files = list(content_dir.glob("*.md"))
    if not all_files: return []
    
    sorted_files = sorted(all_files, key=lambda x: (int(order_data.get(x.name, 999)), x.name))
    
    processed = []
    for post in sorted_files:
        try:
            raw = post.read_text(encoding="utf-8")
            lines = raw.split('\n')
            title = lines[0].replace('#', '').strip() if lines else post.stem
            
            import bleach
            raw_html = markdown.markdown("\n".join(lines[1:]))
            allowed_tags = ['a', 'b', 'i', 'strong', 'em', 'p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'br', 'span', 'div', 'img', 'iframe']
            allowed_attrs = {'*': ['class', 'id', 'style'], 'a': ['href', 'target'], 'img': ['src', 'alt'], 'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']}
            safe_html = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs)
            
            processed.append({
                'filename': post.name,
                'id': post.stem.replace(".", "_").replace(" ", "_"),
                'title': title,
                'body': safe_html,
                'priority': int(order_data.get(post.name, 999)),
                'is_latest': (post.name == latest_filename)
            })
        except: pass
    return processed

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
    all_posts = [f.name for f in content_dir.glob("*.md")]
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