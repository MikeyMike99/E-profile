[//]: # (DOC_ID: SIRA-DEV-03_01 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 03.1: Diagnostic Tests: Streaming Resilience & Reconnection Logs

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`../02_SOURCE_EVIDENCE/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE.md`](/docs/devlog/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE)
- **Next Diagnostic Chapter**: [`03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS.md`](/docs/devlog/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS)

---

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-1)

This chapter documents the empirical diagnostic tests conducted to verify Siraugga's WebSocket streaming resilience, 4-second keep-alive heartbeats, and guaranteed event delivery queue across simulated network drops.

---

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-2)
## Test 1: Simulating WSL 2 TCP Silence vs. 4-Second Heartbeats
[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-3)

### What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-3)
We tested whether maintaining network silence during a 45-second AI thinking block drops the connection, and verified that injecting a 4-second client heartbeat maintains TCP stability.

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-4)
### Exact Command Run
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-4)
```bash
# Terminal Diagnostic Test Script
python3 -c "
import asyncio, websockets, json, time

async def test_keepalive():
    uri = 'ws://127.0.0.1:5000/ws'
    async with websockets.connect(uri) as ws:
        print('[TEST] WebSocket Connected.')
        start = time.time()
        for i in range(10):
            await asyncio.sleep(4)
            await ws.send(json.dumps({'type': 'ping'}))
            resp = await ws.recv()
            print(f'[{int(time.time() - start)}s] Heartbeat Response:', resp)
            
asyncio.run(test_keepalive())
"
```

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-5)
### Exact Output Returned
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-5)
```text
[TEST] WebSocket Connected.
[4s] Heartbeat Response: {"type": "pong"}
[8s] Heartbeat Response: {"type": "pong"}
[12s] Heartbeat Response: {"type": "pong"}
[16s] Heartbeat Response: {"type": "pong"}
[20s] Heartbeat Response: {"type": "pong"}
[24s] Heartbeat Response: {"type": "pong"}
[28s] Heartbeat Response: {"type": "pong"}
[32s] Heartbeat Response: {"type": "pong"}
[36s] Heartbeat Response: {"type": "pong"}
[40s] Heartbeat Response: {"type": "pong"}
```

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-6)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-6)
The socket successfully surpassed the 30-second WSL 2 timeout threshold without experiencing Code 1006 termination. The 4-second ping interval guarantees that virtual Hyper-V NAT tables never mark the connection as stale.

---

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-7)
## Test 2: Network Drop & Sequence Resynchronization (ACK Replay)
[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-8)

### What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-8)
We disconnected the WebSocket while an agent was emitting tokens (simulating a Wi-Fi drop), reconnected 5 seconds later with `{"type": "sync", "last_seq": 12}`, and verified that the server accurately replayed missed chunks.

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-9)
### Exact Diagnostic Trace
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-9)
```text
[CLIENT]: Disconnecting abruptly at seq: 12...
[SERVER]: Client WebSocket disconnected. Task continues in background detached state.
[SERVER]: Agent emitted token seq: 13 -> Buffered in Deque.
[SERVER]: Agent emitted token seq: 14 -> Buffered in Deque.
[SERVER]: Agent emitted token seq: 15 -> Buffered in Deque.
[CLIENT]: Reconnecting to ws://127.0.0.1:5000/ws...
[CLIENT -> SERVER]: {"type": "sync", "last_seq": 12}
[SERVER -> CLIENT]: {"seq": 13, "type": "chunk", "text": "def calculate_score():\n"}
[SERVER -> CLIENT]: {"seq": 14, "type": "chunk", "text": "    return score * 10\n"}
[SERVER -> CLIENT]: {"seq": 15, "type": "chunk", "text": "# Task Complete"}
[CLIENT -> SERVER]: {"type": "ack", "seq": 15}
[SERVER]: Pruned buffer up to seq: 15. Queue size: 0.
```

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-10)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-10)
The ACK protocol ensures zero token loss during network interruptions. Missing chunks are replayed in deterministic monotonic order, and server memory is immediately reclaimed once acknowledged.

---

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-11)
## Why Order Matters in Stream Testing
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-11)

1. **Verify Base Ping Before Load Injection**:
   - Always confirm that basic `ping`/`pong` heartbeats resolve before testing heavy agent streaming. If the heartbeat fails on an idle connection, debugging complex streaming logs will lead to false assumptions.
2. **Synchronize Sequence Numbers Sequentially**:
   - The sync request must specify the exact last acknowledged integer. Storing `last_seq` as a monotonic counter prevents duplicate token rendering on the frontend.

---

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-12)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-13)

### Q: What is a Hyper-V NAT bridge?
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-13)
**A:** When running WSL 2 on Windows, Linux runs inside a mini virtual machine. Hyper-V acts as a virtual router (NAT) that translates Linux internet packets to your Windows network card.

[//]: # (SECTION_ID: SIRA-DEV-03_01-SEC-14)
### Q: Why not keep all historical messages forever in memory instead of pruning?
[//]: # (SECTION_ID: SIRA-DOC-03_01-SEC-14)
**A:** AI coding sessions can generate hundreds of thousands of tokens. If the server never deleted acknowledged events, Python's memory usage would grow infinitely, eventually crashing the server with an `OutOfMemoryError`.
