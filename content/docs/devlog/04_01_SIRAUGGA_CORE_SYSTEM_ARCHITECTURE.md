[//]: # (DOC_ID: SIRA-DEV-04_01 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 04.1: Architecture Blueprint: Siraugga Core System Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Diagnostic Chapter**: [`../03_DIAGNOSTIC_TESTS/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS.md`](/docs/devlog/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS)
- **Next Architecture Chapter**: [`04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY.md`](/docs/devlog/04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY)

---

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-1)

The Siraugga engine bridges web clients, AI agent subprocesses, and host operating systems across Windows and Linux WSL. 

This chapter presents the unified architectural blueprint detailing data flows, lifecycle management, and boundary isolation.

---

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-2)
## Full End-to-End System Blueprint
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-2)

```text
+-------------------------------------------------------------------------------+
|                           Accessible Browser Client                           |
|  - Semantic HTML5 (No heading spam; ARIA live regions for speech readers)     |
|  - Native <textarea class="artifact-raw-editor"> for direct markdown editing  |
|  - 4-Second Keep-Alive Heartbeat ({"type": "ping"})                           |
|  - Monotonic ACK Delivery Protocol ({"type": "ack", "seq": N})                |
+---------------------------------------+---------------------------------------+
                                        |  WebSocket / HTTP Port 5000
                                        v
+-------------------------------------------------------------------------------+
|                      Quart Asynchronous Server Engine                         |
|  - Event Loop: Handles WebSockets & HTTP routes without blocking              |
|  - Safe Hot-Patch Sequence: py_compile -> snapshot -> in-memory swap/reload   |
|  - Token Broker & PII Scrubber: Intercepts and cleans outbound data streams   |
+-------------------+---------------------------------------+-------------------+
                    |                                       |
                    v                                       v
+---------------------------------------+   +-----------------------------------+
|      Security Manager (Zero-Trust)    |   |     Agent Manager (Supervisor)    |
| - 5 Classification Tiers (1 to 5)     |   | - Detached asyncio subprocesses   |
| - resolve_safe_path() canonical check |   | - Monotonic sequence queue buffer |
| - Workspace confinement (cwd per user)|   | - agy --trust --headless flags    |
+-------------------+-------------------+   +-------------------+---------------+
                    |                                       |
                    v                                       v
+---------------------------------------+   +-----------------------------------+
|          Raugus Resolver VFS          |   |       AI Agent CLI Process        |
| - Opaque keys (devcore.server.py)     |   | - Isolated from Windows host      |
| - Physical filesystem path hiding     |   | - Stream-JSON token generation    |
+---------------------------------------+   +-----------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-3)
## The 4 Primary Subsystems
[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-1)

### 1. The Screen-Reader-Optimized Client
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-1)
- Built with pure HTML5, Tailwind CSS, and lightweight JavaScript.
- Avoids complex `contenteditable` wrappers, utilizing native form controls that work natively with NVDA and JAWS virtual cursors.
- Implements the Flip Card UI for artifacts: front displays styled HTML; back reveals raw markdown editor focused automatically.

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-2)
### 2. The Asynchronous Quart Server
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-2)
- Operates on Port 5000 using asynchronous coroutines (`async`/`await`).
- Never executes blocking file writes on the main thread; dispatches long tasks to background workers.
- Supports zero-downtime hot-patching: updates modules live in memory without dropping connections.

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-3)
### 3. The Zero-Trust Security Manager
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-3)
- Enforces strict Role-Based Access Control (`admin`, `gamedev`, `modder`).
- Confines non-administrators strictly to assigned game project folders.
- Strips directory traversal characters and validates paths using `os.path.realpath`.

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-4)
### 4. The Detached Agent Orchestrator
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-4)
- Launches the AI CLI using `--trust`, `--headless`, and `--stream-json`.
- Survives browser reloads: tasks run independently in the background until completion.
- Buffers events in memory until explicitly acknowledged by the client.

---

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-4)
## Why Order Matters in System Lifecycles
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-4)

1. **Initialize Security Engine Before Web Routes**:
   - The security manager and tier maps must be compiled *before* the web server begins listening on Port 5000. If an incoming request arrives while rules are loading, unauthenticated access could occur.
2. **Buffer Stream Chunk Before WebSocket Dispatch**:
   - Every generated AI token must be stored in the replay deque *before* pushing it down the WebSocket. If the network fails during transmission, the token must already be safely in the buffer for replay.

---

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-6)

### Q: Why Quart instead of traditional Flask?
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-6)
**A:** Flask is synchronous; when handling long-running AI streams, a single Flask thread would freeze, preventing other users from browsing or sending heartbeats. Quart is natively asynchronous, allowing thousands of real-time events to stream simultaneously.

[//]: # (SECTION_ID: SIRA-DEV-04_01-SEC-7)
### Q: How do Flip Cards make Markdown editing accessible?
[//]: # (SECTION_ID: SIRA-DOC-04_01-SEC-7)
**A:** Standard WYSIWYG editors clutter the screen reader's buffer with hundreds of nested `<div>` and `<span>` elements. A Flip Card flips directly to a standard `<textarea>` where screen reader users can read and edit text line-by-line with standard arrow keys.
