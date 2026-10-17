[//]: # (DOC_ID: SIRA-DOC-05_21 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# PyWebView Desktop Wrapper from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_21-SEC-1)
Developers running AI portals in web browsers face constant interruptions from external browser popups, accidental tab closures, and unmanaged background server processes.

This guide details how to build `desktop_app.py` from scratch. It packages a Quart ASGI web server inside a native, standalone desktop window using `pywebview`. It handles headless console redirection, asynchronous server background threading, readiness probing, and clean multi-process lifecycle shutdown.

```
+-------------------------------------------------------------+
|                  Main Thread (GUI Event Loop)               |
|               webview.create_window() & webview.start()     |
+-------------------------------------------------------------+
                              |
                     Spawns Daemon Thread
                              |
                              v
+-------------------------------------------------------------+
|               Background Thread (Hypercorn ASGI)            |
|               Binds loopback 127.0.0.1:5000                 |
|               Serves Quart backend application              |
+-------------------------------------------------------------+
                              |
                     Window Closed Hook (WM_CLOSE)
                              |
                              v
+-------------------------------------------------------------+
|               Clean Multi-Process Shutdown                  |
|               Drains WebSocket connections                  |
|               Reaps child CLI subagent PIDs                 |
|               Terminates process cleanly                    |
+-------------------------------------------------------------+
```

---

## 2. Complete Python Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_21-SEC-2)
Save the following script as `desktop_app.py`:

```python
import os
import sys
import time
import threading
import urllib.request
import asyncio

# Step 1: Headless Console Redirection (Crucial for --windows-disable-console)
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
if sys.stdout is None:
    sys.stdout = open(os.path.join(LOG_DIR, "stdout.log"), "a", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = open(os.path.join(LOG_DIR, "stderr.log"), "a", encoding="utf-8", buffering=1)

try:
    import webview
except ImportError:
    print("FATAL: 'pywebview' is not installed. Run: pip install pywebview")
    sys.exit(1)

# Step 2: Minimal ASGI Application Simulation (or import your Quart app)
async def sample_app(scope, receive, send):
    assert scope['type'] == 'http'
    body = b"<!DOCTYPE html><html><body style='background:#0f172a;color:#fff;font-family:sans-serif;'><h1>Siraugga Desktop Portal</h1><p>Running inside native WebView2 window.</p></body></html>"
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [[b'content-type', b'text/html'], [b'content-length', str(len(body)).encode()]],
    })
    await send({'type': 'http.response.body', 'body': body})

shutdown_event = asyncio.Event()

# Step 3: Background Server Runner
def run_server_thread():
    """Runs the ASGI server in an isolated background thread with its own event loop."""
    try:
        from hypercorn.config import Config
        from hypercorn.asyncio import serve
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        cfg = Config()
        cfg.bind = ["127.0.0.1:5000"]
        cfg.accesslog = None
        cfg.errorlog = sys.stderr
        
        print("[SERVER] Starting Hypercorn ASGI server on 127.0.0.1:5000...")
        loop.run_until_complete(serve(sample_app, cfg, shutdown_trigger=shutdown_event.wait))
    except Exception as e:
        print(f"[SERVER ERROR] {e}")

# Step 4: Window Lifecycle Hooks
def on_window_closed():
    """Fired when the user clicks the native window close button."""
    print("[DESKTOP] Window closed. Triggering graceful shutdown...")
    shutdown_event.set()
    time.sleep(0.2)
    sys.exit(0)

# Step 5: Main Bootstrapper
if __name__ == "__main__":
    # Start server thread
    srv_thread = threading.Thread(target=run_server_thread, daemon=True)
    srv_thread.start()

    # Readiness probe: wait for 127.0.0.1:5000 to respond
    server_ready = False
    for attempt in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:5000", timeout=0.2) as resp:
                if resp.status == 200:
                    server_ready = True
                    break
        except Exception:
            time.sleep(0.1)

    if not server_ready:
        print("[FATAL] Server failed to start within 4 seconds. Exiting.")
        sys.exit(1)

    # Launch Native PyWebView Window
    window = webview.create_window(
        "Siraugga Standalone Workspace",
        "http://127.0.0.1:5000",
        width=1280,
        height=800,
        min_size=(900, 600)
    )
    window.events.closed += on_window_closed

    print("[DESKTOP] Starting GUI event pump on main thread...")
    webview.start()
```

---

## 3. Why Order Matters in Native Window Initialization
[//]: # (SECTION_ID: SIRA-DOC-05_21-SEC-3)
1. **Redirect Stdout Before Imports**: If an imported module attempts to log to a `None` stream, Python crashes with `AttributeError` before the GUI engine can load.
2. **Readiness Probe Before Window Display**: Polling the port ensures the webview never displays an ugly connection error page to the user.
3. **Run GUI on Main Thread**: Desktop window managers enforce that OS UI message pumps must execute on the primary thread (Thread ID 1).

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_21-SEC-4)
**Q: What is the difference between PyWebView and Electron?**  
A: PyWebView uses the operating system's built-in web engine (WebView2 on Windows, WebKit on macOS/Linux), resulting in tiny executables (<20MB) rather than shipping a whole browser bundle.

**Q: Why is `srv_thread` marked `daemon=True`?**  
A: Python exits automatically when only daemon threads remain. If the window closes abruptly, the OS reaps the server thread without hanging.

**Q: Can this script be compiled into a single `.exe` file?**  
A: Yes! You can compile it with Nuitka using:  
`nuitka --standalone --windows-disable-console --enable-plugin=tk-inter desktop_app.py`
