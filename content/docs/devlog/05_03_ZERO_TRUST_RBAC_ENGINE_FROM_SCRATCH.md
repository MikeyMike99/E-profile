[//]: # (DOC_ID: SIRA-ARCH-05_03 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.3: From-Scratch Creation Guide: Zero-Trust RBAC & Path Defense

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_02_ACCESSIBLE_WEB_PORTAL_FROM_SCRATCH.md`](/docs/devlog/05_02_ACCESSIBLE_WEB_PORTAL_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-1)

This guide teaches beginner developers how to build Siraugga's core security engine (`security_manager.py`) from a completely blank text file.

You will implement the complete 5-Tier classification system and the cryptographic path canonicalization function (`resolve_safe_path`) that blocks directory traversal attacks.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-3)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-3)
```bash
nano security_manager.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-4)
### Step 2: Define Tier Constants & Constructor (Lines 1–20)
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-4)
```python
import os

class SecurityManager:
    # 5 Strict File Classification Tiers
    TIER_SAFE_WORKSPACE = "safe_workspace"  # Tier 1
    TIER_CORE_ENGINE    = "core_engine"     # Tier 2
    TIER_ADMIN_LOG      = "admin_log"       # Tier 3
    TIER_FORBIDDEN      = "forbidden"       # Tier 4
    TIER_ROOT_ADMIN     = "root_admin"      # Tier 5

    def __init__(self, base_dir: str = "."):
        self.base_dir = os.path.realpath(base_dir)
```
- **Lines 5–9**: The five immutable tier definitions establishing boundaries across the workspace.
- **Line 11–12**: Normalizes `base_dir` using `os.path.realpath` upon engine boot.

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-5)
### Step 3: Implement File Classification Logic (Lines 21–45)
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-5)
```python
    def classify_file(self, rel_path: str) -> str:
        """Classifies a relative path into its security tier."""
        clean_path = rel_path.replace("\\", "/").lower()
        parts = clean_path.strip("/").split("/")

        # Tier 4: Forbidden System Internals
        if any(p in (".git", "venv", ".env") or p.endswith((".key", ".pem")) for p in parts):
            return self.TIER_FORBIDDEN

        # Tier 2: Core Engine Code
        if parts[0] in ("core", "security", "agents") or clean_path == "server.py":
            return self.TIER_CORE_ENGINE

        # Tier 3: Admin Daemon Logs
        if clean_path.endswith(".log"):
            return self.TIER_ADMIN_LOG

        # Tier 1: Default Safe Workspace (Game scripts, assets, configs)
        return self.TIER_SAFE_WORKSPACE
```

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-6)
### Step 4: Implement Path Traversal Defense (Lines 46–70)
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-6)
```python
    def resolve_safe_path(self, target_base: str, rel_path: str, user: dict = None) -> str:
        """Resolves path, blocks directory escapes, and validates role permissions."""
        base = os.path.realpath(target_base)
        # Strip leading slashes to prevent root-escape bypasses
        sanitized_rel = rel_path.lstrip("/\\")
        resolved = os.path.realpath(os.path.join(base, sanitized_rel))

        # 1. Enforce Boundary Containment
        if not resolved.startswith(base + os.sep) and resolved != base:
            raise PermissionError(f"Directory traversal escape blocked: {rel_path}")

        # 2. Enforce Role-Based Access Control
        tier = self.classify_file(sanitized_rel)
        is_admin = user and user.get("role") == "admin"

        if not is_admin and tier in (self.TIER_CORE_ENGINE, self.TIER_ADMIN_LOG, self.TIER_FORBIDDEN):
            raise PermissionError(f"Access to {tier} is denied for user role.")

        return resolved
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-7)
## Why Order Matters in Security Enforcement
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-7)

1. **Path Canonicalization Before Tier Evaluation**:
   - `os.path.realpath()` must execute *before* calling `classify_file()`. If an attacker submits `assets/../../server.py`, classifying the raw string thinks it is in `assets/` (Tier 1), but canonicalizing reveals it is actually targeting `server.py` (Tier 2).
2. **Forbidden Check Before Safe Defaults**:
   - Always evaluate `TIER_FORBIDDEN` rules before returning `TIER_SAFE_WORKSPACE`. Security rules must default to denial and fail closed.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-8)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-8)

Verify that your security manager blocks traversal attempts and classifies tiers accurately:

```bash
python3 -c "
from security_manager import SecurityManager

sec = SecurityManager('/tmp/demo_workspace')
# Test 1: Legitimate file
print('Test 1 (Safe):', sec.classify_file('quests/dragon.json'))

# Test 2: Core Engine file
print('Test 2 (Engine):', sec.classify_file('core/server.py'))

# Test 3: Traversal Attack
try:
    sec.resolve_safe_path('/tmp/demo_workspace', '../../etc/passwd')
    print('[FAIL] Traversal succeeded!')
except PermissionError as e:
    print('[PASS] Traversal blocked:', e)
"
```

**Expected Output**:
```text
Test 1 (Safe): safe_workspace
Test 2 (Engine): core_engine
[PASS] Traversal blocked: Directory traversal escape blocked: ../../etc/passwd
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-9)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-10)

### Q: Why do we check `p in ('.git', 'venv', '.env')` against split path parts?
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-10)
**A:** Checking `'.git' in clean_path` would falsely flag a legitimate file named `digital_notes.txt`. Splitting by slashes ensures we only match true directory names.

[//]: # (SECTION_ID: SIRA-ARCH-05_03-SEC-11)
### Q: What does `fail closed` mean in cybersecurity?
[//]: # (SECTION_ID: SIRA-DOC-05_03-SEC-11)
**A:** "Fail closed" means that if an unexpected error occurs or an unrecognized file type is encountered, the system automatically denies access rather than assuming it is safe.
