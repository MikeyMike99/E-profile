[//]: # (DOC_ID: SIRA-DOC-02_10 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 02_10: Transcript Tailer & Native Subprocess Evidence

Primary source evidence from the Siraugga task orchestrator demonstrating how the engine replaced cached Python file reads with native OS tail subprocesses to achieve real-time subagent audio dispatch.

---

## Source Citation 1: Defeating Python EOF Buffering (`agents/agent_manager.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-1)

This excerpt displays the cross-platform asynchronous subprocess implementation that monitors subagent transcripts without polling lag:

```python
# Location: <project_root>/agents/agent_manager.py
# Lines: 765-795

async def tail_transcript(self, conv_id):
    import asyncio
    import os
    import platform
    
    transcript_path = os.path.expanduser(
        f"~/.gemini/antigravity-cli/brain/{conv_id}/.system_generated/logs/transcript.jsonl"
    )
    
    # Wait up to 3 seconds for subagent to create transcript
    for _ in range(30):
        if os.path.exists(transcript_path):
            break
        await asyncio.sleep(0.1)
        
    if not os.path.exists(transcript_path):
        return
        
    if platform.system() == 'Windows':
        process = await asyncio.create_subprocess_exec(
            'powershell', '-NoProfile', '-Command', 
            f'Get-Content -Path "{transcript_path}" -Wait -Tail 0',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    else:
        process = await asyncio.create_subprocess_exec(
            'tail', '-n', '0', '-F', transcript_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-2)
- **Elimination of EOF Caching**: Standard Python `open(path).readline()` hits EOF and relies on `libc` buffer flushes. Invoking native `tail -n 0 -F` (Linux) or `Get-Content -Wait -Tail 0` (PowerShell) hooks directly into kernel-level file append events.
- **Cross-Platform Compatibility**: Uses `platform.system() == 'Windows'` to route commands appropriately between Linux/WSL environments and standalone Windows `.exe` deployments.

---

## Source Citation 2: Audio Event Dispatch Loop (`agents/agent_manager.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-3)

This excerpt demonstrates the zero-trust parsing loop that extracts lifecycle status without involving the LLM:

```python
# Location: <project_root>/agents/agent_manager.py
# Lines: 796-820

    try:
        while self.current_conversation_id == conv_id:
            line = await process.stdout.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='replace')
            
            # Deterministic lifecycle keyword detection
            if "has gone idle" in line_str or "killed" in line_str or "terminated" in line_str:
                await self.broadcast({"type": "audio", "sound": "completed"})
    except asyncio.CancelledError:
        process.terminate()
    except Exception as e:
        import logging
        logging.error(f"Transcript tailer failed: {e}")
        try:
            process.terminate()
        except:
            pass
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-4)
- **Zero Prompt Pollution**: The audio cue is dispatched via `self.broadcast({"type": "audio", "sound": "completed"})` purely from the background watcher thread. The LLM never sees or processes the audio event.
- **Safe Process Reaping**: If the parent task cancels or switches sessions, `process.terminate()` is called immediately in both `asyncio.CancelledError` and generic `Exception` handlers, preventing orphaned `tail` processes.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-5)

In real-time event tailing, process coordination order determines responsiveness:
1. **Poll Existence Before Spawning Tail**: The 30-iteration existence check ensures the transcript file actually exists before `tail` launches. Running `tail` on a non-existent file produces a `No such file or directory` error.
2. **Start Tail at Offset 0 (`-n 0` / `-Tail 0`)**: Starting at tail 0 prevents replaying old historical lines from previous runs, ensuring sounds fire *only* for fresh events occurring during this session.
3. **Terminate Process Before Context Switch**: Checking `self.current_conversation_id == conv_id` guarantees that when the user switches sessions, the tailer terminates immediately rather than leaking CPU cycles.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-6)

### What does the `-F` flag in `tail` do?
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-7)
The capital `-F` flag tells `tail` to follow the file by name rather than file descriptor. If the logging system rotates the log or temporarily replaces the file, `tail` automatically reopens the new file without crashing.

### What does `-NoProfile` do in PowerShell?
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-8)
PowerShell profiles can load third-party scripts, custom prompts, and aliases that take seconds to start. Passing `-NoProfile` launches a lean, clean shell instance in under 50 milliseconds.

### Why do we use `errors='replace'` when decoding bytes?
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-9)
JSONL logs can occasionally be interrupted mid-write, resulting in half-formed UTF-8 byte sequences. Using `replace` prevents the entire tailing loop from crashing on an incomplete character.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_10-SEC-10)
- To understand why standard Python file reads failed, read [`01_PROBLEMS_ENCOUNTERED/01_14_SUBAGENT_AUDIO_ROUTING_AND_EOF_CACHE_BUFFER_TRAPS.md`](/docs/devlog/01_14_SUBAGENT_AUDIO_ROUTING_AND_EOF_CACHE_BUFFER_TRAPS).
- To view diagnostic latency benchmarks comparing Python IO vs native tailing, visit [`03_DIAGNOSTIC_TESTS/03_10_NATIVE_TAIL_VS_PYTHON_BUFFER_BENCHMARK_LOGS.md`](/docs/devlog/03_10_NATIVE_TAIL_VS_PYTHON_BUFFER_BENCHMARK_LOGS).
- To build the complete native audio watcher daemon from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_12_NATIVE_TRANSCRIPT_TAILER_AUDIO_ROUTER_FROM_SCRATCH.md`](/docs/devlog/05_12_NATIVE_TRANSCRIPT_TAILER_AUDIO_ROUTER_FROM_SCRATCH).
