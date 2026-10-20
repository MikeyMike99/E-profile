[//]: # (DOC_ID: SIRA-ARCH-05_05 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.5: From-Scratch Creation Guide: Zero-Downtime Hot-Patch Runner

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_04_RAUGUS_OPAQUE_VFS_FROM_SCRATCH.md`](/docs/devlog/05_04_RAUGUS_OPAQUE_VFS_FROM_SCRATCH)
- **Next From-Scratch Guide**: [`05_06_FORENSIC_SESSION_VAULT_FROM_SCRATCH.md`](/docs/devlog/05_06_FORENSIC_SESSION_VAULT_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-1)

This guide walks you through building an automated **Zero-Downtime Hot-Patch Runner** (`hot_patch_runner.py`) from a blank editor.

This script allows you to update backend Python modules in live servers on Port 5000 with pre-compilation syntax checks, snapshot backups, and automatic self-healing rollbacks.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-3)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-3)
```bash
nano hot_patch_runner.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-4)
### Step 2: Implement the 4-Stage Hot-Patch Function (Lines 1–45)
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-4)
```python
import importlib
import os
import py_compile
import shutil
import sys

def apply_staged_patches(staging_dir: str, live_dir: str, backup_dir: str):
    """Safely validates, backs up, swaps, and reloads code in memory."""
    os.makedirs(backup_dir, exist_ok=True)
    applied_patches = []

    for filename in os.listdir(staging_dir):
        if not filename.endswith(".py"):
            continue

        staged_file = os.path.join(staging_dir, filename)
        live_file = os.path.join(live_dir, filename)
        backup_file = os.path.join(backup_dir, filename)

        try:
            # Stage 1: Pre-Flight Syntax Compilation
            print(f"[HOT-PATCH] Validating syntax for {filename}...")
            py_compile.compile(staged_file, doraise=True)

            # Stage 2: Atomic Backup Snapshot
            if os.path.exists(live_file):
                print(f"[HOT-PATCH] Snapshotting backup to {backup_file}...")
                shutil.copy2(live_file, backup_file)
                applied_patches.append((live_file, backup_file))

            # Stage 3: File Swap and In-Memory Module Reload
            shutil.copy2(staged_file, live_file)
            mod_name = filename[:-3]
            if mod_name in sys.modules:
                print(f"[HOT-PATCH] Reloading module in memory: {mod_name}")
                importlib.reload(sys.modules[mod_name])

            # Cleanup staged file only on success
            os.remove(staged_file)
            print(f"[HOT-PATCH SUCCESS] Successfully patched {filename}!")

        except Exception as err:
            print(f"[HOT-PATCH ROLLBACK] Error occurred: {err}. Initiating rollback...")
            # Stage 4: Automated Rollback on any failure
            for target, backup in applied_patches:
                if os.path.exists(backup):
                    shutil.copy2(backup, target)
            raise RuntimeError(f"Hot-patch aborted and rolled back: {err}")
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-5)
## Why Order Matters in Hot-Patch Runners
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-5)

1. **`py_compile` Before Any File Copy**:
   - Staged files must be compiled *before* creating backups or touching live files. If you overwrite the live file first, a syntax error breaks the server immediately.
2. **Snapshot Live State Before Overwriting**:
   - Always copy the current working version to `backup_dir` before copying the patch. If you don't take a snapshot first, you have nothing to restore when an exception occurs.
3. **Delete Staged Patch Only After Reload Confirmation**:
   - Removing the patch from `staging_dir` must be the final action. If the reload fails, leaving the staged patch intact allows the engineer to inspect what caused the failure.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-6)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-6)

Verify that your hot-patch runner applies clean code and automatically rolls back broken code:

```bash
python3 -c "
import os
from hot_patch_runner import apply_staged_patches

os.makedirs('/tmp/hotpatch_demo/staging', exist_ok=True)
os.makedirs('/tmp/hotpatch_demo/live', exist_ok=True)
os.makedirs('/tmp/hotpatch_demo/backup', exist_ok=True)

# 1. Setup stable live file
with open('/tmp/hotpatch_demo/live/worker.py', 'w') as f:
    f.write('def status(): return \"STABLE_V1\"\n')

# 2. Stage broken syntax patch
with open('/tmp/hotpatch_demo/staging/worker.py', 'w') as f:
    f.write('def status( broken syntax!\n')

# 3. Test rollback
try:
    apply_staged_patches(
        '/tmp/hotpatch_demo/staging',
        '/tmp/hotpatch_demo/live',
        '/tmp/hotpatch_demo/backup'
    )
except RuntimeError as e:
    print('[PASS] Rollback Triggered:', e)

# 4. Verify live file is still STABLE_V1
with open('/tmp/hotpatch_demo/live/worker.py') as f:
    print('[PASS] Live File Content:', f.read().strip())
"
```

**Expected Output**:
```text
[PASS] Rollback Triggered: Hot-patch aborted and rolled back: ...
[PASS] Live File Content: def status(): return "STABLE_V1"
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-7)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-8)

### Q: Why do we pass `doraise=True` to `py_compile.compile()`?
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-8)
**A:** By default, `py_compile.compile()` writes errors to `sys.stderr` and returns silently. Passing `doraise=True` forces it to raise a real Python `PyCompileError` exception that our `try...except` block can catch.

[//]: # (SECTION_ID: SIRA-ARCH-05_05-SEC-9)
### Q: What is `sys.modules`?
[//]: # (SECTION_ID: SIRA-DOC-05_05-SEC-9)
**A:** `sys.modules` is Python's internal dictionary where all currently loaded modules are stored. Looking up `mod_name in sys.modules` tells us if the code is actively running in memory.

> [!WARNING] Line Ending Advisory (CRLF vs LF)
> If you are authoring this file on Windows for execution within Linux or WSL, ensure your text editor saves with Unix line endings (`LF`). Windows carriage returns (`CRLF`) will cause bash and Python interpreters to fail with unexpected syntax errors.


---

## 10-Second Verification Checklist

To verify that your newly created file is functioning properly:
- [ ] Confirm the file is saved with the exact filename and correct extension in the target directory.
- [ ] Run `python3 <filename> --help` or execute the script in dry-run mode to verify clean startup.
- [ ] Inspect console output to confirm there are no syntax errors or missing module tracebacks.

