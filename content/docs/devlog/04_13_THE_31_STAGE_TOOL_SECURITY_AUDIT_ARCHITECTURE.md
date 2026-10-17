[//]: # (DOC_ID: SIRA-DOC-04_13 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 04_13: The 31-Stage Tool Security Audit Architecture

An architectural blueprint of Siraugga's **Continuous Tool Security Audit Engine**—the automated 5-stage, 31-check verification pipeline that validates RBAC boundaries, PreToolUse hooks, AST code hygiene, and DLP canary sanitization.

---

## Architectural Overview & Topology
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-1)

In autonomous agent systems where LLMs generate code, execute terminal commands, and call custom tools, security cannot rely on manual code review. Every tool, plugin, and staged patch must pass through an automated verification gauntlet.

```
┌─────────────────────────────────────────────────────────────┐
│           STAGE 1: RAUGUS MAP & RBAC CLEARANCE              │
│  • Sensitive vault flags verified                           │
│  • Tier 3 Dev blocked from Tier 5 Core Engine               │
│  • Path normalization & symlink traversal blocked           │
└──────────────────────────────┬──────────────────────────────┘
                               │ PASS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           STAGE 2: PRETOOLUSE HOOK INTERCEPTION             │
│  • Synthetic JSON payloads piped via stdin                  │
│  • Command injection & sensitive path reads blocked         │
│  • Non-blocking 403 error feedback generated                │
└──────────────────────────────┬──────────────────────────────┘
                               │ PASS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           STAGE 3: AST STATIC CODE HYGIENE                  │
│  • Abstract Syntax Tree scan: Zero eval() or exec()         │
│  • Zero forbidden imports (pickle, os.system)               │
│  • Function write-locks & decorator integrity verified      │
└──────────────────────────────┬──────────────────────────────┘
                               │ PASS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           STAGE 4: DLP CANARY SCRUBBING & PRIVACY           │
│  • Synthetic canary injection (__RAUGUS_AUDIT_CANARY__)     │
│  • Microsoft Presidio PII redaction (email/phone)           │
│  • Egress firewall prevents prompt rule leakage             │
└──────────────────────────────┬──────────────────────────────┘
                               │ PASS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           STAGE 5: SIEM & ALERT QUEUE LOGGING               │
│  • High-priority threat logged to MAQ queue                 │
│  • Monotonic sequence IDs & ISO-8601 UTC timestamps         │
│  • Clean Workspace Purge: Synthetic tokens erased from disk │
└─────────────────────────────────────────────────────────────┘
```

---

## The 5 Audit Stages Explained
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-2)

1. **Stage 1 (RBAC & Path Security)**:
   - Validates that `RaugusResolver.enforce_path_security()` rejects any Tier 3 developer attempting to read or write Tier 5 server code (`server.py`).
2. **Stage 2 (Hook Interception)**:
   - Uses `simulate_hook()` to feed synthetic tool calls directly into `raugus_hook.py`, proving that malicious calls are caught before execution.
3. **Stage 3 (AST Static Hygiene)**:
   - Compiles Python files into abstract syntax trees without running them, proving mathematically that no dangerous functions exist.
4. **Stage 4 (DLP & Canary Scrubbing)**:
   - Injects fake credit card numbers, email addresses, and secret canaries to prove privacy filters redact sensitive tokens in real time.
5. **Stage 5 (SIEM Logging & Clean Room Purge)**:
   - Confirms that blocked threats generate alerts in `master_alert_queue.jsonl`, then deletes test canaries so production logs remain clean.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-3)

In multi-stage security validation, order prevents false positives:
1. **Verify Static AST Before Dynamic Execution**: Checking AST code hygiene first prevents malicious code from executing during subsequent dynamic stages.
2. **Execute Hook Interception Before Egress Redaction**: Proving that the gateway blocks unauthorized access precedes testing whether privacy filters redact leaked text.
3. **Execute Canary Purge in Finally Block**: The log cleanup routine MUST execute in a `finally` block to ensure test tokens are deleted even if an assertion fails mid-audit.

---

## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-4)

To run the complete 31-stage security audit before deploying any code update:

```bash
# Step 1: Run the automated audit harness
python3 security/tool_security_auditor.py --filter all

# Step 2: Verify zero exit code before hot-patching
if [ $? -eq 0 ]; then
    echo "Security audit passed! Triggering safe hot-patch..."
    curl -s -X POST http://127.0.0.1:5000/api/simulate-patch
else
    echo "SECURITY AUDIT FAILED! Deployment halted."
    exit 1
fi
```

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-5)

### Why does the audit check both AST and runtime hooks?
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-6)
AST checks find bad code that is written in files. Runtime hooks catch bad inputs that are sent dynamically while the program is running. Together, they provide Defense in Depth.

### What is the "Clean Workspace Purge"?
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-7)
During Stage 4 and 5, fake secret tokens are logged. The purge routine scans the log files and erases only the test tokens, leaving real security alerts intact.

### How fast is this audit?
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-8)
The entire 31-check audit runs in approximately 1.4 seconds. Because it is so fast, Siraugga runs it automatically every time a developer stages an update.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_13-SEC-9)
- To understand why automated validation is necessary, read [`01_PROBLEMS_ENCOUNTERED/01_19_CONTINUOUS_ADVERSARIAL_VALIDATION_AND_AGENTIC_REFUSAL_TRAPS.md`](/docs/devlog/01_19_CONTINUOUS_ADVERSARIAL_VALIDATION_AND_AGENTIC_REFUSAL_TRAPS).
- To inspect the primary source code of the auditor, view [`02_SOURCE_EVIDENCE/02_14_TOOL_SECURITY_AUDIT_31_CHECK_EVIDENCE.md`](/docs/devlog/02_14_TOOL_SECURITY_AUDIT_31_CHECK_EVIDENCE).
- To view diagnostic scan logs covering all 31 checks, visit [`03_DIAGNOSTIC_TESTS/03_13_TOOL_SECURITY_AUDIT_31_STAGE_SCAN_LOGS.md`](/docs/devlog/03_13_TOOL_SECURITY_AUDIT_31_STAGE_SCAN_LOGS).
