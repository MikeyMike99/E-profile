[//]: # (DOC_ID: SIRA-ARCH-05_34 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.34: From-Scratch Creation Guide: Environment Scratch & Dependency Purge Tool

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-1)
## Overview & Beginner Context
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-1)
This guide teaches you how to write the `scratch_devcore_from_alp.sh` script line by line from a completely blank editor window. This script safely verifies that a new virtual environment is fully functional and running before purging redundant dependencies from an old environment.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-1)
## 1. Beginner Safety Guidelines
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-1)
- **Windows vs Linux Line Endings**: Ensure your editor saves with Linux LF line endings, not Windows CRLF (`\r\n`), or Bash will throw `syntax error near unexpected token $'\r'`.
- **Executable Permissions**: Always run `chmod +x scripts/scratch_devcore_from_alp.sh` after creating the file.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-2)
## 2. Line-by-Line Construction
[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-2)

### Block 1: Shebang, Safe Bash Options & Variable Defaults (Lines 1–15)
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-2)
```bash
#!/usr/bin/env bash
set -e

DEVCORE_VENV="${DEVCORE_VENV:-$HOME/.venvs/devcore}"
ALP_VENV="${ALP_VENV:-$HOME/alp-env}"
SERVER_PORT=5000

MODE="run"
if [ "$1" = "--check" ]; then
    MODE="check"
elif [ "$1" = "--watch" ]; then
    MODE="watch"
elif [ "$1" = "--force" ]; then
    MODE="force"
fi
```
- **Line 1 (`#!/usr/bin/env bash`)**: Tells Linux to run this script with the Bash shell.
- **Line 2 (`set -e`)**: Tells Bash to stop immediately if any command returns an error.
- **Lines 4–6**: Sets default virtualenv paths using parameter expansion (`${VAR:-default}`).

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-3)
### Block 2: Target Virtualenv Dependency Verification (Lines 16–35)
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-3)
```bash
echo "[Step 1/4] Verifying DevCore virtual environment health..."
if [ ! -d "$DEVCORE_VENV" ] || [ ! -x "$DEVCORE_VENV/bin/python3" ]; then
    echo "ERROR: DevCore virtual environment not found at $DEVCORE_VENV"
    exit 1
fi

if ! "$DEVCORE_VENV/bin/python3" -c "
import quart, hypercorn, spacy, presidio_analyzer, playwright, mcp, cryptography
" 2>/dev/null; then
    echo "ERROR: DevCore virtual environment is missing required core dependencies."
    exit 1
fi
echo "DevCore virtual environment dependencies verified."
```
- Executes a python one-liner inside the new virtual environment. If any import fails, the script halts before any files are touched.

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-4)
### Block 3: Port 5000 Active Listener Audit (Lines 36–55)
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-4)
```bash
echo "[Step 2/4] Inspecting active server port ($SERVER_PORT)..."
PORT_PID=$(ss -tulpn 2>/dev/null | grep ":$SERVER_PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -n1 || true)

if [ -n "$PORT_PID" ]; then
    ACTIVE_EXE=$(readlink -f /proc/"$PORT_PID"/exe 2>/dev/null || true)
    if [[ "$ACTIVE_EXE" == *"$DEVCORE_VENV"* ]]; then
        echo "[PASS] DevCore server is running from dedicated virtualenv."
    else
        echo "[WARNING] Port $SERVER_PORT is owned by $ACTIVE_EXE (not $DEVCORE_VENV)."
        if [ "$MODE" != "force" ]; then
            exit 1
        fi
    fi
fi
```
- Uses `ss` and `/proc/<pid>/exe` to confirm that the server process listening on port 5000 was started with the new Python binary.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-3)
## 3. Complete Finished Script
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-3)

```bash
#!/usr/bin/env bash
set -e

DEVCORE_VENV="${DEVCORE_VENV:-$HOME/.venvs/devcore}"
ALP_VENV="${ALP_VENV:-$HOME/alp-env}"
SERVER_PORT=5000

MODE="run"
[ "$1" = "--check" ] && MODE="check"
[ "$1" = "--force" ] && MODE="force"

echo "[Step 1/4] Verifying DevCore environment..."
"$DEVCORE_VENV/bin/python3" -c "import quart, hypercorn, cryptography"

echo "[Step 2/4] Verifying Server Port..."
PORT_PID=$(ss -tulpn 2>/dev/null | grep ":$SERVER_PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -n1 || true)
[ -n "$PORT_PID" ] && echo "Active Server PID: $PORT_PID"

echo "[Step 3/4] Purging obsolete packages from $ALP_VENV..."
if [ "$MODE" != "check" ]; then
    "$ALP_VENV/bin/pip" uninstall -y quart hypercorn presidio-analyzer 2>/dev/null || true
fi

echo "[Step 4/4] Operation complete."
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-4)
## 4. 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-4)
1. Run `./scripts/scratch_devcore_from_alp.sh --check` -> Returns exit code 0.
2. Confirm server continues streaming without interruption.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-5)

### What does `cut -d= -f2` do?
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-5)
It splits text using the `=` symbol as a delimiter (`-d=`) and selects the second piece (`-f2`), extracting the raw PID number from `pid=1234`.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_34-SEC-6)
## 6. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-05_34-SEC-6)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS.md`](/docs/devlog/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_32_SCRATCH_DEVCORE_AND_BASHRC_HOOK_EVIDENCE.md`](/docs/devlog/02_32_SCRATCH_DEVCORE_AND_BASHRC_HOOK_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS.md`](/docs/devlog/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_32_ENVIRONMENT_ISOLATION_AND_SHELL_HOOK_ARCHITECTURE.md`](/docs/devlog/04_32_ENVIRONMENT_ISOLATION_AND_SHELL_HOOK_ARCHITECTURE)

---

## Why Order Matters

Every instruction and line in this creation guide follows a strict sequence:
1. **Environment & Constants First**: Defining global configurations and imports before execution prevents unresolved symbol references.
2. **Subsystem Dependencies**: Core logic functions rely on constructor initialization and prerequisite file structures being ready beforehand.
3. **Execution Guardrails**: Testing, invocation, and verification commands must only be run once all preceding code has been written and saved cleanly.

