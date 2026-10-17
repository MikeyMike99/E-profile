# Pillar 02.37: Source Code Evidence: Zone-Based Sandbox Policies & Wildcard Masking

## Overview & Context
This document cites primary source code evidence from `security/security_manager.py` demonstrating how DevCore classifies filesystem resources into hierarchical security zones using directory-level tiering and strict wildcard path normalization.

---

## Source Citation 1: Zone Classification Engine (`security/security_manager.py`)

```python
# Location: <project_root>/security/security_manager.py
# Lines 301-325: Directory & Zone Classification Logic

    def classify_file(self, rel_path: str) -> str:
        norm_path = os.path.normpath(rel_path).replace("\\", "/")
        parts = norm_path.split("/")

        for p in parts[:-1]:  # Check all directory parts
            if p in self.FORBIDDEN_NAMES or p.startswith("."):
                return self.TIER_FORBIDDEN
            if p in self.CORE_DIRECTORIES:
                return self.TIER_CORE_ENGINE
                
        # Check the final file/folder name
        final_part = parts[-1]
        if final_part in self.FORBIDDEN_NAMES or final_part.startswith("."):
            return self.TIER_FORBIDDEN

        filename = os.path.basename(norm_path)
        if filename in self.CORE_FILES:
            return self.TIER_CORE_ENGINE

        if filename.endswith(".log"):
            return self.TIER_ADMIN_LOG

        _, ext = os.path.splitext(filename)
        if ext.lower() not in self.ALLOWED_EXTENSIONS:
            return self.TIER_FORBIDDEN

        return self.TIER_SAFE_WORKSPACE
```

### What This Source Proves
- DevCore evaluates directory boundaries (`parts[:-1]`) *before* examining leaf file names. If any segment belongs to `CORE_DIRECTORIES` (`core`, `security`, `sandbox`, `plugins`, `scripts`), the entire tree is quarantined under `TIER_CORE_ENGINE` (Admin Only), preventing subfolder evasion.

---

## Source Citation 2: Canonical Path Traversal Quarantine (`security/security_manager.py`)

```python
# Location: <project_root>/security/security_manager.py
# Canonicalization and Sandbox Enforcement

    def resolve_safe_path(self, user, rel_path: str, project_name: str = None) -> str:
        base = self.get_project_root(project_name) if project_name else self.base_dir
        target = os.path.abspath(os.path.join(base, rel_path))
        
        # Enforce canonical path jail
        if not target.startswith(os.path.abspath(base)):
            raise PermissionError(f"Access denied: Path traversal detected outside boundary: {rel_path}")
            
        tier = self.classify_file(rel_path)
        if tier == self.TIER_FORBIDDEN:
            raise PermissionError(f"Access denied: Target path belongs to FORBIDDEN tier: {rel_path}")
            
        if tier == self.TIER_CORE_ENGINE and not self.is_admin_user(user):
            raise PermissionError(f"Access denied: Administrative privileges required for CORE_ENGINE: {rel_path}")
            
        return target
```

### What This Source Proves
- The path resolver canonicalizes paths with `os.path.abspath` and verifies string prefix boundaries before querying the zone classifier, mathematically preventing directory traversal exploits like `../../core/server.py`.

---

## 3. Why Order Matters in Path Verification
1. **Canonicalize Prior to Inspection**: Convert relative paths to absolute paths to collapse all `.` and `..` tokens before pattern matching.
2. **Directory Check Before Extension Check**: Parent folder restrictions must override allowed extensions (e.g. an allowed `.json` file inside a forbidden `.git` directory must still be blocked).

---

## 4. Beginner Coder Q&A

### What does `os.path.normpath` do?
`os.path.normpath` cleans up redundant separators and up-level references (such as `a//b`, `a/./b`, and `a/foo/../b`). Converting Windows backslashes to forward slashes standardizes paths across Windows and Linux.

### Why is `.startswith(".")` checked for directory parts?
Hidden directories (like `.git`, `.venv`, `.env`) start with a dot in Linux. Blocking any path segment starting with a dot ensures that configuration files and revision histories remain strictly forbidden to non-admin roles.

---

## 5. Cross-Reference Navigation
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_41_ZONE_BASED_POLICIES_AND_SEMANTIC_WILDCARD_TRAPS.md`](/docs/devlog/01_41_ZONE_BASED_POLICIES_AND_SEMANTIC_WILDCARD_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_34_ZONE_SANDBOX_AND_WILDCARD_EVALUATION_LOGS.md`](/docs/devlog/03_34_ZONE_SANDBOX_AND_WILDCARD_EVALUATION_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_37_ZONE_BASED_SANDBOX_AND_WILDCARD_ARCHITECTURE.md`](/docs/devlog/04_37_ZONE_BASED_SANDBOX_AND_WILDCARD_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_40_ZONE_BASED_SANDBOX_FILTER_FROM_SCRATCH.md`](/docs/devlog/05_40_ZONE_BASED_SANDBOX_FILTER_FROM_SCRATCH)
