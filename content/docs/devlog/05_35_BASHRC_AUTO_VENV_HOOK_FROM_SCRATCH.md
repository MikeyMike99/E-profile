[//]: # (DOC_ID: SIRA-DOC-05_35 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 05.35: From-Scratch Creation Guide: Directory-Aware Bash Shell Auto-Venv Hook

## Overview & Beginner Context
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-1)
This guide teaches you how to write the `_auto_venv_hook` and directory-aware shell functions line by line into your Linux user profile (`~/.bashrc`). This hook automatically switches virtual environments when you change folders, eliminating manual activation mistakes.

---

## 1. Line-by-Line Construction
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-1)

### Block 1: Dedicated Activation Functions (Lines 1–20)
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-2)
```bash
alp() {
    if [ -f "$HOME/alp-env/bin/activate" ]; then
        source "$HOME/alp-env/bin/activate"
        cd "$HOME/alp-env/nomvula_agri_finance" 2>/dev/null || cd "$HOME/alp-env" 2>/dev/null
        echo "ALP environment activated in $PWD"
    fi
}
alias activate-alp='alp'

devcore-env() {
    if [ -f "$HOME/.venvs/devcore/bin/activate" ]; then
        source "$HOME/.venvs/devcore/bin/activate"
        cd "/mnt/c/Users/$USER/Documents/DevCore" 2>/dev/null || true
        echo "DevCore environment activated in $PWD"
    fi
}
alias devcore='devcore-env'
```
- Defines quick-jump functions `alp` and `devcore-env` that both activate the target environment and navigate directly to the workspace folder.

### Block 2: The Path Evaluation Hook (Lines 21–40)
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-3)
```bash
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
```
- Uses a `case` statement to match `$PWD` against directory patterns. It only sources the environment if `$VIRTUAL_ENV` is not already pointing to it, avoiding redundant subshell work.

### Block 3: Overriding `cd` & Registering `PROMPT_COMMAND` (Lines 41–55)
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-4)
```bash
cd() {
    builtin cd "$@" || return $?
    _auto_venv_hook
}

if [[ ! "$PROMPT_COMMAND" =~ "_auto_venv_hook" ]]; then
    PROMPT_COMMAND="_auto_venv_hook${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
```
- Overrides `cd` to invoke `_auto_venv_hook` immediately after every successful navigation.
- Injects `_auto_venv_hook` into `PROMPT_COMMAND` to catch any external directory shifts.

---

## 2. 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-2)
1. Open a new terminal.
2. Type `cd ~/alp-env` -> Run `which python3` -> Prints `$HOME/alp-env/bin/python3`.
3. Type `cd /mnt/c/Users/<user>/Documents/DevCore` -> Run `which python3` -> Prints `$HOME/.venvs/devcore/bin/python3`.

---

## 3. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-3)

### What does `return $?` mean?
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-5)
`$?` holds the exit status of the last executed command. If `builtin cd` failed (for example, the target folder doesn't exist), `return $?` stops the function and returns the exact error code without executing the hook.

---

## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-05_35-SEC-4)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS.md`](/docs/devlog/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_32_SCRATCH_DEVCORE_AND_BASHRC_HOOK_EVIDENCE.md`](/docs/devlog/02_32_SCRATCH_DEVCORE_AND_BASHRC_HOOK_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS.md`](/docs/devlog/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_32_ENVIRONMENT_ISOLATION_AND_SHELL_HOOK_ARCHITECTURE.md`](/docs/devlog/04_32_ENVIRONMENT_ISOLATION_AND_SHELL_HOOK_ARCHITECTURE)
