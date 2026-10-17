[//]: # (DOC_ID: SIRA-DOC-01_03 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 01.3: Problems Encountered: Path Traversal & Privilege Escalation

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES.md`](/docs/devlog/01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES)
- **Next: Source Evidence**: [`../02_SOURCE_EVIDENCE/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE.md`](/docs/devlog/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-1)

When Siraugga expanded from a solo tool into a multi-tenant platform for game developers, modders, and autonomous AI agents, security became paramount. 

As chronicled in the developmental chatlogs (Chapters 12, 13, and 23), granting an autonomous AI uninhibited system access opened severe vulnerabilities: **Directory Traversal Escapes** and **Agentic Privilege Escalation**.

This chapter breaks down the attack vectors encountered and how Siraugga's zero-trust sandboxing defeated them.

---

## Issue 1: Directory Traversal Attacks (`../../`)
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-2)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-3)
During early API testing, a client requested to view an asset using a relative path payload:
```text
POST /api/files/read
{
    "path": "../../core/server.py"
}
```
In early unhardened iterations, the backend fulfilled the request, streaming core engine source code directly to an unprivileged client interface.

### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-4)
The server was concatenating user input directly to the workspace root without canonicalizing the resulting path:

```python
# VULNERABLE EARLY CODE:
target = os.path.join(workspace_dir, user_supplied_path)
with open(target, 'r') as f:
    return f.read()
```

Because the operating system interprets `..` as "go up one directory," an attacker or confused agent could escape the designated project sandbox and read or overwrite any file on the host machine.

---

## Issue 2: Agentic Privilege Escalation & Prompt Injections
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-5)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-6)
When third-party modders interacted with the agent, they could prompt the AI:
> *"Update the server configuration in `server.py` to disable authentication."*

Because the AI was running with the host user's full permissions, it attempted to rewrite core engine files, bypassing web UI restrictions.

### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-7)
Traditional permission models only check the human user's login. But in an agentic system, the AI acts as an autonomous proxy. If the AI is launched without an explicit sandbox container and without workspace confinement, it executes commands with full administrative access.

---

## The Architectural Solution
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-8)

To achieve uncompromising defense-in-depth, Siraugga instituted four defensive layers:

### 1. Cryptographic Path Canonicalization (`resolve_safe_path`)
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-1)
All file requests must pass through `resolve_safe_path()` before touching the disk:

```python
def resolve_safe_path(base_dir: str, requested_path: str) -> str:
    # 1. Resolve symlinks and normalize '..'
    resolved_base = os.path.realpath(base_dir)
    target_path = os.path.realpath(os.path.join(resolved_base, requested_path))
    
    # 2. Assert target begins strictly with base_dir
    common = os.path.commonpath([resolved_base, target_path])
    if common != resolved_base:
        raise PermissionError("Path traversal violation detected!")
        
    return target_path
```

### 2. Workspace Confinement & CLI Sandboxing
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-2)
For non-admin roles (`gamedev`, `modder`):
- The agent process `cwd` is locked strictly inside their assigned project folder.
- The `--sandbox` flag is enforced, restricting terminal commands to virtual containers.
- The `--dangerously-skip-permissions` flag is permanently disabled.

### 3. File Classification Tiers
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-3)
Tier 2 (Core Engine) and Tier 4 (Forbidden) files are filtered out of all directory listings and cannot be opened by non-administrators.

---

## Why Order Matters in Path Validation
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-9)

1. **`realpath()` Before `commonpath()`**:
   - You must resolve symbolic links and relative path sequences with `os.path.realpath()` *before* checking common ancestor paths. Checking string prefixes before resolution allows symlink bypasses.
2. **Boundary Check Before Disk Access**:
   - The security verification must raise an exception *before* calling `os.path.exists()` or `open()`. Interrogating file metadata on forbidden paths leaks folder existence to attackers.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-10)

### Q: What is a symlink and how does it bypass security?
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-11)
**A:** A symbolic link (symlink) is a shortcut that points to another file. If a user creates a link named `notes.txt` that points to `/etc/shadow`, an unhardened server might read the sensitive file thinking it is just a text note. `os.path.realpath()` resolves links to their true destination.

### Q: Why do we raise `PermissionError` instead of returning an empty file?
[//]: # (SECTION_ID: SIRA-DOC-01_03-SEC-12)
**A:** Raising an explicit error signals an active security event, logs an audit alert to Tier 3 logs, and returns an HTTP 403 Forbidden code to the client.
