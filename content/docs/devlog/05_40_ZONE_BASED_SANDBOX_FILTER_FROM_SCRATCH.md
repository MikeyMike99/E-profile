[//]: # (DOC_ID: SIRA-DOC-05_40 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 05.40: From-Scratch Creation Guide: Zone-Based Sandbox & Wildcard Path Filter

## Overview & Beginner Context
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-1)
This guide teaches you how to write a Zone-Based Sandbox Path Filter in Python from scratch. It categorizes files into security tiers and stops directory traversal attacks (`../../`) using canonical path resolution.

---

## 1. Line-by-Line Construction
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-1)

### Block 1: Zone Classification Constants (Lines 1–20)
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-2)
```python
import os

TIER_SAFE_WORKSPACE = "safe_workspace"
TIER_CORE_ENGINE = "core_engine"
TIER_ADMIN_LOG = "admin_log"
TIER_FORBIDDEN = "forbidden"

CORE_DIRS = {"core", "security", "sandbox", "plugins", "scripts"}
FORBIDDEN_NAMES = {"venv", "__pycache__", ".git", ".env"}
ALLOWED_EXTS = {".py", ".json", ".lua", ".js", ".ts", ".md", ".txt", ".html", ".css"}
```
- Sets strict constants defining zones, forbidden folders, and allowed file extensions.

### Block 2: The Zone Classifier Function (Lines 21–45)
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-3)
```python
def classify_path(rel_path: str) -> str:
    """Classifies a relative path into a security tier."""
    clean = os.path.normpath(rel_path).replace("\\", "/")
    segments = clean.split("/")

    # Check parent directory segments
    for seg in segments[:-1]:
        if seg in FORBIDDEN_NAMES or seg.startswith("."):
            return TIER_FORBIDDEN
        if seg in CORE_DIRS:
            return TIER_CORE_ENGINE

    # Check target file name
    leaf = segments[-1]
    if leaf in FORBIDDEN_NAMES or leaf.startswith("."):
        return TIER_FORBIDDEN
    if leaf.endswith(".log"):
        return TIER_ADMIN_LOG

    _, ext = os.path.splitext(leaf)
    if ext.lower() not in ALLOWED_EXTS:
        return TIER_FORBIDDEN

    return TIER_SAFE_WORKSPACE
```
- Inspects every folder in the path to stop subfolder evasion attacks.

### Block 3: The Canonical Jail Resolver (Lines 46–65)
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-4)
```python
def resolve_safe_path(base_dir: str, rel_path: str, is_admin: bool = False) -> str:
    """Resolves path and enforces sandbox boundary."""
    abs_base = os.path.abspath(base_dir)
    target = os.path.abspath(os.path.join(abs_base, rel_path))

    # Boundary Jail
    if not target.startswith(abs_base):
        raise PermissionError(f"Path traversal detected: {rel_path}")

    tier = classify_path(rel_path)
    if tier == TIER_FORBIDDEN:
        raise PermissionError(f"Access to FORBIDDEN tier blocked: {rel_path}")
    if tier == TIER_CORE_ENGINE and not is_admin:
        raise PermissionError(f"Admin privileges required for CORE_ENGINE: {rel_path}")

    return target
```
- Ensures the path cannot escape `base_dir` using `os.path.abspath` prefix validation.

---

## 2. 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-2)
1. Query `../.env` -> Raises `PermissionError` (Path traversal).
2. Query `core/server.py` as non-admin -> Raises `PermissionError` (Admin required).
3. Query `game/player.lua` as dev -> Returns absolute path (Allowed).

---

## 3. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-3)

### What is the difference between `os.path.abspath` and `os.path.realpath`?
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-5)
`os.path.abspath` calculates the absolute path without resolving symbolic links. `os.path.realpath` resolves all symlinks, ensuring that an attacker cannot use a symlink to trick the system.

---

## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-05_40-SEC-4)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_41_ZONE_BASED_POLICIES_AND_SEMANTIC_WILDCARD_TRAPS.md`](/docs/devlog/01_41_ZONE_BASED_POLICIES_AND_SEMANTIC_WILDCARD_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_37_ZONE_BASED_SANDBOX_POLICY_EVIDENCE.md`](/docs/devlog/02_37_ZONE_BASED_SANDBOX_POLICY_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_34_ZONE_SANDBOX_AND_WILDCARD_EVALUATION_LOGS.md`](/docs/devlog/03_34_ZONE_SANDBOX_AND_WILDCARD_EVALUATION_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_37_ZONE_BASED_SANDBOX_AND_WILDCARD_ARCHITECTURE.md`](/docs/devlog/04_37_ZONE_BASED_SANDBOX_AND_WILDCARD_ARCHITECTURE)
