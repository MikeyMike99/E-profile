[//]: # (DOC_ID: SIRA-DOC-04_32 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 04.32: Architectural Blueprint: Environment Isolation & Automated Shell Hooks

## Executive Summary
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-1)
This blueprint details the architectural solution for decoupling DevCore from legacy or academic environments (`alp-env`) into a sovereign, dedicated virtual environment (`$HOME/.venvs/devcore`), coordinated by directory-aware Bash shell hooks and an automated preflight transition tool (`scratch_devcore_from_alp.sh`).

---

## 1. Architectural System Topology
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-1)

```
Developer Terminal Navigation Workflow:
User `cd $HOME/.../DevCore`
          │
          ▼
Bash `cd` Function Intercept
          │
          ▼
`_auto_venv_hook`
          │
          ├── Matches `*/DevCore*`? ──► Sourced `$HOME/.venvs/devcore/bin/activate`
          │
          └── Matches `*/alp-env*`?  ──► Sourced `$HOME/alp-env/bin/activate`
```

---

## 2. Component Breakdown & Lifecycle
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-2)

### 1. The Sovereign Virtual Environment (`$HOME/.venvs/devcore`)
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-1)
- Completely isolated from external academic scripts and third-party dependencies.
- Contains the complete, validated DevCore runtime stack: Quart, Hypercorn, spaCy, Presidio NLP, Playwright, Cryptography, and the MCP SDK.

### 2. The Transparent Shell Hook (`_auto_venv_hook`)
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-2)
- Injected into `~/.bashrc` to eliminate manual virtual environment activation errors.
- Integrates with both the overloaded `cd` wrapper and the Bash `PROMPT_COMMAND` supervisor, ensuring environment accuracy regardless of how the developer enters a project folder.

### 3. The Non-Destructive Purge Pipeline (`scratch_devcore_from_alp.sh`)
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-3)
- Enforces a 4-step safe transition protocol:
  1. **Preflight Health**: Verifies that all required packages exist and import cleanly in the new environment.
  2. **Port Audit**: Queries port 5000 using socket statistics (`ss`) to verify that the active server PID is running from the new virtual environment binary.
  3. **Diff Analysis**: Identifies redundant DevCore libraries residing in the old virtualenv without modifying files.
  4. **Purge Execution**: Safely uninstalls or removes obsolete dependencies from the old environment only after explicit developer confirmation or automated verification.

---

## 3. Why Order Matters in Environment Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-3)
1. **Target Verification Prior to Source Mutation**: Never uninstall or delete packages from an existing environment until the replacement environment passes 100% of integration smoke tests.
2. **Socket Verification Prior to Process Termination**: Always confirm that port 5000 is claimed by the new virtualenv interpreter to prevent breaking active client WebSocket connections.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-4)

### What happens if I open a new terminal window?
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-2)
Because `_auto_venv_hook` is defined in `~/.bashrc`, every new terminal window automatically inherits the hook. The moment you navigate to DevCore, the environment activates seamlessly.

### Can this setup work on Windows PowerShell too?
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-3)
Yes. In PowerShell, you achieve identical behavior by adding a `prompt` function hook to your `$PROFILE` that inspects `$PWD.Path` and executes `.venv\Scripts\Activate.ps1`.

---

## 5. Reusable Quick-Start Recipe (2-Minute Deployment)
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-5)
1. Add the `_auto_venv_hook` to `~/.bashrc`.
2. Reload shell: `source ~/.bashrc`.
3. Run diagnostic check: `./scripts/scratch_devcore_from_alp.sh --check`.
4. If verified, execute clean purge: `./scripts/scratch_devcore_from_alp.sh`.

---

## 6. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-04_32-SEC-6)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS.md`](/docs/devlog/01_36_VENV_CONTAMINATION_AND_ALP_SCRATCH_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_32_SCRATCH_DEVCORE_AND_BASHRC_HOOK_EVIDENCE.md`](/docs/devlog/02_32_SCRATCH_DEVCORE_AND_BASHRC_HOOK_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS.md`](/docs/devlog/03_29_VENV_SWITCHING_AND_PURGE_BENCHMARK_LOGS)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_34_SCRATCH_DEVCORE_PURGE_TOOL_FROM_SCRATCH.md`](/docs/devlog/05_34_SCRATCH_DEVCORE_PURGE_TOOL_FROM_SCRATCH)
