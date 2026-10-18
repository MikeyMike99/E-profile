[//]: # (DOC_ID: SIRA-DEV-01_09 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 01.9: Problems Encountered: WSL Broken Pipes & Cross-OS I/O Traps

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_08_THE_ENTERPRISE_PRE_AUTHORIZATION_WALL.md`](/docs/devlog/01_08_THE_ENTERPRISE_PRE_AUTHORIZATION_WALL)
- **Next Problem Chapter**: [`01_10_INGESTION_SWARM_PRIVILEGE_ESCALATION_TRAPS.md`](/docs/devlog/01_10_INGESTION_SWARM_PRIVILEGE_ESCALATION_TRAPS)

---

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-1)

In hybrid Windows/Linux environments where frontend clients or desktop apps run on Windows while the core AI backend runs inside the Windows Subsystem for Linux (WSL 2), cross-operating-system file transfers are fraught with silent failures.

As documented in DEVLOG Chapter 46 and the core system guidelines, early attempts to save artifacts into Linux via stdin pipes resulted in **Silent Data Truncation** and **Broken Pipe Deadlocks**.

This chapter details the failure mechanics and how the safe two-stage host bridge permanently solved it.

---

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-2)
## The Incident: Stdin Pipe Corruption Across WSL 2
[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-3)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-3)
When an administrator edited an implementation plan or markdown document on the Windows frontend and clicked "Save", the web route attempted to write the content into Linux using standard subprocess piping:

```python
# FLAWED EARLY PATTERN: Piped stdin into WSL bash
cmd = ["wsl.exe", "bash", "-c", f"cat > '{linux_dest_path}'"]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
proc.communicate(input=markdown_bytes)
```

For small files (under 1 KB), the save succeeded. But when saving large architectural plans or devlogs (over 4 KB), one of two catastrophic bugs occurred:
1. **Broken Pipe Crash**: The Python backend crashed with `BrokenPipeError: [Errno 32] Broken pipe`.
2. **Silent File Truncation**: The file was saved inside Linux, but exactly half of the text was missing, permanently corrupting the document without raising any error code.

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-4)
### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-4)
The boundary between Windows and WSL 2 is an inter-process boundary mediated by Hyper-V sockets and the `wsl.exe` bridging daemon.

1. **Buffer Exhaustion**: On Windows, the standard OS pipe buffer is 4,096 bytes. When `proc.communicate()` writes more than 4KB, the Windows buffer fills up before the WSL Linux shell reads it.
2. **Socket Reset**: If Windows closes the pipe while WSL's `cat` utility is still flushing its internal Linux glibc buffers, the Linux process receives an unexpected EOF (End of File) and closes prematurely, triggering a `SIGPIPE` on the Windows side.

---

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-5)
## The Architectural Solution: The Two-Stage Host Bridge
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-5)

To achieve 100% data integrity without relying on fragile inter-OS pipes, Siraugga established the **Two-Stage Staging Protocol**:

```text
+-------------------------------------------------------------------------------+
|                       Stage 1: Windows Host Staging                           |
|  Write raw markdown payload to a local Windows temp file first:               |
|  C:\Users\<username>\AppData\Local\Temp\staged_artifact.md                    |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                     Stage 2: Deterministic WSL Copy                           |
|  1. Convert Windows path to Linux mount: wslpath -a <win_temp_path>           |
|  2. Execute atomic file copy: wsl.exe cp <source_mount> <linux_target_path>   |
|  3. Clean up Windows temp file immediately                                    |
+-------------------------------------------------------------------------------+
```

By passing files through the filesystem using native `cp` rather than streaming bytes through stdin pipes, data loss is reduced to exactly zero.

---

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-6)
## Why Order Matters in Cross-OS File Transfers
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-6)

1. **Flush and Close Windows File Before Copying**:
   - The temporary Windows file descriptor must be completely closed (`f.close()`) *before* calling `wsl.exe cp`. If the copy runs while Windows still holds the file open with write locks, Linux encounters file-locking sharing violations.
2. **Remove Temp File in Finally Block**:
   - The temporary host file must be deleted in a `finally` block to uphold the Clean Workspace Protocol and prevent disk clutter.

---

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-7)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-8)

### Q: What is `wslpath`?
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-8)
**A:** `wslpath` is a built-in utility in WSL that converts Windows-style paths (`%USERPROFILE%\file.txt`) into Linux mount paths (`%USERPROFILE%/file.txt`), and vice versa.

[//]: # (SECTION_ID: SIRA-DEV-01_09-SEC-9)
### Q: Why is `cp` safer than `cat > file`?
[//]: # (SECTION_ID: SIRA-DOC-01_09-SEC-9)
**A:** `cat > file` relies on live stream piping where network/socket lag can truncate data mid-flight. `cp` is a block-level file copy operation that verifies the entire source file has been copied before completing.
