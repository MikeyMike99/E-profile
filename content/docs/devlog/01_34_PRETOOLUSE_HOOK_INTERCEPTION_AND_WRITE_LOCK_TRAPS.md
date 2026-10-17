# PreToolUse Hook Interception & Write-Lock Traps

## 1. The Problem: The Native Tool Bypass Trap
Autonomous AI agents are equipped with powerful native file-editing tools such as `replace_file_content`, `write_to_file`, `edit_lines`, and `run_command`. While web API routes can enforce Role-Based Access Control (RBAC), an autonomous agent running inside the workspace can invoke its tools directly, completely bypassing web-level route guards.

If a junior subagent decides to overwrite `security/security_manager.py` or modify the system's token validation function, executing the tool call immediately compromises the host before post-execution audits can react.

```
+-------------------------------------------------------------+
|                     Autonomous Subagent                     |
|           Calls: default_api:write_to_file                  |
|           Target: security/security_manager.py              |
+-------------------------------------------------------------+
                              |
                     WITHOUT PRETOOLUSE HOOK
                     Tool Executes Directly on Disk!
                              |
                              v
+-------------------------------------------------------------+
|           [CRITICAL COMPROMISE: Security Layer Wiped]       |
|    - Post-execution scanners detect damage too late         |
|    - System integrity irreversibly damaged                  |
+-------------------------------------------------------------+
```

---

## 2. Granular Function Write-Locks
Even within permissible files, certain functions are mission-critical (such as password verification, hot-patch execution, or cryptographic seed derivation). Allowing an agent to modify an entire file when it only needed to update a helper utility risks accidentally deleting critical security routines.

---

## 3. The Solution: PreToolUse Interception & AST Write Locks
Siraugga instituted the Raugus PreToolUse Interception Hook (`.agents/raugus_hook.py`):
1. **Synchronous Interception**: Before the AI engine executes ANY tool call, the payload is piped through `raugus_hook.py`.
2. **AST Function-Level Verification**: The hook extracts AST symbol ranges from the incoming edit to determine which specific functions are targeted.
3. **Symbol Write Locks**: If a target function (e.g., `reload_system`) possesses an active write lock or exceeds the caller's RBAC tier, the hook terminates the tool call before disk access occurs.
4. **Immediate SIEM Dispatch**: The blocked attempt is logged to the SIEM and Master Alert Queue as a `SECURITY_AUDIT` intrusion attempt.

---

## 4. Why Order Matters in Tool Interception
1. **Intercept Before OS Execution**: Inspecting payloads *before* execution prevents unauthorized disk mutations from ever touching the storage controller.
2. **Parse AST Before Applying Diff**: Verifying that the proposed replacement code forms valid Python syntax prevents agents from writing broken syntax trees into live code.
3. **Log Intrusion Alert Before Returning Denial**: Writing to the SIEM log before returning `{"decision": "deny"}` guarantees the audit trail is recorded even if the subagent crashes upon refusal.

---

## 5. Beginner Coder Q&A
**Q: What is a PreToolUse hook?**  
A: A protective middleware script that runs automatically every time an AI agent attempts to use a tool, giving administrators the power to inspect, approve, or deny the action.

**Q: What does the hook return when it blocks an action?**  
A: It outputs a clean JSON response: `{"decision": "deny", "reason": "Access Denied: Symbol 'reload_system' is write-locked."}`.

**Q: Can the AI agent disable the hook?**  
A: No! The hook is registered at the engine level in `.agents/hooks.json` (`TIER_CORE_ENGINE`), which agents are strictly forbidden from modifying.
