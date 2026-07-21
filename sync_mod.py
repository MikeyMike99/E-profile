import os
from pathlib import Path
from flask import Blueprint, request, jsonify
from config import Config

sync_bp = Blueprint('sync_bp', __name__)
config = Config()

@sync_bp.route('/sync', methods=['POST'])
def handle_sync():
    secret = request.form.get('secret')
    expected_secret = os.environ.get("SYNC_SECRET")
    
    if not expected_secret or secret != expected_secret:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    rel_path = request.form.get('path')
    if not rel_path:
        return jsonify({"status": "error", "message": "No path provided"}), 400
        
    # Security block: prevent overriding sensitive paths
    if '.git' in rel_path or 'profiles.json' in rel_path or '__pycache__' in rel_path or '.env' in rel_path:
        return jsonify({"status": "error", "message": "Forbidden path"}), 403
        
    file = request.files.get('file')
    if not file:
        return jsonify({"status": "error", "message": "No file provided"}), 400
        
    target_path = config.ROOT_DIR / rel_path
    
    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the file
    file.save(str(target_path))
    
    # Reload PythonAnywhere WSGI if it's a python file
    reloaded = False
    if target_path.suffix == '.py':
        wsgi_dir = Path("/var/www/")
        if wsgi_dir.exists():
            for wsgi_file in wsgi_dir.glob("*_wsgi.py"):
                try:
                    wsgi_file.touch()
                    reloaded = True
                except Exception:
                    pass
                    
    return jsonify({
        "status": "success", 
        "message": f"Updated {rel_path}",
        "reloaded": reloaded
    })
