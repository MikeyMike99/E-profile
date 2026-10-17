# Pillar 04.8: Architecture Solutions: In-Memory Execution & Clean Workspace Protocol

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_07_THE_VOICE_OF_SIRAUGGA_CINEMATIC_TTS_ARCHITECTURE.md`](/docs/devlog/04_07_THE_VOICE_OF_SIRAUGGA_CINEMATIC_TTS_ARCHITECTURE)
- **Next: From-Scratch Creation Guides**: [`../05_FROM_SCRATCH_CREATION_GUIDES/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH.md`](/docs/devlog/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH)

---

## Overview

In traditional software development, engineers and AI assistants often litter project directories with one-off "scratch" scripts (`test_fix.py`, `temp_config.json`, `debug.sh`).

In a Zero-Trust environment, leaving dead test scripts behind causes **Digital Hoarding**, exposes sensitive credentials, and creates critical security vulnerabilities (such as Source Code Disclosure, CWE-530).

This chapter details Siraugga's **Clean Workspace Protocol** and in-memory execution architecture.

---

## The Clean Workspace Protocol

The Siraugga platform enforces four mandatory hygiene directives across all agents and background subagents:

### 1. Piped Execution Preference
Whenever possible, execute shell scripts or Python logic dynamically via stdin pipes rather than writing physical `.py` or `.sh` files to disk:
```bash
# RECOMMENDED: Zero disk footprint via stdin pipe
python3 - << 'EOF'
import os
print("Checking active environment:", os.environ.get("VIRTUAL_ENV"))
EOF
```

### 2. Mandatory Immediate Cleanup
If a diagnostic script *must* be written to disk (for example, to test multi-process behavior), the file must be deleted immediately in the very next tool step.

### 3. Ephemeral Secrets (Memory Only)
Passwords, API keys, and sensitive environment variables must never be written to physical `.env`, JSON, or YAML files that linger in the workspace. Secrets are passed purely through process memory and environment variables for the duration of the subprocess.

### 4. Artifact Restraint
Documentation, devlogs, and system configurations are created only when explicitly requested by the user or required by architecture. Single-use test files are strictly forbidden from remaining on disk.

---

## In-Memory Source Code Execution

```text
+-------------------------------------------------------------------------------+
|                        Legacy Vulnerable Pattern                              |
|   Agent writes: scratch_test.py -> Runs: python3 scratch_test.py               |
|   (Leaves credentials on disk, pollutes git status, triggers CWE-530)         |
+-------------------------------------------------------------------------------+
                                        |
                                        v (The Clean Workspace Architecture)
+-------------------------------------------------------------------------------+
|                    Piped In-Memory Execution Architecture                     |
|   cat << 'EOF' | python3 -                                                    |
|   - Bytecode compiles directly into memory (RAM)                              |
|   - Executes immediately; zero files written to disk                          |
|   - Leaves git working tree 100% clean and pristine                           |
+-------------------------------------------------------------------------------+
```

---

## Why Order Matters in Workspace Hygiene

1. **Delete Temporary Test Files in `finally` Blocks**:
   - Disk cleanup must be wrapped in `finally` handlers. If a test script raises an uncaught exception and crashes, a standard sequential delete statement will never execute, leaving orphaned files behind.
2. **Pass Secrets via Subprocess Environment Before Process Launch**:
   - Environment variables must be injected into the `env={...}` parameter during process creation. Trying to pass secrets via intermediate config files exposes tokens to disk-scraping attacks.

---

## Beginner Coder Q&A

### Q: Why is leaving a scratch script on disk dangerous?
**A:** Scratch scripts often contain hardcoded passwords, personal file paths, or bypass flags used during quick debugging. If committed to Git or exposed via a web server misconfiguration, attackers can read sensitive system internals.

### Q: What is CWE-530?
**A:** Common Weakness Enumeration 530 refers to "Exposure of Structural Information through Temporary Files," where backup or scratch files (like `.bak` or `test.py`) inadvertently reveal system source code to unauthorized users.
