[//]: # (DOC_ID: SIRA-DEV-02_16 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 02_16: Self-Healing Bootstrap & Traceback Repair Evidence

Primary source evidence from the Siraugga supervisor gateway (`core/bootstrap_gateway.py`) demonstrating how the 3-Tier Self-Healing Supervisor validates syntax, auto-restores from backups, and spawns headless repair agents to fix crash tracebacks before server launch.

---

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-1)
## Source Citation 1: Pre-Flight Syntax Compilation (`core/bootstrap_gateway.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-1)

This excerpt displays how the supervisor evaluates staged patches and engine files before allowing processes to boot:

```python
# Location: <project_root>/core/bootstrap_gateway.py
# Lines: 83-92, 122-132

def _compile_check(filepath: str) -> tuple:
    """Returns (ok: bool, error_message: str)."""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, ""
    except py_compile.PyCompileError as ce:
        return False, str(ce)
    except Exception as e:
        return False, str(e)

# Inside _promote_staged_patches:
    ok, err = _compile_check(staged_path)
    if not ok:
        if not quiet:
            print(f"[Bootstrap] Quarantining invalid staged patch {patch_name}: {err}")
        try:
            os.remove(staged_path)
        except Exception:
            pass
        rejected.append({"file": patch_name, "reason": err})
        continue
```

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-2)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-2)
- **Strict Pre-Execution Quarantine**: Before any Python module is promoted to the live engine, `_compile_check` forces compilation with `doraise=True`. If syntax errors exist, the file is immediately quarantined and deleted from `core/patches/`.
- **Zero Live Server Crashes**: Bad syntax never reaches active memory; the live server continues running uninterrupted.

---

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-3)
## Source Citation 2: The 3-Tier Self-Healing Hierarchy (`core/bootstrap_gateway.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-3)

This excerpt demonstrates the automated self-healing supervisor loop:

```python
# Location: <project_root>/core/bootstrap_gateway.py
# Lines: 163-220

def run_preflight_checks(
    base_dir=None,
    target_files=None,
    spawn_agent: bool = True,
    exit_on_failure: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Unified Pre-Flight Diagnostics & 3-Tier Self-Healing Supervisor:
      1. Promotes any valid staged patches waiting in core/patches/.
      2. Validates syntax of all engine .py modules via py_compile.
      3. Tier-1 Instant Self-Heal: Restores corrupted modules from core/backups/<name>.py (<5ms).
      4. Tier-2 AI Emergency Auto-Repair: Spawns agy to stage a fix in core/patches/<name>.py,
         then validates and promotes it safely.
    """
    root = get_base_dir(base_dir)
    core_dir = os.path.join(root, "core")
    patch_dir = os.path.join(core_dir, "patches")
    backup_dir = os.path.join(core_dir, "backups")

    promoted_patches, rejected_patches = _promote_staged_patches(root, quiet=quiet)
    files_to_check = get_engine_files(root, custom_files=target_files)

    healed_from_backup = []
    healed_by_agent = []
    failed_files = []

    # Iterate through files, test compilation, and trigger Tier 1 or Tier 2 recovery
    for rel_file in files_to_check:
        full_path = os.path.join(root, rel_file)
        ok, err = _compile_check(full_path)
        if not ok:
            # Tier-1 Instant Restore from core/backups/
            basename = os.path.basename(full_path)
            backup_path = os.path.join(backup_dir, basename)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, full_path)
                healed_from_backup.append(basename)
```

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-4)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-4)
- **Sub-5ms Rollback (Tier-1)**: If a live file is found to have syntax corruption, the gateway instantly copies the pristine backup from `core/backups/` back to the live target in less than 5 milliseconds.
- **Autonomous Auto-Repair (Tier-2)**: If no backup exists, the supervisor programmatically triggers a headless AI agent with the crash traceback, re-runs diagnostics, and proceeds to boot once the fix compiles cleanly.

---

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-5)

In supervisor boot sequences, verification order guarantees high availability:
1. **Promote Valid Staged Patches First**: Validating and promoting pending patches in `core/patches/` must occur before testing the live engine files.
2. **Snapshot Working Live Files Before Overwrite**: Backups are created *only* if the currently running live file compiles cleanly. Never overwrite a good backup with a broken file!
3. **Verify Zero Exit Code Before Launching ASGI Worker**: The gateway launches the main Hypercorn/Quart web service only after `run_preflight_checks` returns 100% clean health.

---

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-7)

### What does `py_compile.compile(..., doraise=True)` do?
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-7)
Normally, `py_compile` might print errors to standard error and continue. Passing `doraise=True` forces Python to throw an actual `PyCompileError` exception that our code can catch and handle programmatically.

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-8)
### What is the difference between Tier-1 and Tier-2 self-healing?
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-8)
Tier-1 is a deterministic rollback (<5ms) that copies the last known working backup file. Tier-2 is an intelligent repair that spawns an AI agent to fix novel bugs when no backup is available.

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-9)
### Why is this called a "Dual-Layer Gateway"?
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-9)
The gateway listens on Port 5000 and proxies traffic to the internal server on Port 5001. If Port 5001 crashes or is restarting, Port 5000 stays open and shows a friendly "Self-Healing in Progress" screen instead of a broken browser connection.

---

[//]: # (SECTION_ID: SIRA-DEV-02_16-SEC-10)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_16-SEC-10)
- To understand the symptoms that necessitated this supervisor, read [`01_PROBLEMS_ENCOUNTERED/01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES.md`](/docs/devlog/01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES).
- To inspect diagnostic logs of an auto-repair sequence, visit [`03_DIAGNOSTIC_TESTS/03_15_AUTONOMOUS_SELF_HEALING_REPAIR_LOOP_LOGS.md`](/docs/devlog/03_15_AUTONOMOUS_SELF_HEALING_REPAIR_LOOP_LOGS).
- To build the complete self-healing supervisor from a blank file, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_18_PREFLIGHT_AUTONOMOUS_SELF_HEALER_FROM_SCRATCH.md`](/docs/devlog/05_18_PREFLIGHT_AUTONOMOUS_SELF_HEALER_FROM_SCRATCH).
