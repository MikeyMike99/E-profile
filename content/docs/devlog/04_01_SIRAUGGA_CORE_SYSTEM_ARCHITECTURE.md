# Pillar 04.1: Architecture Blueprint: Siraugga Core System Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Diagnostic Chapter**: [`../03_DIAGNOSTIC_TESTS/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS.md`](/docs/devlog/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS)
- **Next Architecture Chapter**: [`04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY.md`](/docs/devlog/04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY)

---

## Overview

The Siraugga engine bridges web clients, AI agent subprocesses, and host operating systems across Windows and Linux WSL. 

This chapter presents the unified architectural blueprint detailing data flows, lifecycle management, and boundary isolation.

---

## Full End-to-End System Blueprint

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

## The 4 Primary Subsystems

### 1. The Screen-Reader-Optimized Client
- Built with pure HTML5, Tailwind CSS, and lightweight JavaScript.
- Avoids complex `contenteditable` wrappers, utilizing native form controls that work natively with NVDA and JAWS virtual cursors.
- Implements the Flip Card UI for artifacts: front displays styled HTML; back reveals raw markdown editor focused automatically.

### 2. The Asynchronous Quart Server
- Operates on Port 5000 using asynchronous coroutines (`async`/`await`).
- Never executes blocking file writes on the main thread; dispatches long tasks to background workers.
- Supports zero-downtime hot-patching: updates modules live in memory without dropping connections.

### 3. The Zero-Trust Security Manager
- Enforces strict Role-Based Access Control (`admin`, `gamedev`, `modder`).
- Confines non-administrators strictly to assigned game project folders.
- Strips directory traversal characters and validates paths using `os.path.realpath`.

### 4. The Detached Agent Orchestrator
- Launches the AI CLI using `--trust`, `--headless`, and `--stream-json`.
- Survives browser reloads: tasks run independently in the background until completion.
- Buffers events in memory until explicitly acknowledged by the client.

---

## Why Order Matters in System Lifecycles

1. **Initialize Security Engine Before Web Routes**:
   - The security manager and tier maps must be compiled *before* the web server begins listening on Port 5000. If an incoming request arrives while rules are loading, unauthenticated access could occur.
2. **Buffer Stream Chunk Before WebSocket Dispatch**:
   - Every generated AI token must be stored in the replay deque *before* pushing it down the WebSocket. If the network fails during transmission, the token must already be safely in the buffer for replay.

---

## Beginner Coder Q&A

### Q: Why Quart instead of traditional Flask?
**A:** Flask is synchronous; when handling long-running AI streams, a single Flask thread would freeze, preventing other users from browsing or sending heartbeats. Quart is natively asynchronous, allowing thousands of real-time events to stream simultaneously.

### Q: How do Flip Cards make Markdown editing accessible?
**A:** Standard WYSIWYG editors clutter the screen reader's buffer with hundreds of nested `<div>` and `<span>` elements. A Flip Card flips directly to a standard `<textarea>` where screen reader users can read and edit text line-by-line with standard arrow keys.
