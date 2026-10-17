[//]: # (DOC_ID: SIRA-DOC-02_32 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 02.32: Source Code Evidence: DevCore Environment Scratch & Shell Hooks

## Overview & Context
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-1)
This document cites primary source evidence from `scripts/scratch_devcore_from_alp.sh` and shell profile hooks (`~/.bashrc`) demonstrating how DevCore enforces strict virtual environment isolation, preflight service validation, and automated directory-aware environment switching.

---

## Source Citation 1: Preflight Dependency & Port Verification (`scripts/scratch_devcore_from_alp.sh`)
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-2)

```bash
# Location: <project_root>/scripts/scratch_devcore_from_alp.sh
# Lines 31-48

echo "[Step 1/4] Verifying DevCore virtual environment health..."
if [ ! -d "$DEVCORE_VENV" ] || [ ! -x "$DEVCORE_VENV/bin/python3" ]; then
    echo "ERROR: DevCore virtual environment not found at $DEVCORE_VENV"
    echo "Please create and install dependencies in $DEVCORE_VENV first."
    exit 1
fi

if ! "$DEVCORE_VENV/bin/python3" -c "
import quart, hypercorn, spacy, presidio_analyzer, playwright, mcp, cryptography
" 2>/dev/null; then
    echo "ERROR: DevCore virtual environment is missing required core dependencies."
    echo "Run dependency installation in $DEVCORE_VENV before purging alp-env."
    exit 1
fi
echo "DevCore virtual environment dependencies verified."
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-3)
- The script refuses to delete or purge dependencies from the source environment until the isolated DevCore virtualenv (`$HOME/.venvs/devcore`) has proven that all critical packages (`quart`, `hypercorn`, `presidio_analyzer`, `cryptography`, `playwright`, `mcp`) compile and import without errors.

---

## Source Citation 2: Directory-Aware Automated Shell Hooks (`~/.bashrc`)
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-4)

```bash
# Location: $HOME/.bashrc
# Shell environment switching automation

_auto_venv_hook() {
    case "$PWD" in
        */alp-env*)
            if [ "$VIRTUAL_ENV" != "$HOME/alp-env" ] && [ -f "$HOME/alp-env/bin/activate" ]; then
                source "$HOME/alp-env/bin/activate"
            fi
            ;;
        */DevCore*)
            if [ "$VIRTUAL_ENV" != "$HOME/.venvs/devcore" ] && [ -f "$HOME/.venvs/devcore/bin/activate" ]; then
                source "$HOME/.venvs/devcore/bin/activate"
            fi
            ;;
    esac
}

cd() {
    builtin cd "$@" || return $?
    _auto_venv_hook
}

if [[ ! "$PROMPT_COMMAND" =~ "_auto_venv_hook" ]]; then
    PROMPT_COMMAND="_auto_venv_hook${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-5)
- The shell environment dynamically detects when a developer enters a DevCore directory or an ALP directory, executing `source` automatically to guarantee that all terminal commands run under the correct Python interpreter.

---

## 3. Why Order Matters in Environment Scratches
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-3)
1. **Import Test Before Service Checks**: Verifying Python library availability must occur before querying the network port to distinguish between runtime crashes and network binding delays.
2. **Listen Check Before Dependency Purge**: Checking `ss -tulpn | grep :5000` ensures that a live server process is actively responding from the new environment before removing packages from the old one.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-4)

### What does `builtin cd` mean in the shell script?
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-6)
In Bash, if you define a function named `cd`, typing `cd` would call the function recursively and cause an infinite loop. `builtin cd` tells Bash to run the real internal Linux command rather than calling the custom wrapper function again.

### Why use `PROMPT_COMMAND` alongside `cd`?
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-7)
Wrapping `cd` only catches directory changes made with `cd`. If a developer uses a tool, a script, or another shortcut that alters working directories without `cd`, `PROMPT_COMMAND` re-verifies the environment before displaying the prompt.

---

## 5. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-02_32-SEC-5)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS.md`](/docs/devlog/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS.md`](/docs/devlog/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_32_ENVIRONMENT_ISOLATION_AND_SHELL_HOOK_ARCHITECTURE.md`](/docs/devlog/04_32_ENVIRONMENT_ISOLATION_AND_SHELL_HOOK_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_34_SCRATCH_DEVCORE_PURGE_TOOL_FROM_SCRATCH.md`](/docs/devlog/05_34_SCRATCH_DEVCORE_PURGE_TOOL_FROM_SCRATCH)
