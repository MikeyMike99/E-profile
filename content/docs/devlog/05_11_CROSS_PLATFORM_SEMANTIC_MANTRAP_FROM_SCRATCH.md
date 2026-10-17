# Chapter 05_11: Cross-Platform Semantic Mantrap From Scratch

A step-by-step guide to writing the cross-platform **Semantic Mantrap** (`mantrap.py`) line by line from a completely blank text editor window.

---

## What We Are Building & Beginner Safety Rules

We are constructing `mantrap.py`—a lightweight module that provides atomic file-locking and race-condition prevention across both Linux/WSL and native Windows.

### Beginner Safety Directives
1. **Never Lock Empty Files on Windows**: `msvcrt.locking` throws an error if attempting to lock a 0-byte file. We will write 1 dummy byte (`"X"`) upon creation.
2. **Always Use `try...finally`**: An exclusive lock must *always* be released in a `finally` block so that crashes or interruptions never freeze the system.
3. **OS-Agnostic Imports**: Never import `fcntl` directly on Windows or `msvcrt` directly on Linux without wrapping them in `try...except ImportError`.

---

## Step-by-Step Line Breakdown

### Block 1: Imports & OS Detection (Lines 1–15)

Open a blank file named `mantrap.py` and write:

```python
import os
import logging
import time
from contextlib import contextmanager

try:
    import fcntl
    OS_TYPE = "linux"
except ImportError:
    try:
        import msvcrt
        OS_TYPE = "windows"
    except ImportError:
        OS_TYPE = "unknown"

MANTRAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "mantrap_locks")
```

- **Lines 1–4**: Standard imports. `@contextmanager` allows us to use the `with` statement.
- **Lines 6–14**: Tries to import `fcntl` (Linux). If that fails, it tries `msvcrt` (Windows). If both fail, it sets `OS_TYPE = "unknown"`.
- **Line 16**: Defines the directory where lock files will live.

---

### Block 2: The Context Manager & Lock Acquisition (Lines 17–45)

Add the `SemanticMantrap` class and context manager:

```python
class SemanticMantrap:
    @staticmethod
    @contextmanager
    def execution_chamber(target_db_path: str, agent_id: str = "System"):
        os.makedirs(MANTRAP_DIR, exist_ok=True)
        
        safe_name = target_db_path.replace("/", "_").replace("\\", "_").replace(":", "_") + ".lock"
        lock_path = os.path.join(MANTRAP_DIR, safe_name)
        
        # Windows requires at least 1 byte to lock a region
        if not os.path.exists(lock_path):
            with open(lock_path, "w") as init_f:
                if OS_TYPE == "windows":
                    init_f.write("X")
                    
        lock_fd = open(lock_path, "r+")
        
        try:
            logging.info(f"[MANTRAP] Agent '{agent_id}' waiting at Outer Door for {target_db_path}")
            if OS_TYPE == "linux":
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            elif OS_TYPE == "windows":
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
            else:
                time.sleep(0.1)
                
            logging.info(f"[MANTRAP] Agent '{agent_id}' has entered the Execution Chamber")
            yield True
```

- **Lines 21–22**: Replaces slashes and colons with underscores to create a safe filename.
- **Lines 25–28**: If the lock file is new and we are on Windows, writes `"X"` so the file has 1 byte.
- **Line 30**: Opens the lock file in read/write mode (`"r+"`).
- **Lines 34–39**: Acquires an exclusive lock (`LOCK_EX` on Linux, `LK_LOCK` on Windows).
- **Line 43**: `yield True` pauses this function and allows the caller's code inside the `with` block to run!

---

### Block 3: Guaranteed Lock Release (Lines 46–60)

Complete the function with the `finally` cleanup block:

```python
        finally:
            logging.info(f"[MANTRAP] Agent '{agent_id}' exiting Execution Chamber. Releasing lock")
            if OS_TYPE == "linux":
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            elif OS_TYPE == "windows":
                try:
                    lock_fd.seek(0)
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            lock_fd.close()
```

- **Line 47**: The `finally` block runs NO MATTER WHAT—even if the caller's code crashes or throws an exception.
- **Lines 49–56**: Unlocks the descriptor (`LOCK_UN` or `LK_UNLCK`).
- **Line 57**: Closes the file descriptor cleanly.

---

## Complete Finished File Listing

```python
import os
import logging
import time
from contextlib import contextmanager

try:
    import fcntl
    OS_TYPE = "linux"
except ImportError:
    try:
        import msvcrt
        OS_TYPE = "windows"
    except ImportError:
        OS_TYPE = "unknown"

MANTRAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "mantrap_locks")

class SemanticMantrap:
    @staticmethod
    @contextmanager
    def execution_chamber(target_db_path: str, agent_id: str = "System"):
        os.makedirs(MANTRAP_DIR, exist_ok=True)
        safe_name = target_db_path.replace("/", "_").replace("\\", "_").replace(":", "_") + ".lock"
        lock_path = os.path.join(MANTRAP_DIR, safe_name)
        
        if not os.path.exists(lock_path):
            with open(lock_path, "w") as init_f:
                if OS_TYPE == "windows":
                    init_f.write("X")
                    
        lock_fd = open(lock_path, "r+")
        try:
            logging.info(f"[MANTRAP] Agent '{agent_id}' waiting at Outer Door for {target_db_path}")
            if OS_TYPE == "linux":
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            elif OS_TYPE == "windows":
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
            else:
                time.sleep(0.1)
                
            logging.info(f"[MANTRAP] Agent '{agent_id}' has entered the Execution Chamber")
            yield True
        finally:
            logging.info(f"[MANTRAP] Agent '{agent_id}' exiting Execution Chamber. Releasing lock")
            if OS_TYPE == "linux":
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            elif OS_TYPE == "windows":
                try:
                    lock_fd.seek(0)
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            lock_fd.close()
```

---

## 10-Second Verification Checklist

```bash
# 1. Test basic acquisition and release
python3 -c "
from mantrap import SemanticMantrap
with SemanticMantrap.execution_chamber('test.db', 'QuickTest'):
    print('Inside chamber successfully!')
"
```
If it prints `Inside chamber successfully!` without errors, your cross-platform mantrap is fully operational.

---

## Beginner Coder Q&A

### What does `r+` mean in `open()`?
`r+` opens the file for both reading and writing without erasing its contents. Standard `w` erases the file immediately, which would delete our Windows 1-byte marker!

### What happens if I forget to close `lock_fd`?
Python will eventually close it when the garbage collector runs, but leaving open file descriptors can cause Windows to report "File in use by another process". Explicitly closing it in `finally` is a critical best practice.

---

## Next Steps & Related Chapters
- To understand why uncoordinated concurrency broke the server, read [`01_PROBLEMS_ENCOUNTERED/01_13_SEMANTIC_MANTRAP_AND_CONCURRENT_THREAD_LOCK_TRAPS.md`](/docs/devlog/01_13_SEMANTIC_MANTRAP_AND_CONCURRENT_THREAD_LOCK_TRAPS).
- To inspect diagnostic benchmark logs, visit [`03_DIAGNOSTIC_TESTS/03_09_SEMANTIC_MANTRAP_AND_CONCURRENCY_BENCHMARK_LOGS.md`](/docs/devlog/03_09_SEMANTIC_MANTRAP_AND_CONCURRENCY_BENCHMARK_LOGS).
- To explore the architectural deep dive, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_09_CROSS_PLATFORM_MANTRAP_AND_CONCURRENCY_ARCHITECTURE.md`](/docs/devlog/04_09_CROSS_PLATFORM_MANTRAP_AND_CONCURRENCY_ARCHITECTURE).
