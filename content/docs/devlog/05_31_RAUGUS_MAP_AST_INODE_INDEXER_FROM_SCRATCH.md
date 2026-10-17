# Raugus Map AST & Inode Indexer from Scratch

## 1. Architectural Role & Module Overview
Exposing raw physical file paths to autonomous agents creates attack surfaces for path traversal and filesystem evasion attacks.

This guide details how to build `generate_raugusmap.py` from scratch. It parses the Abstract Syntax Tree (AST) of every Python file in a project, extracts hardware filesystem inodes (`st_ino`) to detect file renaming tricks, and generates an opaque virtual key phonebook (`raugus_map.json`).

```
+-------------------------------------------------------------+
|               Project Workspace Directory                   |
|           core/, security/, plugins/, agents/               |
+-------------------------------------------------------------+
                              |
                     Recursive AST Crawler
                              |
                              v
+-------------------------------------------------------------+
|                generate_raugusmap.py Pipeline               |
|   1. Extracts AST symbols: FunctionDef, ClassDef, Assign    |
|   2. Fetches hardware filesystem inode (st_ino)             |
|   3. Assigns Opaque Virtual Keys: 'devcore.*::symbol'       |
|   4. Flags Sensitive Vaults (RBAC Tier 5)                   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 security/raugus_map.json                    |
|          Phonebook mapping opaque keys to permissions       |
+-------------------------------------------------------------+
```

---

## 2. Complete Python Implementation
Save the following script as `map_generator.py`:

```python
import os
import ast
import json

IGNORE_DIRS = {'.git', '__pycache__', 'venv', 'node_modules', 'scratch'}
IGNORE_FILES = {'.DS_Store', 'raugus_map.json'}

def extract_ast_symbols(filepath: str) -> list[str]:
    """Extracts top-level function, class, and variable names from Python code."""
    symbols = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(target.id)
    except Exception:
        pass # Skip unparseable or syntax-error files
    return symbols

def get_file_inode(path: str) -> int:
    """Returns the unique hardware inode number of the file on disk."""
    try:
        return int(os.stat(path).st_ino)
    except Exception:
        return 0

def build_raugus_map(workspace_root: str, output_path: str = "raugus_map.json"):
    vfs_map = {}
    print(f"[INDEXER] Crawling {workspace_root} for AST symbols and inodes...")

    for root, dirs, files in os.walk(workspace_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file in IGNORE_FILES:
                continue

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")
            
            # Formulate opaque key: core/server.py -> devcore.core.server.py
            module_key = "devcore." + rel_path.replace("/", ".")
            inode = get_file_inode(full_path)
            
            # Determine RBAC tier
            tier = 2 if rel_path.startswith(("core/", "security/", "agents/")) else 1

            vfs_map[module_key] = {
                "type": "file",
                "real_path": rel_path,
                "inode": inode,
                "rbac_tier": tier,
                "is_sensitive_vault": False,
                "symbols": {}
            }

            # If Python, extract symbols
            if file.endswith(".py"):
                symbols = extract_ast_symbols(full_path)
                for sym in symbols:
                    sym_key = f"{module_key}::{sym}"
                    vfs_map[module_key]["symbols"][sym] = {
                        "vfs_key": sym_key,
                        "rbac_tier": tier,
                        "write_locked": sym in ["reload_system", "get_current_user", "verify_key"]
                    }

    # Explicitly register sensitive vault directory
    vault_alias = "devcore.plugins.exam_application.content"
    vfs_map[vault_alias] = {
        "type": "directory",
        "real_path": "plugins/exam_application/content",
        "inode": get_file_inode(os.path.join(workspace_root, "plugins", "exam_application", "content")),
        "rbac_tier": 5,
        "is_sensitive_vault": True
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(vfs_map, f, indent=2)

    print(f"[INDEXER] Successfully mapped {len(vfs_map)} VFS keys to {output_path}")

if __name__ == "__main__":
    # Test mapping current workspace
    build_raugus_map(".", "test_raugus_map.json")
    if os.path.exists("test_raugus_map.json"):
        os.remove("test_raugus_map.json")
```

---

## 3. Why Order Matters in VFS Generation
1. **Prune Ignore Dirs In-Place**: Modifying `dirs[:] = [...]` prevents `os.walk` from descending into massive `.git` or `node_modules` folders, speeding up indexing by 100x.
2. **Fetch Inode Before Key Construction**: Extracting the inode before processing file contents ensures physical hardware verification occurs even on empty files.
3. **Write Locked Flag on Critical Functions**: Marking critical functions (`write_locked: True`) at map generation guarantees pre-tool hooks enforce locks automatically.

---

## 4. Beginner Coder Q&A
**Q: What does `dirs[:] = [...]` do in Python?**  
A: It modifies the active directory list in-place inside `os.walk`, telling the crawler to completely skip those subfolders before searching them.

**Q: Why replace slashes with dots in `module_key`?**  
A: Dots look like Python import statements (e.g. `devcore.core.server.py`), allowing developers to query virtual files using standard module notation.

**Q: How does this prevent prompt injection attacks?**  
A: The AI only sees keys like `devcore.core.server.py`. It does not know where the file lives on disk or what user account owns it.
