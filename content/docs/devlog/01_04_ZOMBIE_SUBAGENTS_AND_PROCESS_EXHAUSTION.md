# Pillar 01.4: Problems Encountered: Zombie Subagents & Process Exhaustion

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_03_PATH_TRAVERSAL_AND_PRIVILEGE_ESCALATION.md`](/docs/devlog/01_03_PATH_TRAVERSAL_AND_PRIVILEGE_ESCALATION)
- **Next Problem Chapter**: [`01_05_SCREEN_READER_SPAM_AND_PHANTOM_KEYSTROKES.md`](/docs/devlog/01_05_SCREEN_READER_SPAM_AND_PHANTOM_KEYSTROKES)

---

## Overview

When Siraugga introduced autonomous subagent swarms to run multi-file audits and background tasks, the system encountered a critical resource management failure: **Zombie Subagent Accumulation**.

This chapter details how orphaned background processes paralyzed the host machine and how Siraugga engineered an automated process reaper to guarantee deterministic task termination.

---

## The Incident: Subagent Zombies & CPU Exhaustion

### What Happened
During heavy multi-agent testing (DEVLOG Chapter 39), the host system's fans began spinning at maximum speed. Terminal responsiveness dropped, file operations lagged, and attempting to spawn new agents failed with:
```text
BlockingIOError: [Errno 11] Resource temporarily unavailable (os.fork failed)
```
Upon inspecting Linux processes with `htop` and `ps aux | grep agy`, the administrator discovered dozens of orphaned `agy` and `python` worker processes running invisibly in the background, consuming 100% of available CPU cores.

### Why It Happened
When a developer cancelled a running task in the web UI, the backend executed a standard Python coroutine cancellation:

```python
# FLAWED EARLY PATTERN: Cancelling coroutine leaves OS process alive
async def cancel_task(task_id):
    async_task = running_tasks.get(task_id)
    if async_task:
        async_task.cancel()  # Cancels Python coroutine, but NOT the OS subprocess!
```

In Linux, calling `async_task.cancel()` raises an `asyncio.CancelledError` inside Python's async wrapper. However, the operating system subprocess (spawned via `subprocess.Popen` or `create_subprocess_exec`) was not attached to a process group. 

The Python coroutine exited, but the underlying OS subprocess was detached as an **orphan**. It continued running its calculations forever, holding open memory pages and system file descriptors.

---

## The Architectural Solution

To eliminate zombie accumulation, Siraugga implemented a three-tier Process Reaping Architecture:

### 1. Process Group Isolation (`preexec_fn=os.setpgrp`)
When launching agent subprocesses, the server assigns each subprocess to its own unique process group ID (PGID):
```python
process = await asyncio.create_subprocess_exec(
    *cmd,
    preexec_fn=os.setpgrp  # Creates dedicated process group
)
```

### 2. Cascading Signal Termination (`SIGTERM` -> `SIGKILL`)
When a cancellation is triggered, the supervisor sends termination signals to the entire process group, ensuring all child and grandchild workers are reaped:
```python
def reap_process_group(pgid):
    try:
        # Graceful request to stop
        os.killpg(pgid, signal.SIGTERM)
        time.sleep(0.5)
        # Forceful termination if still alive
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # Process already exited cleanly
```

### 3. Server Shutdown & Subagent Sweeper (`kill_all`)
During server shutdowns or session resets, a global reaper sweeps all registered subagent conversation IDs and executes a cascading `kill_all` sequence, leaving zero orphaned processes behind.

---

## Why Order Matters in Process Termination

1. **`SIGTERM` Before `SIGKILL`**:
   - Always send `SIGTERM` first, allowing the agent to flush file buffers, release lockfiles, and close database handles. Jumping straight to `SIGKILL` corrupts open SQLite databases and leaves half-written files on disk.
2. **Reap OS Process Before Deleting Task Registry**:
   - The operating system PID must be confirmed dead *before* removing the task record from Python's memory dictionary. If you clear the dictionary first and the process fails to terminate, you lose the PID reference required to kill it.

---

## Beginner Coder Q&A

### Q: What is an orphan process vs. a zombie process?
**A:** An **orphan** is a running child process whose parent process terminated without waiting for it; the Linux `init` process adopts it. A **zombie** is a process that has finished execution but still has an entry in the process table because its parent hasn't read its exit code.

### Q: Why doesn't `task.cancel()` kill the command running in the terminal?
**A:** `asyncio.Task` only controls Python's internal event loop. It has no native knowledge of operating system hardware processes unless you explicitly link the cancellation handler to `process.terminate()`.
