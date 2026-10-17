[//]: # (DOC_ID: SIRA-DOC-04_30 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# PreToolUse Hook & Function Lock Architecture

## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_30-SEC-1)
Securing an AI platform solely at the web API layer is insufficient. Autonomous agents have direct access to native environment tools (`write_to_file`, `replace_file_content`, `edit_lines`, `run_command`). If an agent attempts to overwrite a critical security module, it bypasses the web portal entirely.

The PreToolUse Hook Architecture (`.agents/raugus_hook.py`) establishes an un-bypassable middleware layer. Every tool call must pass through the hook before execution, enforcing AST function-level write locks and RBAC tier clearances.

```
+-------------------------------------------------------------+
|                     Autonomous AI Agent                     |
|           Prepares Tool Call: replace_file_content          |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 PreToolUse Interception Hook                |
|                    (.agents/raugus_hook.py)                 |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
      Clearance Verified            Violation Detected
      (Safe Playground Path)        (Locked Function / High Tier)
               |                             |
               v                             v
       {"decision": "approve"}      {"decision": "deny"}
               |                             |
               v                             v
         Tool Executes               1. Block Execution
                                     2. Emit SIEM Intrusion Alert
                                     3. Return Reason to Agent
```

---

## 2. Function-Level Write Locks
[//]: # (SECTION_ID: SIRA-DOC-04_30-SEC-2)
Files often contain both general helper logic and critical security routines. Rather than locking entire files, the architecture enforces **Function-Level Write Locks**:
- Specific AST symbols (e.g., `reload_system`, `get_current_user`, `verify_key`) are marked as write-locked in the Raugus Map.
- If an edit targets lines within a locked symbol's span, the hook blocks the edit, even if the user has permission to edit the rest of the file.

---

## 3. Shell Command Sanitization
[//]: # (SECTION_ID: SIRA-DOC-04_30-SEC-3)
When `run_command` is invoked, the hook inspects the command line string for prohibited destructive actions:
- Commands like `rm -rf`, `mkfs`, `sudo`, `dd`, and destructive redirect operators are blocked.
- Path traversal sequences (`../../`) targeting system files like `/etc/shadow` trigger immediate execution denials.

---

## 4. Why Order Matters in Tool Hook Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_30-SEC-4)
1. **Intercept Before Disk Mutation**: The hook must evaluate permissions *prior* to executing the tool call to prevent destructive modifications.
2. **Dispatch SIEM Alert Before Denial Response**: Logging the security event before exiting guarantees that forensic records exist even if the agent aborts.
3. **Parse AST on Proposed Diff Before Acceptance**: Checking that the replacement text forms valid Python syntax prevents agents from breaking codebases with syntax errors.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_30-SEC-5)
**Q: Where is the PreToolUse hook configured?**  
A: In `.agents/hooks.json`, which instructs the Antigravity agentic engine to route all tool dispatches through `raugus_hook.py`.

**Q: Does this hook add noticeable lag to development?**  
A: No! The hook executes in under 25 milliseconds, providing real-time security validation without disrupting developer typing or response streaming.

**Q: Can a prompt injection trick the agent into disabling the hook?**  
A: No. The hook runs as an external OS process outside the AI agent's prompt context. The agent cannot modify the hook because `.agents/` is a Tier-2 protected folder.
