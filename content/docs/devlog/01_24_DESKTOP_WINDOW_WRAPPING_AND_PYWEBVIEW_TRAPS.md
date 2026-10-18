[//]: # (DOC_ID: SIRA-DEV-01_24 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 01_24: Desktop Window Wrapping & PyWebView Traps

Running developer portals inside standard web browsers introduces tab clutter, accidental disconnections, and browser security restrictions. This chapter details how running inside external browsers degraded developer focus, and how wrapping the frontend into a native desktop window via **PyWebView (Microsoft WebView2)** created a dedicated, self-contained application.

---

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-1)
## What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-1)

During early developer trials where Siraugga operated as a local web server (`http://localhost:5000`) accessed via Google Chrome or Microsoft Edge:
- **Accidental Disconnections**: Developers routinely closed the browser tab by mistake while closing research tabs, dropping active WebSocket streams and aborting long-running agent tasks.
- **Multiple Tab Desynchronization**: Opening multiple browser tabs to the same URL created duplicate WebSocket clients that competed for the same monotonic event sequence, corrupting ACK state.
- **Browser Accessibility Clutter**: Screen readers had to navigate through browser address bars, extensions, and bookmarks before reaching the developer portal interface.

---

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-2)
## Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-2)

The issues stemmed from treating a mission-critical developer command center as an ephemeral webpage:
- **Lack of Dedicated Window Chrome**: In standard browsers, there is no application boundary. The web app is trapped within the browser's generic lifecycle.
- **Browser Sandboxing Boundaries**: Modern web browsers restrict local IPC, clipboard access, and filesystem interactions, forcing clumsy workarounds.
- **Electron Bloat**: Bundling a full Chromium browser via Electron would have added 200MB+ to the executable size and consumed 500MB of RAM.

```
Standard Browser Tab:
Chrome/Edge Window [Tab 1 | Tab 2 | DevCore Tab] ---> Accidental Ctrl+W closes active agent task!

Dedicated Native PyWebView Window:
Siraugga Desktop App (WebView2 Native Core) ---> Dedicated Process, Zero Tab Clutter, Direct Hotkeys!
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-3)

In native desktop window wrapping, initialization sequence controls lifecycle stability:
1. **Boot ASGI Backend Server First**: The background Quart/Hypercorn server must bind to its local port and confirm healthy status before the desktop window is launched.
2. **Initialize WebView Engine**: The GUI window must target the verified local URL (`http://127.0.0.1:5000`). Opening the window before the server is ready produces a blank white error screen.
3. **Bind Window Close Event to Clean Shutdown**: Closing the native desktop window must trigger a graceful shutdown signal to the backend server and its child subprocesses.

---

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-4)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-5)

### What is PyWebView?
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-5)
PyWebView is a lightweight Python library that opens a native GUI window displaying web content. On Windows, it uses Microsoft Edge WebView2, which is already built into Windows 10 and 11, requiring zero large downloads.

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-6)
### Why not use Electron?
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-6)
Electron bundles an entire copy of Google Chromium and Node.js with every application, resulting in 200MB+ installer files. PyWebView produces standalone executables under 45MB while using native Windows memory management.

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-7)
### Can screen readers interact with PyWebView windows?
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-7)
Yes! Because Microsoft WebView2 uses native Windows UI Automation (UIA) APIs, NVDA, JAWS, and Narrator treat the window exactly like a modern accessible desktop application.

---

[//]: # (SECTION_ID: SIRA-DEV-01_24-SEC-8)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-01_24-SEC-8)
- To see the primary source implementation of the portable distribution architecture, read [`02_SOURCE_EVIDENCE/02_15_BINARY_STAMPER_AND_PE_TRAILER_EVIDENCE.md`](/docs/devlog/02_15_BINARY_STAMPER_AND_PE_TRAILER_EVIDENCE).
- To view the complete portable distribution architecture blueprint, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_15_PORTABLE_EXECUTABLE_AND_BINARY_STAMPING_ARCHITECTURE.md`](/docs/devlog/04_15_PORTABLE_EXECUTABLE_AND_BINARY_STAMPING_ARCHITECTURE).
- To build a native desktop window wrapper from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_02_ACCESSIBLE_WEB_PORTAL_FROM_SCRATCH.md`](/docs/devlog/05_02_ACCESSIBLE_WEB_PORTAL_FROM_SCRATCH).
