[//]: # (DOC_ID: SIRA-DOC-01_14 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 01_14: Subagent Audio Routing & EOF Cache Buffer Traps

Audio cues provide essential non-visual feedback to screen reader developers when autonomous background subagents start, finish, or exchange messages. This chapter reveals how standard Python file I/O failed due to EOF cache buffering, and how swapping to native OS streaming processes created real-time audio triggers without polluting the AI's prompt context.

---

## What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-1)

When subagents were launched in parallel workspaces, the accessible web portal was designed to play distinct auditory chimes (`incoming_message.wav`, `action_done.wav`) to notify the developer of lifecycle transitions:
- **Massive Audio Latency**: Subagent completion chimes did not trigger when the subagent finished. Instead, they remained silent for 20 to 45 seconds, then suddenly fired in a rapid, overlapping burst minutes later.
- **The Stale EOF Trap**: When a Python background thread read the subagent's `transcript.jsonl` using standard loops (`while True: line = f.readline()`), Python's runtime cached the End-Of-File (EOF) state. New lines appended by the subagent were invisible until the buffer flushed.
- **LLM Context Pollution**: Early attempts to trigger sounds by asking the LLM to output magic tokens (like `[PLAY_SOUND]`) wasted valuable context tokens, slowed down reasoning, and failed whenever the model omitted the string.

---

## Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-2)

The breakdown occurred at the intersection of operating system buffer caches and standard language runtimes:
- **C Runtime File Buffering**: Python's `open()` function relies on the underlying C runtime library (`libc`), which uses 4KB or 8KB memory buffers by default. File reads do not immediately see file appends until the writing process flushes or closes the descriptor.
- **Inotify & File Polling Limitations Across WSL**: When files are written across the WSL 9P filesystem mount (`/mnt/c/...`), Linux `inotify` kernel events frequently fail to trigger, leaving standard file watcher libraries (like `watchdog`) completely blind.
- **Subagent Lifecycle Asynchrony**: Subagents write logs in small JSON bursts. If the monitoring thread is blocked on a cached file descriptor, real-time auditory notifications become impossible.

```
Standard Python IO:
Subagent Appends Line ---> OS 4KB Buffer ---> Python Reader hits EOF Cache ---> 30s Silence!

Native OS Tail Process:
Subagent Appends Line ---> Kernel Pipe ---> Native OS Tail (-F / Get-Content) ---> 0.01s Chime!
```

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-3)

Achieving zero-latency audio dispatch requires strict sequencing across process boundaries:
1. **Launch Watcher Before Subprocess**: The transcript watcher must be spawned and listening to the target log path *before* the subagent subprocess starts executing. If the watcher starts second, it risks missing initial spawn events.
2. **Unbuffer Subprocess Stdout First**: Set `PYTHONUNBUFFERED=1` in the agent's environment before launch. Without unbuffered output, internal logger events never reach the filesystem in real time.
3. **Dispatch Audio Out-of-Band**: Audio triggers must be sent over the dedicated WebSocket notification channel independently of the LLM's conversational text stream. Never make audio playback dependent on text token generation.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-4)

### Why didn't `f.flush()` solve the problem in Python?
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-5)
`f.flush()` only flushes the *writer's* internal buffer. It does not force a separate *reader* process to invalidate its internal C runtime read cache when reading past EOF.

### What native OS commands replace standard Python file reading?
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-6)
On Linux and WSL, the engine executes `tail -n 0 -F <path>`. On Windows, it invokes PowerShell with `Get-Content -Path <path> -Wait -Tail 0`. Both tools hook directly into low-level OS kernel file-append interrupts.

### Why is this better than having the AI say "I'm starting a subagent"?
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-7)
Having the AI generate text consumes hundreds of tokens and introduces several seconds of LLM generation delay. An OS-level audio chime sounds in less than 15 milliseconds, providing instant developer awareness without cost.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-01_14-SEC-8)
- To see the native transcript tailer code implementation, view [`02_SOURCE_EVIDENCE/02_10_TRANSCRIPT_TAILER_AND_NATIVE_SUBPROCESS_EVIDENCE.md`](/docs/devlog/02_10_TRANSCRIPT_TAILER_AND_NATIVE_SUBPROCESS_EVIDENCE).
- To compare latency benchmarks between Python IO and native tailing, visit [`03_DIAGNOSTIC_TESTS/03_10_NATIVE_TAIL_VS_PYTHON_BUFFER_BENCHMARK_LOGS.md`](/docs/devlog/03_10_NATIVE_TAIL_VS_PYTHON_BUFFER_BENCHMARK_LOGS).
- To build the complete audio watcher daemon from scratch, read [`05_FROM_SCRATCH_CREATION_GUIDES/05_12_NATIVE_TRANSCRIPT_TAILER_AUDIO_ROUTER_FROM_SCRATCH.md`](/docs/devlog/05_12_NATIVE_TRANSCRIPT_TAILER_AUDIO_ROUTER_FROM_SCRATCH).
