import sys
import os
try:
    sys.path.insert(0, os.path.dirname(__file__))
except NameError:
    pass
import threading
import time
import urllib.request
import sys
import os
import subprocess

import sys
import os
import importlib.util
from importlib.abc import MetaPathFinder

class LiveOverrideFinder(MetaPathFinder):
    """
    OTA Drop-in Live Override for Python Modules.
    Injects at the front of sys.meta_path to intercept imports and load loose .py files
    located next to the .exe INSTEAD of the compiled Nuitka binary modules.
    """
    def find_spec(self, fullname, path, target=None):
        # Ignore builtin/stdlib common heavily used modules to speed up boot
        if fullname in ['sys', 'os', 'builtins', 'math', 'time', 'json']:
            return None
            
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        rel_path = fullname.replace('.', os.sep) + '.py'
        full_path = os.path.join(exe_dir, rel_path)
        
        if os.path.exists(full_path):
            print(f"[LIVE OVERRIDE] Hijacking compiled module, loading loose script: {fullname}")
            spec = importlib.util.spec_from_file_location(fullname, full_path)
            return spec
            
        rel_pkg_path = os.path.join(fullname.replace('.', os.sep), '__init__.py')
        full_pkg_path = os.path.join(exe_dir, rel_pkg_path)
        if os.path.exists(full_pkg_path):
            print(f"[LIVE OVERRIDE] Hijacking compiled package, loading loose package: {fullname}")
            spec = importlib.util.spec_from_file_location(fullname, full_pkg_path)
            spec.submodule_search_locations = [os.path.join(exe_dir, fullname.replace('.', os.sep))]
            return spec

        return None

# Inject before Nuitka's module loader
sys.meta_path.insert(0, LiveOverrideFinder())

# Safeguard for --windows-disable-console where stdout/stderr can be None
import os
import sys

def get_real_cwd():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

log_dir = get_real_cwd()

if sys.stdout is None:
    sys.stdout = open(os.path.join(log_dir, "stdout.log"), "a", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = open(os.path.join(log_dir, "stderr.log"), "a", encoding="utf-8", buffering=1)

try:
    import webview
except ImportError:
    print("CRITICAL ERROR: 'pywebview' is not installed.")
    print("Please run: pip install pywebview")
    input("Press Enter to exit...")
    sys.exit(1)

import asyncio

shutdown_event = asyncio.Event()

def start_server():
    """Starts the DevCore backend in a background thread using Hypercorn ASGI."""
    try:
        from core.bootstrap_gateway import run_preflight_checks
        run_preflight_checks(spawn_agent=False, quiet=False)
        from hypercorn.config import Config
        from hypercorn.asyncio import serve
        import core.server as server
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        config = Config()
        
        # 1. Generate/Ensure TLS certificates exist
        import os
        from generate_cert import generate_self_signed_cert
        cert_path = os.path.join(get_real_cwd(), "cert.pem")
        key_path = os.path.join(get_real_cwd(), "key.pem")
        generate_self_signed_cert(cert_path, key_path)
        
        # 2. Configure Hypercorn for dual-binding
        config.certfile = cert_path
        config.keyfile = key_path
        
        # TLS encryption for public/external access
        config.bind = ["0.0.0.0:5001"]
        # Plaintext exclusively for local EdgeWebView2 wrapper to prevent SSL validation errors
        config.insecure_bind = ["127.0.0.1:5000"]
        
        print("Starting DevCore Backend on 5001 (HTTPS) and 5000 (HTTP Localhost)")
        # Explicit shutdown_trigger bypasses Hypercorn signal installation in worker threads
        loop.run_until_complete(serve(server.app, config, shutdown_trigger=shutdown_event.wait))
    except Exception as e:
        with open(os.path.join(get_real_cwd(), "crash_log.txt"), "w") as crash_file:
            import traceback
            tb_str = traceback.format_exc()
            crash_file.write(tb_str)
        print(f"CRASH: {e}")
        
        # Self-heal logic
        try:
            from core.bootstrap_gateway import heal_crash
            heal_crash(tb_str, restart_process=True)
        except Exception as heal_err:
            print(f"Self-heal module error: {heal_err}")

def wait_for_server():
    """Polls localhost until the backend is fully booted and responsive."""
    print("Waiting for DevCore backend to boot...")
    max_retries = 30
    for _ in range(max_retries):
        try:
            urllib.request.urlopen("http://localhost:5000", timeout=1)
            print("Backend is online! Launching Desktop UI...")
            return True
        except Exception:
            time.sleep(0.5)
    
    print("ERROR: Backend failed to start in time.")
    with open(os.path.join(get_real_cwd(), "crash_log.txt"), "a") as crash_file:
        crash_file.write("ERROR: Backend failed to start in time.\n")
    input("Press Enter to exit...")
    return False


if __name__ == '__main__':
    # [COLD STORAGE] Unlock AI Transcripts Before Boot
    try:
        from security.cold_storage import unlock_brain, lock_brain
        unlock_brain()
    except Exception as e:
        print(f"Cold Storage Unlock Failed: {e}")

    # 1. Start the backend daemon in a background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Wait for the server to be ready
    if wait_for_server():
        try:
            # 3. Create the Native Desktop Window wrapper around our web UI
            webview.create_window(
                title="Siraugga", 
                url="http://localhost:5000",
                width=1280,
                height=800,
                min_size=(800, 600),
                background_color='#0f172a' # Matches Tailwind slate-900 background
            )
            
            # 4. Start the native window event loop
            webview.start(gui='edgechromium,mshtml')
        except Exception as e:
            import traceback
            with open(os.path.join(get_real_cwd(), "crash_log_ui.txt"), "w") as crash_file:
                crash_file.write(traceback.format_exc())
            print(f"UI CRASH: {e}")
            input("Press Enter to exit...")
        finally:
            shutdown_event.set()
            # [COLD STORAGE] Lock AI Transcripts on Shutdown
            try:
                from security.cold_storage import lock_brain
                lock_brain()
            except Exception as e:
                print(f"Cold Storage Lock Failed: {e}")
