[//]: # (DOC_ID: JOSH-DEV-04_10 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 04_10: Zero-Trust Subagent Audio Event Architecture

An architectural guide to Siraugga's **Dual-Channel Event Pipeline**—separating conversational AI token streams from real-time auditory notifications using out-of-band OS kernel tail processes.

---

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-1)
## The Dual-Channel Philosophy
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-1)

In accessible software for screen reader developers, audio cues provide vital situational awareness. However, asking an AI model to decide when to make noises introduces latency, wastes tokens, and creates security risks.

Siraugga enforces a **Zero-Trust Audio Architecture**:
- **Channel 1 (Conversational Stream)**: The LLM outputs purely technical text, code edits, and explanations. It is completely blind to audio events.
- **Channel 2 (Out-of-Band Audio Stream)**: Native OS kernel watchers stream file append events from subagent transcripts directly into the browser's Web Audio API.

```
                    ┌────────────────────────┐
                    │  Developer User Query  │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Orchestrator Subprocess│
                    └─────┬────────────┬─────┘
                          │            │
             (Channel 1)  │            │ (Channel 2)
        Text/Token Stream │            │ Native OS Tail (-F / Get-Content)
                          ▼            ▼
             ┌──────────────┐     ┌───────────────────────┐
             │ AI Reasoning │     │  Kernel File Watcher  │
             │   & Output   │     │ (Zero-Trust Listener) │
             └──────────────┘     └───────────┬───────────┘
                                              │ Detects "gone idle" / "killed"
                                              ▼
                                  ┌───────────────────────┐
                                  │ WebSocket Audio Chunk │
                                  │ {"sound": "completed"}│
                                  └───────────┬───────────┘
                                              │
                                              ▼
                                  ┌───────────────────────┐
                                  │ Browser Web Audio API │
                                  │ Plays instant chime!  │
                                  └───────────────────────┘
```

---

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-2)
## Architectural Components
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-2)

1. **The Native OS Tailer**:
   - Rather than polling Python `open()`, the agent manager launches an OS-native `tail -n 0 -F` (Linux) or PowerShell `Get-Content -Wait -Tail 0` (Windows) subprocess.
   - Operates with sub-15ms event delivery latency.
2. **Deterministic Lifecycle Parser**:
   - Evaluates incoming transcript lines using rigid string matching (`"has gone idle"`, `"killed"`, `"terminated"`).
   - Zero LLM inference or dynamic prompt interpretation.
3. **The Web Audio Synthesizer**:
   - The browser client receives a lightweight JSON payload: `{"type": "audio", "sound": "completed"}`.
   - Pre-loaded HTML5 audio buffers play the sound instantly without interrupting the screen reader's virtual cursor.

---

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-3)

In decoupled event pipelines, initialization sequence prevents missed cues:
1. **Pre-Load Audio Buffers in Browser**: Audio files (`completed.wav`, `message.wav`) must be fetched and decoded into browser RAM during page load so playback is instantaneous.
2. **Launch Subprocess Tailer Before Work Begins**: The OS tail process must bind to the transcript file descriptor before the subagent starts working to catch early lifecycle events.
3. **Kill Tailer on Subagent Termination**: Reaping the tail process immediately upon task completion prevents background descriptor leaks.

---

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-4)
## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-4)

To add zero-trust audio notifications to your own multi-process agent pipeline in 2 minutes:

```python
import asyncio, platform

async def watch_subagent_events(transcript_path: str, broadcast_fn):
    # Step 1: Select OS-native tail command
    if platform.system() == "Windows":
        cmd = ["powershell", "-NoProfile", "-Command", f"Get-Content -Path '{transcript_path}' -Wait -Tail 0"]
    else:
        cmd = ["tail", "-n", "0", "-F", transcript_path]
        
    # Step 2: Spawn non-blocking OS watcher
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
    
    # Step 3: Stream and broadcast audio triggers
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            if "has gone idle" in text or "completed" in text:
                await broadcast_fn({"type": "audio", "sound": "completed"})
    finally:
        proc.terminate()
```

---

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-6)

### Why not let the AI send `{"sound": "completed"}`?
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-6)
If the AI encounters a Python error, runs out of tokens, or gets stuck in a loop, it never sends the sound! By listening to the operating system transcript directly, the audio alert plays even if the AI crashes.

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-7)
### Does this interfere with speech synthesizers like NVDA?
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-7)
No. Short non-vocal audio chimes (chimes and clicks) play through the default audio output device without occupying the screen reader's virtual buffer.

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-8)
### What happens if the transcript file doesn't exist yet?
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-8)
The watcher runs a small 3-second retry loop (checking every 100ms) until the subagent creates the file, ensuring zero race-condition crashes.

---

[//]: # (SECTION_ID: JOSH-DEV-04_10-SEC-9)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_10-SEC-9)
- To understand why standard Python file reading failed, read [`01_PROBLEMS_ENCOUNTERED/01_14_SUBAGENT_AUDIO_ROUTING_AND_EOF_CACHE_BUFFER_TRAPS.md`](/docs/devlog/01_14_SUBAGENT_AUDIO_ROUTING_AND_EOF_CACHE_BUFFER_TRAPS).
- To inspect the primary source code of the tailer, view [`02_SOURCE_EVIDENCE/02_10_TRANSCRIPT_TAILER_AND_NATIVE_SUBPROCESS_EVIDENCE.md`](/docs/devlog/02_10_TRANSCRIPT_TAILER_AND_NATIVE_SUBPROCESS_EVIDENCE).
- To build the complete audio watcher daemon from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_12_NATIVE_TRANSCRIPT_TAILER_AUDIO_ROUTER_FROM_SCRATCH.md`](/docs/devlog/05_12_NATIVE_TRANSCRIPT_TAILER_AUDIO_ROUTER_FROM_SCRATCH).
