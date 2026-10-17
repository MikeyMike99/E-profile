[//]: # (DOC_ID: SIRA-DOC-02_30 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# PreToolUse Raugus Hook Source Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_30-SEC-1)
This document records source code evidence from `.agents/raugus_hook.py`. Registered as a pre-execution hook in `.agents/hooks.json`, it intercepts all AI tool calls (`write_to_file`, `replace_file_content`, `edit_lines`, `run_command`), validates RBAC tiers and function write locks, and logs violations to the SIEM.

---

## 2. AST Line Span Parser Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_30-SEC-2)
The hook parses incoming replacement code to determine the exact start and end line ranges of targeted functions:

```python
# .agents/raugus_hook.py: Lines 6-22
def get_ast_symbols(source_code):
    symbols = {}
    try:
        tree = ast.parse(source_code)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Record the start and end lines of the function
                symbols[node.name] = (node.lineno, getattr(node, 'end_lineno', node.lineno))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols[target.id] = (node.lineno, getattr(node, 'end_lineno', node.lineno))
    except SyntaxError:
        pass
    return symbols
```

---

## 3. SIEM & Swarm Intrusion Alert Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_30-SEC-3)
Blocked actions trigger immediate telemetry alerts across both SIEM and Swarm loggers:

```python
# .agents/raugus_hook.py: Lines 24-44
def log_violation(tool_name, target, reason):
    try:
        from security.central_logger import log_siem_event
        from security.swarm_telemetry import SwarmFlowLogger

        log_siem_event(
            level="ERROR",
            message=f"[SECURITY_AUDIT] Raugus PreToolUse Hook intercepted and denied action. Tool: {tool_name}, Target: {target}, Reason: {reason}",
            module_name="raugus_hook",
            logger_name="security.raugus_hook",
        )
        SwarmFlowLogger.log_intrusion_alert(
            modder_id="MainCloudBrain",
            agent_id="PreToolUse_Hook",
            target_namespace=f"{tool_name}:{target}",
            reason=reason,
        )
    except Exception:
        pass
```

---

## 4. Hook Interception & Decision Output Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_30-SEC-4)
The hook evaluates incoming stdin JSON and terminates unauthorized operations:

```python
# .agents/raugus_hook.py: Decision engine
payload = json.loads(sys.stdin.read())
tool_call = payload.get("toolCall", {})
tool_name = tool_call.get("name", "")
args = tool_call.get("args", {})

# Validate target against Raugus Map
target_file = args.get("TargetFile") or args.get("target_file")
if is_write_locked(target_file):
    log_violation(tool_name, target_file, "Function-level write lock engaged.")
    print(json.dumps({"decision": "deny", "reason": "Access Denied: File or symbol is write-locked."}))
    sys.exit(0)

# If verified, grant approval
print(json.dumps({"decision": "approve"}))
```

---

## 5. Why Order Matters in Tool Interception
[//]: # (SECTION_ID: SIRA-DOC-02_30-SEC-5)
1. **Read Stdin Completely Before Processing**: The hook must ingest the full tool payload before attempting JSON decoding to avoid partial-frame errors.
2. **Log Alert Before Emitting Denial**: Firing the SIEM event before printing `{"decision": "deny"}` guarantees the incident is recorded before the child process exits.
3. **Approve Explicitly on Clean Exit**: Returning a clean approval JSON ensures legitimate developer tool calls proceed without artificial latency.

---

## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_30-SEC-6)
**Q: How does the AI system know to run `raugus_hook.py`?**  
A: It is registered in `.agents/hooks.json` under `"PreToolUse"`, which instructs the Antigravity engine to pipe tool arguments through the script before execution.

**Q: What does `sys.exit(0)` do here?**  
A: A return code of 0 informs the engine that the hook completed successfully and the engine should read its JSON output to decide whether to allow or block the tool.

**Q: Can this hook inspect terminal shell commands?**  
A: Yes! When `run_command` is called, the hook inspects the `CommandLine` string for dangerous commands like `rm -rf`, `sudo`, or path escapes.
