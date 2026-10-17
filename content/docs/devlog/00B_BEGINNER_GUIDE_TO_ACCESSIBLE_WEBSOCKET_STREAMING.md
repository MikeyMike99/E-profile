# Pillar 00B: Beginner Guide to Accessible WebSocket Streaming

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Primer**: [`00A_BEGINNER_GUIDE_TO_SIRAUGGA_AND_ZERO_TRUST.md`](/docs/devlog/00A_BEGINNER_GUIDE_TO_SIRAUGGA_AND_ZERO_TRUST)
- **Next: Problems Encountered**: [`../01_PROBLEMS_ENCOUNTERED/01_01_TERMINAL_TEARING_AND_HEADLESS_BYPASS_TRAPS.md`](/docs/devlog/01_01_TERMINAL_TEARING_AND_HEADLESS_BYPASS_TRAPS)

---

## The Challenge: Streaming AI to Screen Readers

When artificial intelligence models write code, they generate continuous streams of tokens, tool calls, and execution logs. In traditional command-line interfaces, this creates an unmanageable experience for developers who use screen readers (such as NVDA or JAWS).

### Why Terminals Fail for Blind Developers
1. **Console Tearing**: When an AI streams output to the terminal while a developer is typing, the output collides with the cursor, garbling speech output.
2. **Key Interception**: Interactive CLI prompts (like "Do you trust this folder? [Y/n]") require raw arrow keys. Screen readers intercept arrow keys for virtual cursor navigation, causing the CLI to freeze indefinitely.
3. **Speech Flooding**: Dumping thousands of lines of raw compiler logs directly into terminal stdout causes screen readers to read continuously for minutes, drowning out vital feedback.

---

## The Solution: Decoupled WebSocket Streaming

To solve these barriers, Siraugga isolates the AI engine in a detached background subprocess and streams structured events over WebSockets to an accessible web browser interface.

```text
+---------------------+                      +---------------------+
|   Siraugga Agent    |                      |   Accessible Web    |
| (Subprocess Engine) |                      |     Portal (UI)     |
+----------+----------+                      +----------+----------+
           |                                            |
           | 1. stdout: stream-json                     |
           v                                            |
+----------+----------+                                 |
| Quart WebSocket Svr |                                 |
| - Monotonic seq++   |                                 |
| - Buffer in Deque   |                                 |
+----------+----------+                                 |
           |                                            |
           | 2. Push event {seq: 42, type: "chunk"}    |
           +------------------------------------------->+
           |                                            | 3. Render HTML
           |                                            |    Speak ARIA
           | 4. Client ACK {type: "ack", seq: 42}       |
           +<-------------------------------------------+
           |                                            |
           | 5. Prune buffer up to seq: 42              |
```

---

## Two Critical Streaming Pillars

### 1. The 4-Second Keep-Alive Heartbeat
Windows WSL 2 networking enforces aggressive TCP timeouts, severing idle connections after 30 seconds of silence. If an AI agent takes 45 seconds to analyze a codebase, the socket dies silently.

Siraugga solves this with a 4-second client heartbeat:
- The browser transmits `{"type": "ping"}` every 4,000 milliseconds.
- The server responds immediately with `{"type": "pong"}`.
- TCP connections remain actively registered in the Windows network stack.

### 2. The Guaranteed Delivery Queue (ACK Protocol)
When developers switch browser tabs or temporarily lose network connectivity, events must not be lost.

1. **Monotonic Sequence (`seq`)**: Every event emitted by the server receives an incrementing integer (`seq: 1`, `seq: 2`, ...).
2. **Server Buffer**: The server retains recent events in a memory queue (`collections.deque`).
3. **Client Acknowledgement**: The browser acknowledges processed events with `{"type": "ack", "seq": N}`, allowing the server to safely discard them.
4. **Reconnection Replay**: If the browser reconnects, it sends `{"type": "sync", "last_seq": 40}`. The server instantly replays missed events starting at `seq: 41`.

---

## Why Order Matters in WebSocket Streaming

1. **Heartbeat Startup Before Agent Execution**:
   - The keep-alive ping loop must start as soon as the WebSocket opens, *before* triggering long agent tasks. Otherwise, heavy startup workloads can stall the socket before the first ping fires.
2. **Assign Sequence Number Before Enqueueing**:
   - The sequence ID must be atomically assigned *before* placing the message into the replay queue. Reversing or staggering this order creates race conditions where out-of-order messages corrupt the client timeline.
3. **Acknowledge Before Pruning**:
   - The server must never delete an event from the buffer until the client explicitly returns an `ack` containing that sequence number. Pruning on send causes message loss during network spikes.

---

## Beginner Coder Q&A

### Q: What is a WebSocket and why not just use regular HTTP?
**A:** Standard HTTP requires the browser to ask for data every time ("polling"). A WebSocket is an open, two-way pipe that stays connected, allowing the server to push new AI tokens to the screen the exact millisecond they are generated.

### Q: Why do screen readers need HTML instead of a terminal?
**A:** HTML has semantic tags (`<button>`, `<main>`, `<textarea>`, ARIA live regions) that tell screen readers what an element does. Terminals only have raw pixels and text characters, making it impossible for screen readers to differentiate between a button, an alert, and a code block.

### Q: What happens if my browser disconnects for 10 seconds?
**A:** Thanks to the ACK protocol, the server holds your unacknowledged messages in memory. When your browser reconnects, it sends its last received sequence number, and the server replays everything you missed seamlessly.
