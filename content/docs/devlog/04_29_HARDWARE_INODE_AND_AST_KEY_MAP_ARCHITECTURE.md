# Hardware Inode & AST Key Map Architecture

## 1. Architectural Concept & Core Objective
Conventional access control models bind security permissions strictly to physical filesystem paths (e.g., `/core/server.py`). However, path-based access control fails against autonomous subagents that can rename files, create symlinks, or move files into unmonitored directories.

The Hardware Inode & AST Key Map Architecture (`generate_raugusmap.py` and `security/raugus_map.json`) decouples permissions from physical paths. It anchors access control to **hardware filesystem inodes** (`st_ino`) and maps code to **semantic AST keys** (`devcore.*::symbol`).

```
+-------------------------------------------------------------+
|               Physical File on Storage Device               |
|            Inode: 18492041 | Path: core/server.py           |
+-------------------------------------------------------------+
                              |
                     Abstract Syntax Tree Scan
                              |
                              v
+-------------------------------------------------------------+
|              Raugus Map Indexer (generate_raugusmap)        |
|    - Maps Inode 18492041 -> devcore.core.server.py          |
|    - Indexes symbols: FunctionDef, ClassDef, Assign         |
|    - Tags Sensitive Vaults (RBAC Tier 5)                    |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|               Opaque Virtual File System (VFS)              |
|        Exposes: 'devcore.core.server.py::reload_system'     |
|              (Zero Physical Paths Exposed to AI!)           |
+-------------------------------------------------------------+
```

---

## 2. Inode Evasion Immunity
Even if an agent or malicious process executes `mv core/server.py core/tmp_server.py`, the filesystem's hardware inode remains unchanged. When the Raugus Resolver inspects the file, it looks up the inode in `raugus_map.json` and immediately re-attaches the original Tier-2 Core Engine security policy.

---

## 3. Semantic AST Granularity & Zero Line Drift
Instead of addressing code by static line numbers, the architecture identifies symbols by their AST node names (`FunctionDef`, `AsyncFunctionDef`, `ClassDef`). When an edit is requested:
1. The resolver parses the current file AST into memory.
2. It locates the target symbol by name.
3. It extracts the exact live line span (`node.lineno` to `node.end_lineno`), completely neutralizing line drift.

---

## 4. Why Order Matters in VFS Mapping
1. **Query Hardware Inode Before Path Strings**: Comparing inodes before path names detects symlink swaps and file renames instantly.
2. **Parse AST on Clean Files Before Writing Map**: Verifying that source code parses without syntax errors ensures corrupt trees are not saved to the phonebook.
3. **Register Sensitive Vaults Explicitly**: Tagging confidential folders (like exam question vaults) guarantees they are hidden even before files are added.

---

## 5. Beginner Coder Q&A
**Q: What is a semantic AST key?**  
A: A virtual string that represents an exact function or class (like `devcore.core.routes.system.py::reload_system`) without exposing the real file path on disk.

**Q: Can two files have the same inode?**  
A: On the same filesystem partition, every distinct file has a unique inode number. Only hard links point to the same inode.

**Q: Why hide physical file paths from the AI?**  
A: Because an AI that does not know the physical path cannot attempt path traversal attacks (`../../`) or probe the host operating system.
