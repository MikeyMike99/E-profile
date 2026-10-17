# PreToolUse Hook Interceptor from Scratch

## 1. Architectural Role & Module Overview
Securing web APIs is not enough when autonomous AI agents have native tools to edit files and run terminal commands. Without pre-execution interception, an agent can modify critical system files directly.

This guide details how to build `.agents/raugus_hook.py` from scratch. It acts as a PreToolUse middleware that intercepts tool calls from stdin, validates targets against the Raugus VFS map, enforces function-level write locks, blocks dangerous shell commands, and emits SIEM intrusion logs.

```
+-------------------------------------------------------------+
|                     Antigravity AI Engine                   |
|           Pipes tool call JSON into raugus_hook.py          |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 raugus_hook.py stdin Parser                 |
|   1. Reads payload: {"toolCall": {"name": ..., "args": ...}}|
|   2. If tool is 'run_command': Scans for dangerous commands |
|   3. If tool edits file: Checks Raugus Map write-locks      |
|   4. Returns: {"decision": "approve"} OR {"decision": "deny"}|
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
             ALLOW                         DENY
               |                             |
      Tool Executes Cleanly        1. Log SECURITY_AUDIT to SIEM
                                   2. Print Denial JSON
                                   3. Agent Halts Tool Operation
```

---

## 2. Complete Python Implementation
Save the following script as `tool_hook.py`:

```python
import sys
import json
import re

PROHIBITED_COMMANDS = [r"\brm\s+-rf\b", r"\bsudo\b", r"\bchmod\b", r"\bmkfs\b", r"\bchown\b"]
LOCKED_FUNCTIONS = {"reload_system", "get_current_user", "verify_master_signature"}

def log_siem_alert(tool_name: str, target: str, reason: str):
    """Simulates logging an intrusion event to the central SIEM."""
    print(f"[SIEM INTRUSION ALERT] Intercepted {tool_name} on {target}: {reason}", file=sys.stderr)

def evaluate_tool_call(tool_name: str, args: dict) -> tuple[bool, str]:
    # 1. Shell command safety
    if "run_command" in tool_name:
        cmd = args.get("CommandLine", "")
        for pat in PROHIBITED_COMMANDS:
            if re.search(pat, cmd):
                return False, f"Prohibited destructive command detected: '{cmd}'"

    # 2. File modification safety
    target_file = args.get("TargetFile") or args.get("target_file") or ""
    if target_file:
        # Prevent modifying core engine files directly
        if any(target_file.startswith(prefix) for prefix in ["core/", "security/", "agents/"]):
            return False, f"Access Denied: Cannot modify protected path '{target_file}' directly."

    # 3. Function-level write lock inspection
    target_content = args.get("TargetContent", "") or args.get("ReplacementContent", "")
    for locked_sym in LOCKED_FUNCTIONS:
        if f"def {locked_sym}" in target_content or f"async def {locked_sym}" in target_content:
            return False, f"Access Denied: Symbol '{locked_sym}' is write-locked."

    return True, "Operation approved."

def main():
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print(json.dumps({"decision": "approve"}))
            return

        payload = json.loads(raw_input)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})

        approved, reason = evaluate_tool_call(tool_name, args)
        if not approved:
            target = args.get("TargetFile") or args.get("CommandLine") or "unknown"
            log_siem_alert(tool_name, target, reason)
            print(json.dumps({"decision": "deny", "reason": reason}))
        else:
            print(json.dumps({"decision": "approve"}))

    except Exception as e:
        # In case of hook error, fail closed
        print(json.dumps({"decision": "deny", "reason": f"Hook error: {str(e)}"}))

if __name__ == "__main__":
    main()
```

---

## 3. Why Order Matters in Tool Hook Logic
1. **Check Shell Commands Before Inspecting Paths**: Evaluating `CommandLine` first prevents commands that combine arguments (like `rm -rf core/`) from slipping past path rules.
2. **Log Alert to Stderr Before Printing JSON**: Printing the SIEM alert to `sys.stderr` ensures standard output (`sys.stdout`) remains clean JSON for the calling AI framework.
3. **Fail-Closed on Parsing Errors**: If `json.loads()` fails, the hook must return `{"decision": "deny"}` rather than allowing uninspected tools to execute.

---

## 4. Beginner Coder Q&A
**Q: What does "fail-closed" mean?**  
A: A security principle where if an error occurs in the security checker, it defaults to blocking the action rather than accidentally letting it through.

**Q: Why print SIEM logs to `sys.stderr`?**  
A: The AI agent framework reads `sys.stdout` to get the JSON decision. Printing debug logs to `sys.stdout` would break JSON parsing.

**Q: Where does this file live in production?**  
A: In `.agents/raugus_hook.py`, registered inside `.agents/hooks.json` under `"PreToolUse"`.
