import os
import json
import markdown
from pathlib import Path
from flask import Blueprint, session, request, jsonify, send_from_directory
from config import Config

cert_bp = Blueprint('certifications', __name__)
config = Config()

CERT_DIR = config.CONTENT_DIR / "certifications" / "digital badges and certificates"
ORDER_FILE = config.CONTENT_DIR / "certifications" / "order.json"

def get_certifications_data():
    if not CERT_DIR.exists():
        CERT_DIR.mkdir(parents=True, exist_ok=True)
        
    order_data = []
    if ORDER_FILE.exists():
        try:
            order_data = json.loads(ORDER_FILE.read_text(encoding='utf-8'))
        except:
            order_data = []
            
    certs = []
    
    # Recursively find files
    valid_exts = ['.pdf', '.png', '.jpg', '.jpeg', '.docx']
    
    for path in CERT_DIR.rglob('*'):
        if path.is_file():
            if path.suffix.lower() in valid_exts:
                rel_path = path.relative_to(CERT_DIR)
                provider = rel_path.parts[0] if len(rel_path.parts) > 1 else "General"
                
                # Check for MD description
                md_path = path.with_suffix('.md')
                description_html = ""
                if md_path.exists():
                    try:
                        md_text = md_path.read_text(encoding='utf-8')
                        import bleach
                        raw_html = markdown.markdown(md_text, extensions=['fenced_code', 'tables', 'nl2br'])
                        allowed_tags = ['a', 'b', 'i', 'strong', 'em', 'p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'br', 'span', 'div', 'img', 'iframe']
                        allowed_attrs = {'*': ['class', 'id', 'style'], 'a': ['href', 'target'], 'img': ['src', 'alt'], 'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']}
                        description_html = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs)
                    except:
                        pass

                # Fixed: Handle backslash conversion outside of the dictionary/f-string
                rel_path_str = str(rel_path).replace('\\', '/')

                # Custom formatting to preserve whitelist acronyms/proper nouns
                whitelist = ["IBM", "CompTIA", "Cisco", "Linux", "Python", "LinkedIn", "NQF", "IT", "AI"]
                whitelist_lower = {w.lower(): w for w in whitelist}
                
                raw_words = path.stem.replace('-', ' ').split()
                formatted_words = []
                for word in raw_words:
                    if word.lower() in whitelist_lower:
                        formatted_words.append(whitelist_lower[word.lower()])
                    else:
                        formatted_words.append(word.title())
                
                formatted_name = ' '.join(formatted_words)

                certs.append({
                    'id': rel_path_str,
                    'name': formatted_name,
                    'provider': provider,
                    'file_path': f"/api/certifications/files/{rel_path_str}",
                    'ext': path.suffix.lower(),
                    'description_html': description_html
                })
                
    # Sort by order.json if present
    if order_data:
        cert_dict = {c['id']: c for c in certs}
        sorted_certs = []
        for cid in order_data:
            if cid in cert_dict:
                sorted_certs.append(cert_dict.pop(cid))
        # append the rest that were not in order list
        sorted_certs.extend(cert_dict.values())
        return sorted_certs
        
    # Default sort by provider then name
    return sorted(certs, key=lambda x: (x['provider'], x['name']))

@cert_bp.route('/api/certifications/reorder', methods=['POST'])
def reorder_certs():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "UNAUTHORIZED"}), 403
        
    order_list = request.json.get('order', [])
    try:
        ORDER_FILE.write_text(json.dumps(order_list, indent=4), encoding='utf-8')
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from flask import send_from_directory
@cert_bp.route('/api/certifications/files/<path:filename>')
def get_cert_file(filename):
    target_dir = str(CERT_DIR.resolve())
    return send_from_directory(target_dir, filename)