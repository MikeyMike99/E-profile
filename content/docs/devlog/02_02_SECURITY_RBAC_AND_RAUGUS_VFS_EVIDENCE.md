[//]: # (DOC_ID: SIRA-DEV-02_02 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.2: Source Evidence: Security RBAC & Raugus VFS Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE.md`](/docs/devlog/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE)
- **Next: Diagnostic Tests**: [`../03_DIAGNOSTIC_TESTS/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS.md`](/docs/devlog/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS)

---

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-1)

This chapter documents verbatim source citations from Siraugga's security subsystem (`security/security_manager.py`) and the Zero-Downtime Hot-Patch engine.

These citations provide concrete architectural proof of how Role-Based Access Control (RBAC), path traversal immunity, and in-memory module reloading operate.

---

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-2)
## Source 1: File Classification Tiers & Path Canonicalization
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-2)

- **Source File**: `<project_root>/security/security_manager.py`
- **Location**: Lines 26–29 & Lines 329–374

```python
# 1. Tier Constants
TIER_SAFE_WORKSPACE = "safe_workspace"
TIER_CORE_ENGINE = "core_engine"
TIER_ADMIN_LOG = "admin_log"
TIER_FORBIDDEN = "forbidden"

# 2. Canonical Path Traversal Defense
def resolve_safe_path(self, target_base: str, rel_path: str, user: dict = None) -> str:
    # Resolve symbolic links and normalize path structures
    base = os.path.realpath(target_base)
    resolved = os.path.realpath(os.path.join(base, rel_path.lstrip("/\\")))
    
    # Enforce strict boundary containment
    if not resolved.startswith(base + os.sep) and resolved != base:
        raise PermissionError(f"Directory traversal escape blocked: {rel_path}")
        
    tier = self.classify_file(rel_path)
    is_admin = user and user.get("role") == "admin"
    
    # Enforce role-based access rules
    if not is_admin and tier in (self.TIER_CORE_ENGINE, self.TIER_ADMIN_LOG, self.TIER_FORBIDDEN):
        raise PermissionError(f"Access to {tier} is denied for user role.")
        
    return resolved
```

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-3)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-3)
1. **Immunity to Traversal**: Any attempt to escape `target_base` using `../` or sneaky symlinks is caught by `os.path.realpath()` and string containment validation.
2. **Deterministic Role Gating**: Non-administrators are denied access to Core Engine, Admin Logs, and Forbidden directories before any file handle is opened.

---

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-4)
## Source 2: Safe 3-Step Hot-Patch Sequence
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-4)

- **Source File**: `<project_root>/core/routes/system.py` (Git Commit `b520f5f`)
- **Location**: Hot-Patch Execution Engine

```python
def execute_hot_patch_sequence():
    """Compiles, backs up, swaps, and reloads code in memory with auto-rollback."""
    for patch_file in os.listdir(STAGING_DIR):
        staged_path = os.path.join(STAGING_DIR, patch_file)
        live_path = os.path.join(LIVE_DIR, patch_file)
        backup_path = os.path.join(BACKUP_DIR, patch_file)
        
        try:
            # 1. Pre-Compilation Syntax Check
            py_compile.compile(staged_path, doraise=True)
            
            # 2. Atomic Backup Snapshot
            if os.path.exists(live_path):
                shutil.copy2(live_path, backup_path)
                
            # 3. Swap and In-Memory Module Reload
            shutil.copy2(staged_path, live_path)
            module_name = f"core.{patch_file[:-3]}"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                
            os.remove(staged_path)
            
        except Exception as err:
            # 4. Automated Rollback on any failure
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, live_path)
            raise RuntimeError(f"Hot-patch failed! Rolled back safely: {err}")
```

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-5)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-5)
1. **Zero Downtime**: Active WebSocket streams and running background tasks are not killed when server code is updated.
2. **Self-Healing Resilience**: If an engineer uploads a patch with a syntax error, `py_compile.compile` catches it before the file replaces live code. If a runtime reload fails, the backup is immediately restored.

---

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-6)
## Why Order Matters in Security & Hot-Patching
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-6)

1. **Syntax Compilation Before Live File Replacement**:
   - `py_compile.compile(..., doraise=True)` must succeed *before* overwriting the live module. If broken code is copied to disk first, the application is left in a corrupted state if the reload fails.
2. **Snapshot Backup Before Staging Copy**:
   - The original file must be copied to `BACKUP_DIR` *before* `shutil.copy2` moves the patch into place. Overwriting without a backup prevents automated rollback.

---

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-7)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-8)

### Q: Why do we use `rel_path.lstrip("/\\")`?
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-8)
**A:** On Unix and Windows systems, a leading slash or backslash (like `/etc` or `\Windows`) tells `os.path.join()` to treat the path as an absolute root path, completely discarding the `base` folder. Stripping leading slashes neutralizes this bypass.

[//]: # (SECTION_ID: SIRA-DEV-02_02-SEC-9)
### Q: What is `importlib.reload()`?
[//]: # (SECTION_ID: SIRA-DOC-02_02-SEC-9)
**A:** When Python imports a module, it caches the compiled bytecode in `sys.modules`. `importlib.reload()` forces Python to re-read the file from disk and update the running application in memory without stopping the process.
