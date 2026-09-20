#
import os
import sys
import traceback
import subprocess
from pathlib import Path
import argparse
import json

# --- BULLETPROOF PATH INJECTION ---
local_lib = Path.home() / '.local' / 'lib'
if local_lib.exists():
    for py_dir in local_lib.glob('python*'):
        site_pkg = py_dir / 'site-packages'
        if site_pkg.exists() and str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))
# ---------------------------------

# Required dependencies
REQUIRED_PACKAGES = {
    'Flask': 'flask',
    'Markdown': 'markdown',
    'Werkzeug': 'werkzeug',
    'python-dotenv': 'dotenv',
    'bleach': 'bleach',
    'libcst': 'libcst',
    'requests': 'requests',
    'flask-socketio': 'flask_socketio'
}

# Required files/directories (Added sync_mod.py to pre-flight checks)
REQUIRED_PATHS = [
    'server.py',
    'config.py',
    'sync_mod.py',
    'templates',
    'static'
]

def install_package(package):
    """Attempts to install a package programmatically."""
    try:
        # WSGI sys.executable is uwsgi, so use python3 explicitly
        if package == 'python-dotenv':
            subprocess.run(['python3', '-m', 'pip', 'uninstall', '-y', 'dotenv'], capture_output=True)
            subprocess.check_call(['python3', '-m', 'pip', 'install', '--user', 'python-dotenv'])
        else:
            subprocess.check_call(['python3', '-m', 'pip', 'install', '--user', package])
        return True
    except Exception as e:
        return False

def generate_diagnostic_html(error_msg, traceback_str, missing_pkgs, missing_files):
    """Generates a diagnostic dashboard in raw HTML."""
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BOOTSTRAP | SYSTEM_DIAGNOSTICS</title>
        <style>
            :root {{
                --bg: #0a0a0f;
                --text: #e0e0e0;
                --cyan: #00e5ff;
                --magenta: #ff0055;
                --panel: rgba(20, 20, 25, 0.9);
                --font: 'Consolas', monospace;
            }}
            body {{
                background-color: var(--bg);
                color: var(--text);
                font-family: var(--font);
                padding: 40px;
                margin: 0;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
                background: var(--panel);
                border: 1px solid var(--magenta);
                padding: 30px;
                box-shadow: 0 0 30px rgba(255, 0, 85, 0.2);
            }}
            h1 {{
                color: var(--magenta);
                text-transform: uppercase;
                letter-spacing: 2px;
                border-bottom: 1px solid var(--magenta);
                padding-bottom: 10px;
            }}
            h2 {{
                color: var(--cyan);
                margin-top: 30px;
            }}
            .status-box {{
                background: rgba(0, 0, 0, 0.5);
                padding: 15px;
                border-left: 4px solid var(--cyan);
                margin: 10px 0;
            }}
            .status-box.error {{
                border-left-color: var(--magenta);
                color: #ffb3c6;
            }}
            pre {{
                background: #000;
                padding: 15px;
                border: 1px solid #333;
                overflow-x: auto;
                color: #a3be8c;
            }}
            ul {{
                list-style-type: square;
            }}
            li.missing {{ color: var(--magenta); }}
            li.found {{ color: var(--cyan); }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>[CRITICAL_FAILURE] Server Initialization Halted</h1>
            
            <div class="status-box error">
                <strong>ERROR:</strong> {error_msg}
            </div>
            
            <h2>[01] TRACEBACK_LOG</h2>
            <pre>{traceback_str}</pre>

            <h2>[02] DEPENDENCY_CHECK</h2>
            <ul>
    """
    for pkg, status in missing_pkgs.items():
        if status == 'MISSING':
            html += f"<li class='missing'>[MISSING] {pkg} (Attempted auto-install, failed. Please run: pip install --user {pkg})</li>"
        else:
            html += f"<li class='found'>[INSTALLED] {pkg}</li>"

    html += """
            </ul>

            <h2>[03] FILE_SYSTEM_CHECK</h2>
            <ul>
    """
    
    for path, status in missing_files.items():
        if status == 'MISSING':
            html += f"<li class='missing'>[MISSING] {path}</li>"
        else:
            html += f"<li class='found'>[FOUND] {path}</li>"
            
    html += """
            </ul>
            
            <h2>[04] RECOVERY_INSTRUCTIONS</h2>
            <div class="status-box">
                1. Ensure <strong>sync_mod.py</strong> and all required modules are uploaded.<br>
                2. Verify that <strong>SYNC_SECRET</strong> is set in your environment variables.<br>
                3. Click the green "Reload" button on your PythonAnywhere Web dashboard.
            </div>
        </div>
    </body>
    </html>
    """
    return html.encode('utf-8')

# The main WSGI application entry point
def application(environ, start_response):
    try:
        # Step 1: Set working directory and prioritize path
        BASE_DIR = Path(__file__).resolve().parent
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        os.chdir(str(BASE_DIR))
        
        missing_pkgs = {}
        missing_files = {}
        has_errors = False
        
        # Step 2: Check dependencies programmatically
        import importlib
        for pkg_name, import_name in REQUIRED_PACKAGES.items():
            try:
                mod = importlib.import_module(import_name)
                # Ensure the correct dotenv is installed
                if import_name == 'dotenv' and not hasattr(mod, 'load_dotenv'):
                    raise ImportError("Wrong dotenv package installed")
                missing_pkgs[pkg_name] = 'INSTALLED'
            except ImportError:
                success = install_package(pkg_name)
                if success:
                    missing_pkgs[pkg_name] = 'INSTALLED (Auto-Recovered)'
                else:
                    missing_pkgs[pkg_name] = 'MISSING'
                    has_errors = True

        # Step 3: Check required files/directories (including sync_mod.py)
        for path in REQUIRED_PATHS:
            target = BASE_DIR / path
            if target.exists():
                missing_files[path] = 'FOUND'
            else:
                missing_files[path] = 'MISSING'
                has_errors = True

        # Step 3.5: Verify if SYNC_SECRET environment variable is loaded
        # (This warns you if the secret is missing on the server without breaking startup entirely)
        sync_secret_set = os.environ.get("SYNC_SECRET") is not None

        # Step 4: If structural file or package errors exist, render the diagnostic page immediately
        if has_errors:
            html_bytes = generate_diagnostic_html(
                "System validation failed. Missing core components or sync module.",
                "None (Caught during pre-flight checks)",
                missing_pkgs,
                missing_files
            )
            status = '500 Internal Server Error'
            headers = [('Content-type', 'text/html; charset=utf-8')]
            start_response(status, headers)
            return [html_bytes]

        # Step 5: Attempt to import sync_mod and run the actual Flask app defensively
        try:
            import sync_mod  # Validates that sync_mod is functional
            from server import app as flask_app
            return flask_app(environ, start_response)
        except (ImportError, ModuleNotFoundError) as import_err:
            missing_files[str(import_err).split("'")[-1]] = 'MISSING (Import Failed)'
            html_bytes = generate_diagnostic_html(
                f"Missing module error: {import_err}",
                traceback.format_exc(),
                missing_pkgs,
                missing_files
            )
            status = '500 Internal Server Error'
            headers = [('Content-type', 'text/html; charset=utf-8')]
            start_response(status, headers)
            return [html_bytes]
        
    except Exception as e:
        traceback_str = traceback.format_exc()
        html_bytes = generate_diagnostic_html(
            str(e),
            traceback_str,
            missing_pkgs if 'missing_pkgs' in locals() else {},
            missing_files if 'missing_files' in locals() else {}
        )
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        return [html_bytes]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap and Maintenance Utility")
    parser.add_argument('--undo', '--rollback', action='store_true', help='Revert file renames using rename_history.json')
    args = parser.parse_args()

    if args.undo:
        BASE_DIR = Path(__file__).resolve().parent
        history_file = BASE_DIR / "rename_history.json"
        cert_dir = BASE_DIR / "content" / "certifications" / "digital badges and certificates"
        
        if not history_file.exists():
            print("No rename_history.json found. Nothing to rollback.")
            sys.exit(0)
            
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except Exception as e:
            print(f"Error reading history file: {e}")
            sys.exit(1)
            
        print(f"Attempting to rollback {len(history)} items...")
        success_count = 0
        
        for old_rel, new_rel in reversed(history):
            old_abs = cert_dir / old_rel
            new_abs = cert_dir / new_rel
            
            if not new_abs.exists():
                print(f"[SKIP] Target file not found (already reverted or moved): {new_rel}")
                continue
                
            if old_abs.exists():
                print(f"[SKIP] Original path already exists (avoiding overwrite): {old_rel}")
                continue
                
            try:
                old_abs.parent.mkdir(parents=True, exist_ok=True)
                new_abs.rename(old_abs)
                print(f"[OK] Reverted: {new_rel} -> {old_rel}")
                success_count += 1
            except Exception as e:
                print(f"[ERROR] Could not revert {new_rel}: {e}")
                
        print(f"\nRollback complete. Successfully restored {success_count}/{len(history)} items.")
        
        if success_count == len(history):
            history_file.unlink(missing_ok=True)
            print("Cleared rename_history.json.")
        else:
            print("WARNING: Not all files were restored. rename_history.json was kept.")
            
        sys.exit(0)
        
    print("This is a WSGI bootstrap file. Use --undo to rollback renames.")