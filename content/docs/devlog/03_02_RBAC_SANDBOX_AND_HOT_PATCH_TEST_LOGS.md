[//]: # (DOC_ID: SIRA-DEV-03_02 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 03.2: Diagnostic Tests: RBAC Sandbox & Hot-Patch Logs

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Diagnostic Chapter**: [`03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS.md`](/docs/devlog/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS)
- **Next: Solutions & Architecture**: [`../04_SOLUTIONS_AND_ARCHITECTURE/04_01_SIRAUGGA_CORE_SYSTEM_ARCHITECTURE.md`](/docs/devlog/04_01_SIRAUGGA_CORE_SYSTEM_ARCHITECTURE)

---

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-1)

This chapter records the empirical penetration and resilience tests conducted against Siraugga's Zero-Trust access control and Zero-Downtime Hot-Patch mechanisms.

---

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-2)
## Test 1: Path Traversal Penetration Test
[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-3)

### What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-3)
We attempted to force the file reading route (`/api/files/read`) to escape the assigned workspace directory and access root server files using relative traversal sequences (`../../core/server.py`).

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-4)
### Exact Command Run
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-4)
```bash
curl -s -X POST http://127.0.0.1:5000/api/files/read \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <dev_jwt_token>" \
  -d '{"path": "../../core/server.py"}'
```

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-5)
### Exact Output Returned
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-5)
```json
{
  "error": "Directory traversal escape blocked: ../../core/server.py",
  "status": 403,
  "tier": "forbidden"
}
```

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-6)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-6)
`security_manager.resolve_safe_path()` intercepted the path string, canonicalized it via `os.path.realpath()`, identified that the resolved target lay outside the caller's project root, and aborted execution with an HTTP 403 before any file descriptor was allocated.

---

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-7)
## Test 2: Hot-Patch Syntax Failure & Automated Rollback
[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-8)

### What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-8)
We staged an intentionally broken Python patch containing invalid syntax into `core/patches/` and triggered the hot-patching sequence to verify that broken code never replaces the live server module.

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-9)
### Exact Staged Content (`core/patches/test_route.py`)
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-9)
```python
# Deliberately broken syntax to test pre-flight compilation
def broken_route(
    return "This should never compile"
```

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-10)
### Exact Command Run
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-10)
```bash
curl -s -X POST http://127.0.0.1:5000/api/simulate-patch
```

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-11)
### Exact Log Output Returned
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-11)
```text
[HOT-PATCH] Inspecting staged files in core/patches/...
[HOT-PATCH] Pre-compiling core/patches/test_route.py...
[ERROR] Syntax error detected during pre-compilation:
  File "core/patches/test_route.py", line 2
    def broken_route(
                    ^
SyntaxError: invalid syntax
[HOT-PATCH] Staging aborted. Live module core/routes/test_route.py untouched.
[HOT-PATCH] Automated Rollback verified. Server process 100% stable on Port 5000.
```

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-12)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-12)
The pre-flight `py_compile.compile(..., doraise=True)` caught the syntax error before copying files into `core/`. Active WebSocket connections remained active and undisturbed.

---

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-13)
## Why Order Matters in Security & Patch Testing
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-13)

1. **Verify Boundary Defense Before Role Defense**:
   - Always test path containment (`os.path.commonpath`) before evaluating user tier permissions. If an attacker can escape the directory structure, tier checks can be bypassed by spoofed paths.
2. **Pre-Compile in Staging Before Backup Overwrite**:
   - Compiling the staged file must happen *before* taking a new backup snapshot. If you snapshot while compiling broken code, your backup could be overwritten with bad state.

---

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-14)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-15)

### Q: What is a Bearer token?
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-15)
**A:** A Bearer token is a secure cryptographic string passed in the HTTP Authorization header that proves the user has logged in and holds specific permissions (like `admin`, `dev`, or `mod`).

[//]: # (SECTION_ID: SIRA-DEV-03_02-SEC-16)
### Q: Why is Port 5000 never killed during code updates?
[//]: # (SECTION_ID: SIRA-DOC-03_02-SEC-16)
**A:** Killing Port 5000 terminates all browser WebSockets, cancels active background AI tasks, and can lead to port-binding conflicts ("Address already in use"). In-memory hot-patching updates code without dropping the networking port.
