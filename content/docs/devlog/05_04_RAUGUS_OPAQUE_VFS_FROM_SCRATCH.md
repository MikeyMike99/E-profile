# Pillar 05.4: From-Scratch Creation Guide: Raugus Opaque VFS Resolver

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH)
- **Next From-Scratch Guide**: [`05_05_ZERO_DOWNTIME_HOT_PATCH_RUNNER_FROM_SCRATCH.md`](/docs/devlog/05_05_ZERO_DOWNTIME_HOT_PATCH_RUNNER_FROM_SCRATCH)

---

## Overview

This guide walks you through building an **Opaque Key Resolver** (`raugus_resolver.py`) from a blank editor window.

The Resolver acts as a gatekeeper that allows AI agents to inspect and modify specific Python functions and classes via abstract keys (e.g., `app.core::login`) while completely hiding physical filesystem paths.

---

## Step-by-Step Implementation

### Step 1: Open a Blank Python File
```bash
nano raugus_resolver.py
```

### Step 2: Implement Key Registry & AST Scanner (Lines 1–35)
```python
import ast
import json
import os

class RaugusResolver:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.realpath(workspace_root)
        self.key_map = {}

    def index_python_file(self, rel_path: str, module_key: str, required_tier: int = 1):
        """Scans a Python file using AST and registers functions as opaque keys."""
        full_path = os.path.join(self.workspace_root, rel_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Register Module Key
        self.key_map[module_key] = {
            "type": "module",
            "rel_path": rel_path,
            "tier": required_tier,
            "symbols": {}
        }

        # Parse AST to find functions and line numbers
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol_key = f"{module_key}::{node.name}"
                self.key_map[symbol_key] = {
                    "type": "function",
                    "rel_path": rel_path,
                    "tier": required_tier,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno
                }
```

### Step 3: Implement `read_by_key` with Tier Gating (Lines 36–55)
```python
    def read_by_key(self, key: str, user_tier: int = 1) -> str:
        """Reads code by opaque key. Physical path is never exposed."""
        if key not in self.key_map:
            raise KeyError(f"Key not found in Raugus Map: {key}")

        entry = self.key_map[key]
        # 1. Enforce RBAC Tier Clearance
        if user_tier < entry["tier"]:
            raise PermissionError(f"Access denied: Requires Tier {entry['tier']}")

        full_path = os.path.join(self.workspace_root, entry["rel_path"])
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if entry["type"] == "module":
            return "".join(lines)

        # Slice exact function coordinates
        start = entry["start_line"] - 1
        end = entry["end_line"]
        return "".join(lines[start:end])
```

---

## Why Order Matters in Opaque VFS Engines

1. **Verify Key Existence Before Opening File Descriptors**:
   - Checking `key in self.key_map` must occur *before* attempting file I/O. If an attacker inputs `../../etc/passwd`, the resolver throws `KeyError` immediately without touching the filesystem.
2. **AST Parsing Before Line Slicing**:
   - `node.lineno` and `node.end_lineno` must be populated by Python's native AST parser. Counting lines using regex strings produces inaccurate coordinates if comments or docstrings span multiple lines.

---

## Verification & Testing

Verify that your resolver indexes functions and protects against unauthorized access:

```bash
python3 -c "
from raugus_resolver import RaugusResolver
import os

# Create dummy script
os.makedirs('/tmp/vfs_test', exist_ok=True)
with open('/tmp/vfs_test/demo.py', 'w') as f:
    f.write('def secret_func():\n    return 42\n')

resolver = RaugusResolver('/tmp/vfs_test')
resolver.index_python_file('demo.py', 'app.demo', required_tier=5)

# Test 1: Unauthorized access (Tier 1 user)
try:
    resolver.read_by_key('app.demo::secret_func', user_tier=1)
    print('[FAIL] Unauthorized read succeeded!')
except PermissionError:
    print('[PASS] Tier 1 blocked from Tier 5 key.')

# Test 2: Authorized access (Tier 5 Admin)
code = resolver.read_by_key('app.demo::secret_func', user_tier=5)
print('[PASS] Admin Read Success:\n', code.strip())
"
```

**Expected Output**:
```text
[PASS] Tier 1 blocked from Tier 5 key.
[PASS] Admin Read Success:
 def secret_func():
    return 42
```

---

## Beginner Coder Q&A

### Q: Why is `start_line - 1` used when slicing lines?
**A:** Python's AST line numbers are 1-indexed (the first line is line 1). Python lists are 0-indexed (the first element is index 0). Subtracting 1 aligns the coordinates accurately.

### Q: Does this prevent hackers from seeing where files live on the server?
**A:** Yes! The client only ever sends and receives the string `"app.demo::secret_func"`. The actual Linux directory path remains hidden on the server.
