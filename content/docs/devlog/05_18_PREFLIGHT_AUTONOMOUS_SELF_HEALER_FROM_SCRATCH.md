# Pre-Flight Autonomous Self-Healer from Scratch

## 1. Architectural Role & Module Overview
When backend modules fail due to accidental syntax errors or corrupted patch deployments, standard servers crash abruptly on boot, taking down developer dashboards and terminating active WebSocket streams.

The Pre-Flight Autonomous Self-Healer (`self_healer.py`) acts as a protective supervisor before the server imports any application modules. It verifies Python AST syntax across all core files, initiates instant rollback from backups if available, or autonomously invokes a headless repair CLI to fix the syntax error, verify the fix, and resume server boot with zero human intervention.

```
+-------------------------------------------------------------+
|               Pre-Flight Diagnostics (Startup)              |
+-------------------------------------------------------------+
                              |
                     Compile All .py Files
                              |
               +--------------+--------------+
               |                             |
             PASS                          FAIL
               |                             |
      Boot ASGI Server            SyntaxError / Traceback Caught
                                             |
                                  +----------+----------+
                                  |                     |
                            Backup Exists?         No Backup
                                  |                     |
                                 YES                    v
                                  |            Spawn Headless CLI Agent
                         Instant Rollback      ("Fix SyntaxError in file...")
                                  |                     |
                                  +----------+----------+
                                             |
                                    Re-run Diagnostics
                                             |
                                      Verified? -> Boot!
```

---

## 2. Complete Python Implementation
Save the following script as `self_healer.py`:

```python
import os
import sys
import shutil
import py_compile
import subprocess
import traceback

CORE_DIR = "./core"
BACKUP_DIR = "./core/backups"

def run_preflight_diagnostics(target_dir: str = CORE_DIR) -> tuple[bool, str, str]:
    """Compiles all Python files in target_dir using py_compile."""
    print(f"[DIAGNOSTICS] Scanning {target_dir} for syntax integrity...")
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                try:
                    py_compile.compile(full_path, doraise=True)
                except py_compile.PyCompileError as err:
                    print(f"[PREFLIGHT-FAIL] Syntax error in {full_path}: {err}")
                    return False, full_path, str(err)
    print("[DIAGNOSTICS] All modules verified. Zero syntax errors detected.")
    return True, "", ""

def attempt_tier1_rollback(failed_file: str) -> bool:
    """Attempts instant restoration from a known-good backup."""
    basename = os.path.basename(failed_file)
    backup_path = os.path.join(BACKUP_DIR, basename)
    if os.path.exists(backup_path):
        print(f"[TIER-1 ROLLBACK] Restoring {failed_file} from {backup_path}...")
        shutil.copy2(backup_path, failed_file)
        # Verify restored version
        try:
            py_compile.compile(failed_file, doraise=True)
            print("[TIER-1 ROLLBACK] Successful. File integrity restored.")
            return True
        except Exception:
            print("[TIER-1 ROLLBACK] Backup file also corrupted. Escalating...")
    return False

def invoke_tier2_agent_repair(failed_file: str, error_details: str) -> bool:
    """Spawns a headless CLI agent to autonomously repair the syntax error."""
    print(f"[TIER-2 AI REPAIR] Invoking autonomous repair agent on {failed_file}...")
    prompt = (
        f"CRITICAL FIX REQUIRED: The Python file '{failed_file}' has a syntax error.\n"
        f"Error details: {error_details}\n"
        f"Inspect the file, fix the syntax error directly, and verify clean compilation.\n"
        f"Do not modify business logic or delete unrelated code."
    )
    
    cmd = ["agy", "--prompt", prompt, "--sandbox=false"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(f"[AGENT-OUTPUT] {proc.stdout[:300]}...")
        # Verify if agent's repair compiled cleanly
        py_compile.compile(failed_file, doraise=True)
        print("[TIER-2 AI REPAIR] Verification passed! Agent successfully fixed the file.")
        return True
    except Exception as e:
        print(f"[TIER-2 AI REPAIR] Autonomous repair failed: {e}")
        return False

def boot_with_self_healing():
    """Supervisor loop that validates code before launching the main server."""
    success, failed_file, err_msg = run_preflight_diagnostics()
    if not success:
        # Try rollback first
        if not attempt_tier1_rollback(failed_file):
            # Escalate to autonomous agent repair
            repaired = invoke_tier2_agent_repair(failed_file, err_msg)
            if not repaired:
                print("[FATAL] Self-healing sequence exhausted. Boot aborted.")
                sys.exit(1)
        
        # Re-verify everything before booting
        final_ok, _, _ = run_preflight_diagnostics()
        if not final_ok:
            print("[FATAL] System remains in an uncompilable state. Boot halted.")
            sys.exit(1)

    print("[BOOT] Bootstrapping ASGI Hypercorn server...")
    # Launch Quart / Hypercorn server here

if __name__ == "__main__":
    boot_with_self_healing()
```

---

## 3. Why Order Matters in Self-Healing Execution
1. **Compile Before Import**: Executing `py_compile.compile()` inspects the abstract syntax tree without executing module-level side effects or importing broken dependencies.
2. **Rollback Before AI Repair**: Rolling back from a validated backup completes in < 5ms, avoiding unnecessary LLM API costs and network latency.
3. **Re-Compile After Agent Repair**: Never trust an AI model's output blindly. Re-running `py_compile.compile(..., doraise=True)` provides deterministic verification before booting the server.

---

## 4. Beginner Coder Q&A
**Q: Does `py_compile` execute any code?**  
A: No! It only parses the code into Python bytecode (`.pyc`). If there are syntax errors (like missing colons or mismatched brackets), it raises an exception without running the file.

**Q: Why use `doraise=True` in `py_compile.compile()`?**  
A: By default, `py_compile.compile()` prints errors to `sys.stderr` and returns silently. `doraise=True` forces it to raise `PyCompileError` so our script can catch it and act.

**Q: Can this create an infinite loop if the AI keeps making errors?**  
A: No. Notice the script tries rollback once, invokes the agent once, and terminates (`sys.exit(1)`) if the re-verification check fails.
