[//]: # (DOC_ID: SIRA-DEV-02_09 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 02_09: Semantic Mantrap & File Locking Evidence

Primary source evidence from the Siraugga security core demonstrating how cross-platform thread synchronization, atomic file locking, and deadlock prevention are implemented across Linux and Windows.

---

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-1)
## Source Citation 1: OS-Agnostic Lock Detection (`security/mantrap.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-1)

This code excerpt shows how the system dynamically discovers the host kernel type at module import time without crashing on missing libraries:

```python
# Location: <project_root>/security/mantrap.py
# Lines: 6-15

try:
    import fcntl
    OS_TYPE = "linux"
except ImportError:
    try:
        import msvcrt
        OS_TYPE = "windows"
    except ImportError:
        OS_TYPE = "unknown"
```

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-2)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-2)
- **Zero Host Crashes**: The code wraps OS-specific imports in nested `try...except ImportError` blocks. Importing `fcntl` on Windows or `msvcrt` on Linux fails gracefully without crashing the Python interpreter.
- **Dynamic Platform Identification**: Sets `OS_TYPE` globally so runtime functions select the appropriate locking API without repeated OS checks.

---

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-3)
## Source Citation 2: The Execution Chamber Context Manager (`security/mantrap.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-3)

This excerpt displays the context manager that locks the resource before yielding control and guarantees unlock upon exit:

```python
# Location: <project_root>/security/mantrap.py
# Lines: 27-75

@staticmethod
@contextmanager
def execution_chamber(target_db_path: str, agent_id: str = "System"):
    os.makedirs(MANTRAP_DIR, exist_ok=True)
    
    safe_name = target_db_path.replace("/", "_").replace("\\", "_").replace(":", "_") + ".lock"
    lock_path = os.path.join(MANTRAP_DIR, safe_name)
    
    # Windows msvcrt requires the file to have at least 1 byte to lock a region
    if not os.path.exists(lock_path):
        with open(lock_path, 'w') as init_f:
            if OS_TYPE == "windows":
                init_f.write("X")
            
    lock_fd = open(lock_path, 'r+')
    
    try:
        logging.info(f"[MANTRAP] Agent '{agent_id}' waiting at Outer Door for {target_db_path} (OS: {OS_TYPE})")
        
        # The Outer Door: Stagger the logic flow and acquire an exclusive lock
        if OS_TYPE == "linux":
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        elif OS_TYPE == "windows":
            lock_fd.seek(0)
            # LK_LOCK blocks the thread until the lock is acquired, simulating fcntl.LOCK_EX
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
        else:
            time.sleep(0.1)
        
        logging.info(f"[MANTRAP] Agent '{agent_id}' has entered the Execution Chamber for {target_db_path}")
        
        # Yield control back to the core logic
        yield True
        
    finally:
        logging.info(f"[MANTRAP] Agent '{agent_id}' exiting Execution Chamber. Releasing lock on {target_db_path}")
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

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-4)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-4)
- **Windows Byte-Range Requirement**: `msvcrt.locking` cannot lock a zero-byte file on Windows. Lines 35–38 ensure the lock file contains at least 1 byte (`"X"`), preventing silent Win32 locking errors.
- **Guaranteed Lock Release**: Placing `LOCK_UN` and `LK_UNLCK` inside a `finally` block guarantees that even if a subagent throws an uncaught exception, the lock descriptor is unlocked and closed cleanly.

---

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-5)

In multi-process synchronization, order prevents race conditions and data corruption:
1. **Sanitize Lock Path Before File Creation**: Transforming slashes and colons into underscores (`safe_name`) ensures valid filename formatting across both Linux and NTFS filesystems before invoking `open()`.
2. **Seek to Byte Zero Before Windows Locking**: `msvcrt.locking` locks bytes relative to the current file pointer. Calling `lock_fd.seek(0)` guarantees you lock the first byte, matching the unlock call.
3. **Yield Inside Try, Release Inside Finally**: The `yield True` statement passes execution to the caller. Enclosing it strictly within `try...finally` ensures execution never bypasses lock release.

---

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-7)

### What does `@contextmanager` do?
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-7)
It is a Python decorator from `contextlib` that lets you write a generator using `yield` that works with the `with` statement (`with SemanticMantrap.execution_chamber("db.json"): ...`).

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-8)
### Why do we lock a `.lock` file instead of locking the database file itself?
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-8)
Locking a dedicated `.lock` file prevents interfering with other software (like text editors or backup tools) that might want to inspect the database file. If the database file is locked directly, third-party tools crash.

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-9)
### What is the difference between `LOCK_EX` and `LOCK_SH`?
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-9)
`LOCK_EX` (Exclusive Lock) permits only one single process to access the resource; all others must wait. `LOCK_SH` (Shared Lock) allows multiple readers to read simultaneously, but blocks any writers.

---

[//]: # (SECTION_ID: SIRA-DEV-02_09-SEC-10)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_09-SEC-10)
- To understand the problems that necessitated this mantrap, read [`01_PROBLEMS_ENCOUNTERED/01_13_SEMANTIC_MANTRAP_AND_CONCURRENT_THREAD_LOCK_TRAPS.md`](/docs/devlog/01_13_SEMANTIC_MANTRAP_AND_CONCURRENT_THREAD_LOCK_TRAPS).
- To view diagnostic stress test logs under high concurrency, visit [`03_DIAGNOSTIC_TESTS/03_09_SEMANTIC_MANTRAP_AND_CONCURRENCY_BENCHMARK_LOGS.md`](/docs/devlog/03_09_SEMANTIC_MANTRAP_AND_CONCURRENCY_BENCHMARK_LOGS).
- To write your own cross-platform mantrap from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_11_CROSS_PLATFORM_SEMANTIC_MANTRAP_FROM_SCRATCH.md`](/docs/devlog/05_11_CROSS_PLATFORM_SEMANTIC_MANTRAP_FROM_SCRATCH).
