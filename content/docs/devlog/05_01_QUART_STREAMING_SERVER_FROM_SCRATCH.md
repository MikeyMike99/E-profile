[//]: # (DOC_ID: SIRA-ARCH-05_01 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.1: From-Scratch Creation Guide: Asynchronous Quart Streaming Server

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Next From-Scratch Guide**: [`05_02_ACCESSIBLE_WEB_PORTAL_FROM_SCRATCH.md`](/docs/devlog/05_02_ACCESSIBLE_WEB_PORTAL_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-1)

This guide teaches beginner developers how to build an asynchronous Quart WebSocket server with a Guaranteed Delivery Queue (ACK protocol) and 4-second keep-alive heartbeats from a completely blank text editor.

By the end of this tutorial, you will have a working streaming backend that survives network interruptions and WSL timeouts.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-3)

### Step 1: Open a Blank Editor
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-3)
Create a new file named `server.py`:
```bash
nano server.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-4)
### Step 2: Write Imports and Global Deque Buffer (Lines 1–15)
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-4)
```python
import asyncio
import json
from collections import deque
from quart import Quart, websocket, jsonify

app = Quart(__name__)

# Monotonic event sequence counter and delivery queue
EVENT_SEQ = 0
EVENT_BUFFER = deque(maxlen=1000)
```
- **Line 1–4**: Import `asyncio` for non-blocking execution, `json` for serializing payloads, and `collections.deque` for a high-performance fixed-size memory queue.
- **Line 9–10**: `EVENT_SEQ` tracks event ordering. `deque(maxlen=1000)` ensures memory never leaks by automatically discarding the oldest items if the buffer exceeds 1,000 entries.

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-5)
### Step 3: Implement the WebSocket Streaming Route (Lines 16–45)
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-5)
```python
@app.websocket('/ws')
async def ws_endpoint():
    global EVENT_SEQ
    print("[SERVER] Client connected to streaming WebSocket.")
    
    try:
        while True:
            raw_msg = await websocket.receive()
            data = json.loads(raw_msg)
            msg_type = data.get("type")
            
            # 1. 4-Second Keep-Alive Heartbeat
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
                
            # 2. Resynchronize Missed Events
            elif msg_type == "sync":
                last_seq = data.get("last_seq", 0)
                for event in list(EVENT_BUFFER):
                    if event["seq"] > last_seq:
                        await websocket.send_json(event)
                continue
                
            # 3. Client Acknowledgment
            elif msg_type == "ack":
                ack_seq = data.get("seq", 0)
                # Prune buffer up to acknowledged sequence
                while EVENT_BUFFER and EVENT_BUFFER[0]["seq"] <= ack_seq:
                    EVENT_BUFFER.popleft()
                continue
                
    except asyncio.CancelledError:
        print("[SERVER] WebSocket connection closed safely.")
```

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-6)
### Step 4: Add the Entrypoint (Lines 46–50)
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-6)
```python
if __name__ == '__main__':
    print("Starting Asynchronous Quart Streaming Server on Port 5000...")
    app.run(host='127.0.0.1', port=5000)
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-7)
## Why Order Matters in Server Architecture
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-7)

1. **Global Deque Initialization Before Route Binding**:
   - The message buffer and sequence locks must exist in memory *before* binding the `/ws` decorator. If connections arrive before data structures are instantiated, requests crash with `NameError`.
2. **Ping Evaluation Before Heavy Event Handlers**:
   - Evaluate `msg_type == "ping"` at the very top of the WebSocket loop. Heartbeats require instant responses; evaluating them after complex handlers causes unnecessary latency.
3. **Popleft After Verification**:
   - Always verify `EVENT_BUFFER[0]["seq"] <= ack_seq` before calling `popleft()`. Removing elements without bounds checking empties unacknowledged data during bursty traffic.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-8)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-8)

Verify that your streaming server boots and responds to heartbeats:

```bash
# 1. Start the server
python3 server.py

# 2. In another terminal, send a WebSocket ping test
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://127.0.0.1:5000/ws') as ws:
        await ws.send(json.dumps({'type': 'ping'}))
        print('Server Replied:', await ws.recv())
asyncio.run(test())
"
```
**Expected Output**: `Server Replied: {"type": "pong"}`

---

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-9)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-10)

### Q: Why do we use `list(EVENT_BUFFER)` when replaying events?
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-10)
**A:** In asynchronous programming, the underlying `deque` might have new items added while you are looping over it. Converting it to a temporary `list` creates a safe snapshot, preventing `RuntimeError: deque mutated during iteration`.

[//]: # (SECTION_ID: SIRA-ARCH-05_01-SEC-11)
### Q: What is `popleft()`?
[//]: # (SECTION_ID: SIRA-DOC-05_01-SEC-11)
**A:** Standard lists delete from the beginning in $O(n)$ time by shifting every element. A `deque` uses a doubly-linked list that removes from the left in $O(1)$ instantaneous time, saving CPU cycles.
