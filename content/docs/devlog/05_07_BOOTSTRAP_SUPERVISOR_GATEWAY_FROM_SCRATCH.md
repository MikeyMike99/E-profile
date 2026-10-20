[//]: # (DOC_ID: SIRA-ARCH-05_07 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.7: From-Scratch Creation Guide: Bootstrap Supervisor Gateway

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_06_FORENSIC_SESSION_VAULT_FROM_SCRATCH.md`](/docs/devlog/05_06_FORENSIC_SESSION_VAULT_FROM_SCRATCH)
- **Next From-Scratch Guide**: [`05_08_CINEMATIC_TTS_PROXY_FROM_SCRATCH.md`](/docs/devlog/05_08_CINEMATIC_TTS_PROXY_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-1)

This guide walks you through building the **Bootstrap Gateway & Supervisor** (`bootstrap_gateway.py`) from a blank editor.

You will implement pre-flight syntax compilation checks to prevent startup crashes and build a dual-layer WebSocket proxy on Port 5000 that maintains browser connections even during backend server restarts.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-3)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-3)
```bash
nano bootstrap_gateway.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-4)
### Step 2: Implement Pre-Flight Syntax Compiler (Lines 1–25)
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-4)
```python
import os
import py_compile
import sys
from quart import Quart, websocket, jsonify

def preflight_check(directory: str) -> bool:
    """Pre-compiles all Python files in a directory to trap syntax errors before boot."""
    print(f"[PREFLIGHT] Checking Python syntax in {directory}...")
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith('.py'):
                fpath = os.path.join(root, f)
                try:
                    py_compile.compile(fpath, doraise=True)
                except py_compile.PyCompileError as err:
                    print(f"[FATAL SYNTAX ERROR] in {fpath}:\n  {err}")
                    return False
    print("[PREFLIGHT OK] All modules compiled successfully.")
    return True
```

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-5)
### Step 3: Implement Dual-Layer WebSocket Proxy (Lines 26–65)
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-5)
```python
gateway_app = Quart(__name__)
BACKEND_WS_URL = "ws://127.0.0.1:5001/ws"

@gateway_app.websocket('/ws')
async def proxy_endpoint():
    """Proxies WebSocket between browser client and private backend port 5001."""
    import websockets
    client_ws = websocket._get_current_object()
    
    try:
        async with websockets.connect(BACKEND_WS_URL) as backend_ws:
            async def forward_to_backend():
                while True:
                    data = await client_ws.receive()
                    await backend_ws.send(data)

            async def forward_to_client():
                while True:
                    msg = await backend_ws.recv()
                    await client_ws.send(msg)

            await asyncio.gather(forward_to_backend(), forward_to_client())
    except Exception as exc:
        print(f"[GATEWAY] Backend connection notice: {exc}")
        await client_ws.send_json({"type": "status", "text": "Backend restarting..."})
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-6)
## Why Order Matters in Gateway Execution
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-6)

1. **Preflight Compilation Before Quart Instantiation**:
   - `preflight_check()` must return `True` *before* the application starts listening for connections. Starting the server while modules have syntax bugs causes crashes on the first incoming user request.
2. **Handle Backend Reconnect in Gateway Loop**:
   - The Gateway must catch backend connection drops inside the proxy handler, allowing the browser socket to stay open while the backend reboots on Port 5001.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-7)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-7)

Verify that your gateway detects syntax errors and reports pre-flight status cleanly:

```bash
python3 -c "
from bootstrap_gateway import preflight_check
import tempfile, os

with tempfile.TemporaryDirectory() as td:
    # 1. Clean file test
    with open(os.path.join(td, 'clean.py'), 'w') as f:
        f.write('def ok(): return True\n')
    assert preflight_check(td) == True
    print('[PASS] Clean preflight passed.')

    # 2. Syntax error test
    with open(os.path.join(td, 'broken.py'), 'w') as f:
        f.write('def broken( syntax error!\n')
    assert preflight_check(td) == False
    print('[PASS] Broken syntax successfully intercepted!')
"
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-8)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-9)

### Q: Why run the backend on Port 5001?
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-9)
**A:** By reserving Port 5000 for the Gateway, users always see a responsive interface. The actual server logic runs on Port 5001, allowing administrators to hot-swap or restart the backend without changing the URL.

[//]: # (SECTION_ID: SIRA-ARCH-05_07-SEC-10)
### Q: What is `py_compile`?
[//]: # (SECTION_ID: SIRA-DOC-05_07-SEC-10)
**A:** `py_compile` is a built-in Python module that compiles `.py` source code into `.pyc` bytecode without executing it, catching syntax errors immediately.

> [!WARNING] Line Ending Advisory (CRLF vs LF)
> If you are authoring this file on Windows for execution within Linux or WSL, ensure your text editor saves with Unix line endings (`LF`). Windows carriage returns (`CRLF`) will cause bash and Python interpreters to fail with unexpected syntax errors.


---

## 10-Second Verification Checklist

To verify that your newly created file is functioning properly:
- [ ] Confirm the file is saved with the exact filename and correct extension in the target directory.
- [ ] Run `python3 <filename> --help` or execute the script in dry-run mode to verify clean startup.
- [ ] Inspect console output to confirm there are no syntax errors or missing module tracebacks.

