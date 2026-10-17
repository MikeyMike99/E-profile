# Pillar 01.2: Problems Encountered: WebSocket Dropouts & Refresh Crashes

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_01_TERMINAL_TEARING_AND_HEADLESS_BYPASS_TRAPS.md`](/docs/devlog/01_01_TERMINAL_TEARING_AND_HEADLESS_BYPASS_TRAPS)
- **Next Problem Chapter**: [`01_03_PATH_TRAVERSAL_AND_PRIVILEGE_ESCALATION.md`](/docs/devlog/01_03_PATH_TRAVERSAL_AND_PRIVILEGE_ESCALATION)

---

## Overview

As the Siraugga web portal scaled to handle heavier AI tasks, two severe stability bugs emerged:
1. **The Page Refresh Trap**: Refreshing the browser mid-task caused running AI subprocesses to terminate abruptly.
2. **The 30-Second WSL Dropout Crisis**: Heavy AI reasoning or file generation caused silent WebSocket disconnections.

This chapter documents the forensic investigation and engineering solutions implemented in `server.py` and `agent_manager.py`.

---

## Issue 1: The Page Refresh Trap (Task Termination)

### What Happened
In early implementations, when a user pressed `F5` or reloaded the browser page while the AI was generating code, the running AI task vanished. The terminal process was killed, leaving unfinished, half-written files scattered across the workspace.

### Why It Happened
The agent execution was originally bound directly to the lifespan of the WebSocket connection handler:

```python
# FLAWED EARLY PATTERN: Bound to connection scope
@app.websocket('/ws')
async def ws_handler():
    try:
        async for msg in websocket:
            await run_agent_in_connection(msg)
    finally:
        # Browser refresh closed socket -> finally block terminated agent!
        process.terminate()
```

When the browser reloaded, the WebSocket closed. The server's connection cleanup handler interpreted this closure as a user cancellation, terminating the background agent subprocess prematurely.

---

## Issue 2: The 30-Second WSL Dropout Crisis

### What Happened
During long agent operations (such as indexing multi-file codebases or running test suites), the browser would suddenly display:
```text
WebSocket Connection Closed (Code 1006 / Abnormal Closure)
```
The conversation stalled, and the user had to refresh and restart their query.

### Why It Happened
Two distinct architectural bottlenecks caused these drops:

1. **WSL 2 TCP Idle Timeout**: The Windows Subsystem for Linux (WSL 2) virtual network switch terminates idle TCP connections after exactly 30 seconds of network silence. If the AI was executing a complex command without emitting tokens, no packets crossed the wire, triggering a silent TCP reset.
2. **Event Loop Starvation**: Heavy file writes and synchronous parsing operations were being performed on Python's main asynchronous thread. This blocked the `asyncio` event loop, delaying WebSocket heartbeat frames and causing ping/pong timeouts.

---

## The Architectural Solution

To achieve 100% resilient streaming, the system was refactored with three decoupled layers:

### 1. Detached Background Task Manager
`AgentManager` was decoupled from the WebSocket lifecycle. When a task starts, it is stored in a server-wide registry:
- Browser refresh only drops the viewer, not the worker.
- When the browser reconnects, it queries `agent_manager.get_active_task()`, seamlessly resuming the live stream.

### 2. The 4-Second Client Keep-Alive Heartbeat
The browser's JavaScript engine transmits an explicit heartbeat every 4 seconds:
```javascript
setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'ping' }));
    }
}, 4000);
```
This guarantees constant packet traffic, preventing WSL 2 from terminating the TCP socket.

### 3. Non-Blocking Asynchronous I/O
All heavy file reading and subprocess streams are read using `asyncio.StreamReader` and dispatched asynchronously. The event loop is never blocked, ensuring WebSocket heartbeats are serviced within milliseconds.

---

## Why Order Matters in Stream Resilience

1. **Register Task in Global Store Before Starting Subprocess**:
   - The task ID and state must be recorded in the global manager *before* spawning `asyncio.create_subprocess_exec`. If an immediate error occurs on startup, the cleanup handler can inspect the record.
2. **Client Heartbeat Verification Before Socket Cleanup**:
   - The server must evaluate timestamp deltas rather than immediately killing connections on a missed frame. Temporary Wi-Fi jitter should not kill tasks.

---

## Beginner Coder Q&A

### Q: What is Code 1006 in WebSockets?
**A:** Code 1006 indicates an "Abnormal Closure." It means the connection was severed abruptly at the network or operating system level without sending a proper close handshake.

### Q: Why does WSL 2 have stricter network timeouts than native Linux?
**A:** WSL 2 runs inside a lightweight Hyper-V virtual machine connected to Windows via a virtual Network Address Translation (NAT) bridge. Virtual NAT tables aggressively prune idle connection entries to save host resources.
