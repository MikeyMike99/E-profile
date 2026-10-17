[//]: # (DOC_ID: SIRA-DOC-02_19 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# PyWebView Desktop Wrapper Source Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_19-SEC-1)
This document records source code evidence for the standalone native desktop wrapper in `desktop_app.py`. It integrates the Quart/Hypercorn ASGI backend with `pywebview`, providing a zero-dependency desktop UI for Windows and Linux without spawning external browser windows.

---

## 2. Console Redirection & Background Server Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_19-SEC-2)
When compiled with `--windows-disable-console`, standard output and error handles are initialized to `None`. Writing to them results in silent crashes. `desktop_app.py` redirects them to local log files:

```python
# desktop_app.py: Lines 8-16
import os, sys, threading, urllib.request

# Safeguard for --windows-disable-console where stdout/stderr can be None
if sys.stdout is None:
    sys.stdout = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdout.log"), "a", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stderr.log"), "a", encoding="utf-8", buffering=1)

try:
    import webview
except ImportError:
    print("CRITICAL ERROR: 'pywebview' is not installed.")
    sys.exit(1)
```

---

## 3. Hypercorn ASGI Threading Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_19-SEC-3)
The Quart server is launched in a background daemon thread with its own `asyncio` event loop:

```python
# desktop_app.py: Background ASGI server runner
import asyncio

shutdown_event = asyncio.Event()

def start_server():
    """Starts the DevCore backend in a background thread using Hypercorn ASGI."""
    try:
        from hypercorn.config import Config
        from hypercorn.asyncio import serve
        import core.server as server
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        config = Config()
        config.bind = ["127.0.0.1:5000"]
        config.accesslog = None
        config.errorlog = sys.stderr
        
        loop.run_until_complete(serve(server.app, config, shutdown_trigger=shutdown_event.wait))
    except Exception as e:
        print(f"Server thread error: {e}")
```

---

## 4. Main Thread GUI Event Pump & Lifecycle Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_19-SEC-4)
The primary thread blocks on `webview.start()`, gracefully signaling the server thread when the user closes the window:

```python
# desktop_app.py: Window instantiation and lifecycle
def on_closed():
    """Triggered when user closes the PyWebView window."""
    print("Window closed by user. Initiating backend shutdown...")
    shutdown_event.set()
    sys.exit(0)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Wait for server readiness probe on 127.0.0.1:5000
    for _ in range(50):
        try:
            with urllib.request.urlopen("http://127.0.0.1:5000/api/health", timeout=0.2) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.1)

    window = webview.create_window(
        "Siraugga AI Portal",
        "http://127.0.0.1:5000",
        width=1200,
        height=800,
        min_size=(800, 600)
    )
    window.events.closed += on_closed
    webview.start()
```

---

## 5. Why Order Matters in GUI Initialization
[//]: # (SECTION_ID: SIRA-DOC-02_19-SEC-5)
1. **Redirect Stdout Before Imports**: If an imported module attempts to print while `sys.stdout` is `None`, Python raises an immediate `AttributeError` before error handlers can initialize.
2. **Readiness Probe Before Window Launch**: Launching `webview.create_window` before the ASGI server socket is listening causes the window to display a connection error.
3. **Daemon Threading for Server**: Setting `daemon=True` on the server thread ensures that if the main window exits abruptly, the operating system reaps the thread cleanly.

---

## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_19-SEC-6)
**Q: What does `sys.stdout = open(..., buffering=1)` mean?**  
A: `buffering=1` enables line-buffering. Every time `print()` outputs a line, it writes to disk immediately rather than waiting in an in-memory buffer.

**Q: Why can't we run `webview.start()` in a background thread?**  
A: Windows Win32 message queues and macOS Cocoa runloops require event pumps to run on Thread 0 (the primary OS process thread).

**Q: How does `shutdown_trigger=shutdown_event.wait` work?**  
A: Hypercorn watches this async event. As soon as `shutdown_event.set()` is called when the window closes, Hypercorn shuts down its listener socket and drains active connections.
