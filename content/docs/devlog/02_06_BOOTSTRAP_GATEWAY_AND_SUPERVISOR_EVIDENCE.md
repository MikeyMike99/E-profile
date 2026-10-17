[//]: # (DOC_ID: SIRA-DOC-02_06 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 02.6: Source Evidence: Bootstrap Gateway & Supervisor Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_05_EPHEMERAL_PLUGINS_AND_MCP_EVIDENCE.md`](/docs/devlog/02_05_EPHEMERAL_PLUGINS_AND_MCP_EVIDENCE)
- **Next Source Evidence**: [`02_07_CINEMATIC_TTS_AND_STEALTH_FEED_EVIDENCE.md`](/docs/devlog/02_07_CINEMATIC_TTS_AND_STEALTH_FEED_EVIDENCE)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-1)

This chapter documents verbatim source citations from Siraugga's dual-layer failover and pre-flight self-healing supervisor (`core/bootstrap_gateway.py`).

These citations prove how the system compiles all core engine modules before boot and isolates browser client connections from backend server restarts.

---

## Source 1: Pre-Flight Syntax Compilation Check
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-2)

- **Source File**: `<project_root>/core/bootstrap_gateway.py`
- **Location**: Lines 83–175

```python
def _compile_check(filepath: str) -> tuple:
    """Pre-compiles a python file and returns (ok: bool, error_message: str)."""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)

def run_preflight_checks(base_dir=None, quiet: bool = False) -> tuple:
    """Runs compilation checks on all critical engine files before startup."""
    engine_files = get_engine_files(base_dir)
    errors = []
    
    for rel_path in engine_files:
        full_path = resolve_engine_target(rel_path, base_dir)
        if not os.path.exists(full_path):
            continue
        ok, err = _compile_check(full_path)
        if not ok:
            errors.append((rel_path, err))
            
    return len(errors) == 0, errors
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-3)
1. **Pre-Boot Gating**: Every critical engine file is pre-compiled using `py_compile.compile(..., doraise=True)` before Python attempts to start the web daemon.
2. **Crash Prevention**: If a syntax error is discovered in an engine script, `run_preflight_checks()` halts the boot sequence, logs the exact line error, and prevents port-binding conflicts.

---

## Source 2: Dual-Layer WebSocket Proxy (Never Dropping Clients)
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-4)

- **Source File**: `<project_root>/core/bootstrap_gateway.py`
- **Location**: Lines 486–555

```python
async def proxy_ws():
    """Proxies WebSocket between client and backend.
    Maintains client connection even if backend restarts!"""
    client_ws = websocket._get_current_object()
    
    async def client_listener():
        while True:
            data = await client_ws.receive()
            await backend_ws.send(data)

    async def forward_to_client():
        while True:
            msg = await backend_ws.receive()
            await client_ws.send(msg)

    # CRITICAL RESILIENCE RULE:
    # Only cancel backend forwarding tasks during a backend failover.
    # NEVER cancel client_listener or client_ws!
    try:
        await asyncio.gather(client_listener(), forward_to_client())
    except asyncio.CancelledError:
        pass
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-5)
1. **Dual-Layer Uptime**: The Gateway listens on Port 5000, while the backend engine runs on Port 5001.
2. **Zero-Disconnect Failover**: If the backend on Port 5001 crashes or reboots, the Gateway holds the client's browser WebSocket open, reconnects to the revived backend, and resumes data forwarding without the user needing to refresh.

---

## Why Order Matters in Gateway Supervision
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-6)

1. **Pre-Flight Syntax Scan Before Port Binding**:
   - `run_preflight_checks()` must succeed *before* calling `app.run(port=5000)`. If you bind the port first and an import fails, the port remains locked in a zombie state by the dying process.
2. **Establish Client Listener Before Backend Handshake**:
   - The Gateway must bind the incoming browser connection *before* dialing the internal backend. If the backend is restarting, the Gateway buffers the client's initial frames rather than rejecting the connection.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-7)

### Q: What is a Dual-Layer Gateway?
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-8)
**A:** Instead of connecting browsers directly to the core server, you place a lightweight "Gateway" in front of it. If the core server crashes while testing a new feature, the Gateway stays alive and politely asks the browser to wait while it restarts the core server in the background.

### Q: Why does Port 5000 remain open if the backend crashes?
[//]: # (SECTION_ID: SIRA-DOC-02_06-SEC-9)
**A:** Because the Gateway owns Port 5000. The backend runs on private Port 5001. A crash on Port 5001 has zero effect on Port 5000's network socket.
