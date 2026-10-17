[//]: # (DOC_ID: SIRA-DOC-02_14 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 02_14: Tool Security Audit & 31-Check Evidence

Primary source evidence from the Siraugga security core demonstrating how the automated **31-Check Tool Security Audit** verifies RBAC tier boundaries, PreToolUse hook interceptions, AST code hygiene, and DLP canary sanitization across the agentic runtime.

---

## Source Citation 1: Synthetic Hook Simulation (`security/tool_security_auditor.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-1)

This excerpt displays how the audit harness tests PreToolUse hook boundaries by injecting synthetic payloads without side effects:

```python
# Location: <project_root>/security/tool_security_auditor.py
# Lines: 28-48

def simulate_hook(tool_name: str, args: dict) -> dict:
    """Pipes a synthetic PreToolUse payload to raugus_hook.py and returns its JSON decision."""
    payload = {
        "toolCall": {
            "name": f"default_api:{tool_name}",
            "args": args,
        }
    }
    res = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    out = res.stdout.strip()
    try:
        return json.loads(out.splitlines()[-1]) if out else {"decision": "error", "raw": res.stderr}
    except Exception:
        return {"decision": "error", "raw": out or res.stderr}
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-2)
- **Isolated Hook Interception**: By feeding structured JSON payloads into `raugus_hook.py` via `stdin`, the test harness safely evaluates whether the security hook permits, blocks, or modifies tool execution before any command touches the host OS.
- **Fast Boundary Verification**: The subprocess runs with a strict 30-second timeout and captures both `stdout` and `stderr` to detect unexpected thread hangs.

---

## Source Citation 2: Clean Workspace Purge Protocol (`security/tool_security_auditor.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-3)

This excerpt demonstrates the automated purging of synthetic canary records from SIEM logs following an audit:

```python
# Location: <project_root>/security/tool_security_auditor.py
# Lines: 50-71

def purge_audit_logs():
    """Removes synthetic audit canary records from SIEM and MAQ logs (Clean Workspace Protocol)."""
    synthetic_tokens = (
        AUDIT_MARKER,
        "audit_canary_secret.txt",
        "canary@secret.internal",
        "write_to_file:<project_root>/.agents/raugus_hook.py",
    )
    for log_path in (MASTER_LOG, ALERT_LOG):
        if not os.path.exists(log_path):
            continue
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            clean_lines = [l for l in lines if not any(t in l for t in synthetic_tokens)]
            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(clean_lines)
        except Exception:
            pass
```

### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-4)
- **Zero Evidence Pollution**: Synthetic attack tokens injected during continuous validation are pruned from production audit logs (`devcore_master.jsonl`, `master_alert_queue.jsonl`), preserving audit integrity.
- **Compliance with Global Rule 1**: Fulfills the Clean Workspace Protocol by ensuring test artifacts never pollute production data stores.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-5)

In automated security audits, check sequencing prevents false positives and test deadlocks:
1. **Audit Static AST Hygiene Before Running Code**: Inspecting source files with Python's `ast.parse()` must happen *before* executing tools to catch forbidden imports (`pickle`, `os.system`) without running them.
2. **Execute Stage 1 (Map & RBAC) Before Stage 2 (Hook Interception)**: The Raugus VFS Map defines permissions. Verifying map integrity first ensures hook interception tests reflect accurate permission policies.
3. **Execute Log Purge in Finally Block**: Purging canary records must occur at the conclusion of the audit run regardless of whether individual checks passed or failed.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-6)

### What are the 5 stages of the Tool Security Audit?
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-7)
- **Stage 1**: Raugus Map & RBAC Clearance.
- **Stage 2**: PreToolUse Hook Interception.
- **Stage 3**: AST Static Code Hygiene.
- **Stage 4**: DLP Canary Scrubbing & Privacy.
- **Stage 5**: SIEM and Alert Queue Logging.

### What is an AST (Abstract Syntax Tree) check?
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-8)
An AST check parses Python code into a tree of grammatical nodes without executing it. It allows the security engine to mathematically prove that a script does not call forbidden functions like `eval()` or `os.system()`.

### Why are canary tokens used in security audits?
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-9)
A canary token is a harmless synthetic string (like `canary@secret.internal`). The auditor injects it into data streams to verify that privacy filters (like Microsoft Presidio) catch and redact sensitive strings before they leak to the UI.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_14-SEC-10)
- To understand why automated validation is required, read [`01_PROBLEMS_ENCOUNTERED/01_19_CONTINUOUS_ADVERSARIAL_VALIDATION_AND_AGENTIC_REFUSAL_TRAPS.md`](/docs/devlog/01_19_CONTINUOUS_ADVERSARIAL_VALIDATION_AND_AGENTIC_REFUSAL_TRAPS).
- To view diagnostic scan logs covering all 31 checks, visit [`03_DIAGNOSTIC_TESTS/03_13_TOOL_SECURITY_AUDIT_31_STAGE_SCAN_LOGS.md`](/docs/devlog/03_13_TOOL_SECURITY_AUDIT_31_STAGE_SCAN_LOGS).
- To examine the full 31-stage architecture, follow [`04_SOLUTIONS_AND_ARCHITECTURE/04_13_THE_31_STAGE_TOOL_SECURITY_AUDIT_ARCHITECTURE.md`](/docs/devlog/04_13_THE_31_STAGE_TOOL_SECURITY_AUDIT_ARCHITECTURE).
