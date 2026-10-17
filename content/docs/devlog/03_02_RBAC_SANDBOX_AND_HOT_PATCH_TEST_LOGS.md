# Pillar 03.2: Diagnostic Tests: RBAC Sandbox & Hot-Patch Logs

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Diagnostic Chapter**: [`03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS.md`](/docs/devlog/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS)
- **Next: Solutions & Architecture**: [`../04_SOLUTIONS_AND_ARCHITECTURE/04_01_SIRAUGGA_CORE_SYSTEM_ARCHITECTURE.md`](/docs/devlog/04_01_SIRAUGGA_CORE_SYSTEM_ARCHITECTURE)

---

## Overview

This chapter records the empirical penetration and resilience tests conducted against Siraugga's Zero-Trust access control and Zero-Downtime Hot-Patch mechanisms.

---

## Test 1: Path Traversal Penetration Test

### What We Tested
We attempted to force the file reading route (`/api/files/read`) to escape the assigned workspace directory and access root server files using relative traversal sequences (`../../core/server.py`).

### Exact Command Run
```bash
curl -s -X POST http://127.0.0.1:5000/api/files/read \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <dev_jwt_token>" \
  -d '{"path": "../../core/server.py"}'
```

### Exact Output Returned
```json
{
  "error": "Directory traversal escape blocked: ../../core/server.py",
  "status": 403,
  "tier": "forbidden"
}
```

### How We Reached Our Conclusion
`security_manager.resolve_safe_path()` intercepted the path string, canonicalized it via `os.path.realpath()`, identified that the resolved target lay outside the caller's project root, and aborted execution with an HTTP 403 before any file descriptor was allocated.

---

## Test 2: Hot-Patch Syntax Failure & Automated Rollback

### What We Tested
We staged an intentionally broken Python patch containing invalid syntax into `core/patches/` and triggered the hot-patching sequence to verify that broken code never replaces the live server module.

### Exact Staged Content (`core/patches/test_route.py`)
```python
# Deliberately broken syntax to test pre-flight compilation
def broken_route(
    return "This should never compile"
```

### Exact Command Run
```bash
curl -s -X POST http://127.0.0.1:5000/api/simulate-patch
```

### Exact Log Output Returned
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

### How We Reached Our Conclusion
The pre-flight `py_compile.compile(..., doraise=True)` caught the syntax error before copying files into `core/`. Active WebSocket connections remained active and undisturbed.

---

## Why Order Matters in Security & Patch Testing

1. **Verify Boundary Defense Before Role Defense**:
   - Always test path containment (`os.path.commonpath`) before evaluating user tier permissions. If an attacker can escape the directory structure, tier checks can be bypassed by spoofed paths.
2. **Pre-Compile in Staging Before Backup Overwrite**:
   - Compiling the staged file must happen *before* taking a new backup snapshot. If you snapshot while compiling broken code, your backup could be overwritten with bad state.

---

## Beginner Coder Q&A

### Q: What is a Bearer token?
**A:** A Bearer token is a secure cryptographic string passed in the HTTP Authorization header that proves the user has logged in and holds specific permissions (like `admin`, `dev`, or `mod`).

### Q: Why is Port 5000 never killed during code updates?
**A:** Killing Port 5000 terminates all browser WebSockets, cancels active background AI tasks, and can lead to port-binding conflicts ("Address already in use"). In-memory hot-patching updates code without dropping the networking port.
