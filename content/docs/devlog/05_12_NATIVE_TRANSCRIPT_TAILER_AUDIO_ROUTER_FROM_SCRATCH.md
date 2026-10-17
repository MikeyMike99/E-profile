# Chapter 05_12: Native Transcript Tailer & Audio Router From Scratch

A step-by-step guide to writing the cross-platform **Native Transcript Tailer & Audio Event Router** (`transcript_tailer.py`) line by line from a completely blank text editor window.

---

## What We Are Building & Beginner Safety Rules

We are creating an asynchronous daemon that monitors subagent log files and dispatches audio events to web clients in real time using native operating system processes instead of slow, cached Python file loops.

### Beginner Safety Directives
1. **Never Read Without Offset 0**: Running `tail` without `-n 0` or `-Tail 0` replays all old events from earlier sessions, causing a loud burst of old sounds when starting up.
2. **Always Terminate Subprocesses**: If you spawn a background `tail` process, you must kill it when your monitoring loop terminates; otherwise, it will stay running in the background forever.
3. **Use Non-Blocking Asynchronous Reads**: Standard `f.readline()` blocks the whole thread. We must use `await proc.stdout.readline()`.

---

## Step-by-Step Line Breakdown

### Block 1: Imports & Setup (Lines 1–15)

Open a blank file named `transcript_tailer.py` and write:

```python
import asyncio
import os
import platform
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
```

- **Lines 1–4**: Core asynchronous and system modules. `platform` lets us detect Windows vs Linux.
- **Line 6**: Sets up a simple logging format.

---

### Block 2: Subprocess Spawning (Lines 16–42)

Add the `tail_subagent_transcript` coroutine:

```python
async def tail_subagent_transcript(transcript_path: str, broadcast_fn):
    # Wait up to 3 seconds for file creation
    for _ in range(30):
        if os.path.exists(transcript_path):
            break
        await asyncio.sleep(0.1)
        
    if not os.path.exists(transcript_path):
        logging.warning(f"Transcript not found: {transcript_path}")
        return

    # Choose OS native streaming command
    if platform.system() == "Windows":
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"Get-Content -Path '{transcript_path}' -Wait -Tail 0"
        ]
    else:
        cmd = ["tail", "-n", "0", "-F", transcript_path]

    logging.info(f"Attaching native watcher to {transcript_path}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
```

- **Lines 18–24**: Checks if the file exists before starting `tail`. If the subagent hasn't created it yet, it waits up to 3 seconds.
- **Lines 27–34**: Selects PowerShell on Windows or `tail` on Linux.
- **Lines 37–42**: Launches the command in the background and hooks its output to an asynchronous pipe.

---

### Block 3: Stream Reading & Cleanup (Lines 43–65)

Add the event detection loop and process termination:

```python
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
                
            text = line.decode("utf-8", errors="replace").strip()
            
            # Detect subagent completion keywords
            if any(k in text for k in ("has gone idle", "killed", "terminated")):
                logging.info("Subagent lifecycle transition detected! Emitting chime.")
                await broadcast_fn({"type": "audio", "sound": "completed"})
                
    except asyncio.CancelledError:
        pass
    finally:
        logging.info("Cleaning up native tail subprocess...")
        try:
            proc.terminate()
            await proc.wait()
        except Exception:
            pass
```

- **Line 45**: Reads lines from the operating system stream asynchronously.
- **Line 49**: Decodes raw bytes to text safely.
- **Lines 52–54**: If the line mentions "has gone idle", "killed", or "terminated", it dispatches the audio trigger.
- **Lines 58–65**: In the `finally` block, terminates the background process cleanly.

---

## Complete Finished File Listing

```python
import asyncio
import os
import platform
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

async def tail_subagent_transcript(transcript_path: str, broadcast_fn):
    for _ in range(30):
        if os.path.exists(transcript_path):
            break
        await asyncio.sleep(0.1)
        
    if not os.path.exists(transcript_path):
        logging.warning(f"Transcript not found: {transcript_path}")
        return

    if platform.system() == "Windows":
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"Get-Content -Path '{transcript_path}' -Wait -Tail 0"
        ]
    else:
        cmd = ["tail", "-n", "0", "-F", transcript_path]

    logging.info(f"Attaching native watcher to {transcript_path}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if any(k in text for k in ("has gone idle", "killed", "terminated")):
                logging.info("Subagent lifecycle transition detected! Emitting chime.")
                await broadcast_fn({"type": "audio", "sound": "completed"})
    except asyncio.CancelledError:
        pass
    finally:
        logging.info("Cleaning up native tail subprocess...")
        try:
            proc.terminate()
            await proc.wait()
        except Exception:
            pass
```

---

## 10-Second Verification Checklist

```bash
# 1. Run quick test with simulated logger
python3 -c "
import asyncio, os
from transcript_tailer import tail_subagent_transcript

async def test():
    test_file = 'quick_test.jsonl'
    with open(test_file, 'w') as f:
        f.write('START\n')
        
    async def mock_broadcast(msg):
        print(f'MOCK_EVENT_RECEIVED: {msg}')
        
    task = asyncio.create_task(tail_subagent_transcript(test_file, mock_broadcast))
    await asyncio.sleep(0.1)
    
    with open(test_file, 'a') as f:
        f.write('Agent has gone idle\n')
        
    await asyncio.sleep(0.2)
    task.cancel()
    await task
    os.remove(test_file)

asyncio.run(test())
"
```
If it prints `MOCK_EVENT_RECEIVED: {'type': 'audio', 'sound': 'completed'}`, your native watcher is working perfectly!

---

## Beginner Coder Q&A

### Why use `errors="replace"` instead of letting it error?
In real-world applications, logs are written in chunks. If the watcher reads half of a multi-byte emoji character, standard UTF-8 decoding throws a `UnicodeDecodeError` and crashes your app. `errors="replace"` safely substitutes a question mark instead.

### What is `await proc.wait()`?
`proc.terminate()` sends a signal asking the process to stop. `await proc.wait()` tells Python to wait until the operating system confirms the process has completely closed and cleared its memory.

---

## Next Steps & Related Chapters
- To understand why standard Python file reading failed, read [`01_PROBLEMS_ENCOUNTERED/01_14_SUBAGENT_AUDIO_ROUTING_AND_EOF_CACHE_BUFFER_TRAPS.md`](/docs/devlog/01_14_SUBAGENT_AUDIO_ROUTING_AND_EOF_CACHE_BUFFER_TRAPS).
- To inspect the primary source code implementation, view [`02_SOURCE_EVIDENCE/02_10_TRANSCRIPT_TAILER_AND_NATIVE_SUBPROCESS_EVIDENCE.md`](/docs/devlog/02_10_TRANSCRIPT_TAILER_AND_NATIVE_SUBPROCESS_EVIDENCE).
- To explore the architectural deep dive, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_10_ZERO_TRUST_SUBAGENT_AUDIO_EVENT_ARCHITECTURE.md`](/docs/devlog/04_10_ZERO_TRUST_SUBAGENT_AUDIO_EVENT_ARCHITECTURE).
