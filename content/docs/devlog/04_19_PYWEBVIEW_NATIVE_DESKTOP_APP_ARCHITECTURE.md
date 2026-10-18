[//]: # (DOC_ID: SIRA-DEV-04_19 | VERSION: v1.0 | SCOPE: DEV)

# PyWebView Native Desktop Application Architecture

[//]: # (SECTION_ID: SIRA-DEV-04_19-SEC-1)
## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_19-SEC-1)
The Siraugga Web Portal provides a real-time development interface accessible via standard web browsers. However, running inside browser tabs introduces friction: external address bars, browser extension conflicts, accidental tab closures, and unmanaged background processes.

The PyWebView architecture wraps the Quart/Hypercorn web server into a standalone native desktop window (`Siraugga IDE.exe`). It boots an in-process ASGI web server, attaches an isolated native webview window (Edge Chromium WebView2 on Windows, WebKitGTK on Linux), and orchestrates clean lifecycle shutdown.

```
+-------------------------------------------------------------+
|                     Desktop Entry Point                     |
|                   (bootstrap_gateway.py)                    |
+-------------------------------------------------------------+
          |                                        |
          | Spawns in Thread                       | Spawns in Main Thread
          v                                        v
+-----------------------+              +----------------------+
| Hypercorn ASGI Server |              | PyWebView Desktop GUI|
| Bound to 127.0.0.1    | <--- HTTP ---| (Chromium WebView2)  |
| Ephemeral Port / 5000 | <--- WS -----| Dedicated App Window |
+-----------------------+              +----------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_19-SEC-2)
## 2. Multi-Threaded Process & Window Coordination
[//]: # (SECTION_ID: SIRA-DOC-04_19-SEC-2)
Quart requires an asynchronous event loop, while GUI frameworks require exclusive control over the OS main UI thread. Running both in the same thread causes deadlock or freezing.

[//]: # (SECTION_ID: SIRA-DEV-04_19-SEC-1)
### Dual-Thread Concurrency Pattern
[//]: # (SECTION_ID: SIRA-DOC-04_19-SEC-1)
1. **Background Server Thread**: Hypercorn runs inside a dedicated Python `threading.Thread(daemon=True)`. It initializes an `asyncio` event loop and serves routes on `127.0.0.1:5000`.
2. **Main GUI Thread**: The main application thread invokes `webview.create_window(...)` and starts the event pump with `webview.start()`.
3. **Synchronization**: PyWebView blocks on the main thread until the user closes the window. Upon closure, the shutdown handler executes a graceful cleanup sequence.

---

[//]: # (SECTION_ID: SIRA-DEV-04_19-SEC-3)
## 3. Process Lifecycle and Clean Exit Orchestration
[//]: # (SECTION_ID: SIRA-DOC-04_19-SEC-3)
In a standalone executable bundle, closing the desktop window must never leave zombie Python or subprocess tasks running in the background.

```
[User Clicks Close Window (X)]
              |
              v
 [PyWebView 'closed' Hook Fires]
              |
              v
 [Signal Server Shutdown Event]
              |
              v
 [Reap Active CLI Agent Processes]
              |
              v
 [sys.exit(0) Closes Main Process]
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_19-SEC-4)
## 4. Why Order Matters in Desktop Wrapping
[//]: # (SECTION_ID: SIRA-DOC-04_19-SEC-4)
1. **Start Server Thread Before GUI Window**: The ASGI server must be listening on the target port before `webview.create_window()` navigates to the URL; otherwise, a blank `ERR_CONNECTION_REFUSED` screen is rendered.
2. **GUI Event Loop on Main Thread**: On Windows and macOS, UI message dispatchers must reside on the primary OS thread. Spawning `webview.start()` in a background thread will trigger fatal OS GUI errors.
3. **Process Termination After Window Exit**: Subprocesses must be reaped before exiting the main thread to ensure no orphaned headless daemons consume CPU or lock open ports.

---

[//]: # (SECTION_ID: SIRA-DEV-04_19-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_19-SEC-5)
**Q: Why use PyWebView instead of Electron?**  
A: PyWebView leverages the operating system's pre-installed browser engine (WebView2 on Windows). This results in a tiny binary footprint (<20MB) compared to Electron's massive Chromium bundle (>150MB).

**Q: Can external websites access the local PyWebView port?**  
A: No. The server binds strictly to `127.0.0.1` (loopback) and requires Master Signature authentication or session tokens for administrative API requests.

**Q: Does PyWebView support screen readers?**  
A: Yes. Because Windows WebView2 uses the native Microsoft Edge Chromium engine, NVDA and JAWS interact with the DOM, ARIA attributes, and live regions identically to modern desktop browsers.
