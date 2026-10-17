[//]: # (DOC_ID: SIRA-DOC-02_03 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 02.3: Source Evidence: Safe Hot-Patching & Self-Healing Engine

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE.md`](/docs/devlog/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE)
- **Next Source Evidence**: [`02_04_FORENSIC_VAULT_AND_PII_SCRUBBING_EVIDENCE.md`](/docs/devlog/02_04_FORENSIC_VAULT_AND_PII_SCRUBBING_EVIDENCE)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-1)

This chapter documents verbatim source citations from Siraugga's zero-downtime hot-patching engine (`core/routes/system.py`). 

It provides concrete code proof of how pre-compilation syntax checks, snapshot backups, in-memory module reloading, and automated rollbacks maintain 100% server availability on Port 5000 without process restarts.

---

## Source 1: The 4-Stage Hot-Patch Execution Sequence
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-2)

- **Source File**: `<project_root>/core/routes/system.py`
- **Location**: Lines 24–130

```python
async def execute_hot_patch_sequence(app_obj=None, manual_trigger=False, fast_countdown=False):
    """Safe zero-downtime hot-patching sequence with syntax validation (py_compile), 
    backup, and automated rollback."""
    import py_compile
    core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    patch_dir = os.path.join(core_dir, "patches")
    backup_dir = os.path.join(core_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    applied_targets = []
    
    # Stage 1: Pre-Compilation Syntax Validation
    for patch in os.listdir(patch_dir):
        if not patch.endswith(".py"):
            continue
        try:
            py_compile.compile(os.path.join(patch_dir, patch), doraise=True)
        except py_compile.PyCompileError as ce:
            print(f"[HOT-PATCH ERROR] Syntax check failed on {patch}: {ce}")
            return {"success": False, "error": f"Syntax error in {patch}"}

        # Stage 2: Atomic Backup Snapshot
        target_file = os.path.join(core_dir, patch)
        if os.path.exists(target_file):
            backup_file = os.path.join(backup_dir, patch)
            shutil.copy2(target_file, backup_file)
            applied_targets.append((patch, target_file, backup_file))
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-3)
1. **Pre-Flight Syntax Gating**: `py_compile.compile(..., doraise=True)` parses the staged patch before any disk changes occur. Invalid syntax is trapped immediately, protecting live code.
2. **Snapshot Guarantees**: Any existing live module is cloned to `core/backups/` before being overwritten, recording a reversible state tuple in `applied_targets`.

---

## Source 2: In-Memory Reload & Automated Rollback
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-4)

- **Source File**: `<project_root>/core/routes/system.py`
- **Location**: Lines 178–245

```python
    try:
        # Stage 3: Live File Swap and In-Memory Module Reload
        importlib.reload(session_manager)
        importlib.reload(project_manager)
        importlib.reload(agent_manager)
        importlib.reload(security_manager)

        # Clean up staged patch files only after successful reload
        for patch in os.listdir(patch_dir):
            if patch.endswith(".py"):
                os.remove(os.path.join(patch_dir, patch))

    except Exception as exc:
        print(f"[HOT-PATCH ROLLBACK] Runtime reload failed! Reverting: {exc}")
        # Stage 4: Automated Rollback on any failure
        for patch, target_file, backup_file in applied_targets:
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, target_file)
        
        # Re-reload previous stable versions in memory
        importlib.reload(session_manager)
        importlib.reload(project_manager)
        importlib.reload(agent_manager)
        importlib.reload(security_manager)
        return {"success": False, "error": f"Rollback triggered: {exc}"}
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-5)
1. **Zero Socket Destruction**: Modules are refreshed using `importlib.reload()`, keeping the Quart server and active WebSockets open.
2. **Self-Healing Rollback**: If an exception occurs during module reloads, the loop automatically copies backup files from `backup_dir` back to their live targets and re-reloads stable code.

---

## Why Order Matters in Hot-Patching
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-6)

1. **`py_compile` Before Disk Copy**:
   - Compiling the file in staging must occur *before* copying it over the live file. If you overwrite the live file first and compilation fails, the application crashes on the next import.
2. **Delete Staged Patch Only After Reload Confirmed**:
   - The patch file is removed from `core/patches/` *only after* all `importlib.reload()` calls succeed. If a reload fails, the staged file remains available for debugging.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-7)

### Q: Why not just restart Python with `os.system("python3 server.py")`?
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-8)
**A:** Restarting Python severs all active WebSocket connections, cancels background AI tasks, and can fail due to port binding collisions (`Address already in use`). Hot-patching updates logic without dropping a single packet.

### Q: What is `shutil.copy2()`?
[//]: # (SECTION_ID: SIRA-DOC-02_03-SEC-9)
**A:** `copy2` copies file contents *and* preserves metadata (timestamps, file permissions), ensuring backup files retain their exact historical attributes.
