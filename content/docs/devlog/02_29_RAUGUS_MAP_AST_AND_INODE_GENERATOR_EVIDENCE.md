# Raugus Map AST & Inode Generator Source Evidence

## 1. Architectural Role & File Location
This document contains source code evidence from `generate_raugusmap.py`. It details how DevCore scans Python source files, extracts function and variable AST symbols, records hardware filesystem inodes, and indexes sensitive vault directories into `security/raugus_map.json`.

---

## 2. AST Symbol Extraction Evidence
The generator uses Python's native `ast` module to catalog all executable symbols without running code:

```python
# generate_raugusmap.py: Lines 6-23
def parse_ast_for_file(filepath):
    """Returns a list of top-level function, class, and variable names."""
    symbols = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(target.id)
    except Exception:
        pass # Ignore syntax errors or unparseable files
    return symbols
```

---

## 3. Hardware Inode Binding Evidence
To detect file renaming attacks, each file's physical hardware inode is recorded:

```python
# generate_raugusmap.py: Inode extraction
def _get_inode(p):
    try:
        return int(os.stat(p).st_ino)
    except Exception:
        return 0
```

---

## 4. Opaque Key Mapping & Sensitive Vault Tagging Evidence
Paths are transformed into opaque keys (`devcore.*`), and protected content vaults are registered:

```python
# generate_raugusmap.py: Vault registration & serialization
def generate_raugusmap(root_dir, existing_map=None):
    raugus_map = {}
    
    # Explicitly register sensitive vault directories (even when empty)
    exam_content_dir = os.path.join(root_dir, "plugins", "exam_application", "content")
    exam_content_alias = "devcore.plugins.exam_application.content"
    raugus_map[exam_content_alias] = {
        "type": "directory",
        "real_path": exam_content_dir,
        "inode": _get_inode(exam_content_dir),
        "rbac_tier": 5,
        "is_sensitive_vault": True
    }
    
    # Serialize to security/raugus_map.json
    out_file = os.path.join(root_dir, "security", "raugus_map.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(raugus_map, f, indent=2)
```

---

## 5. Why Order Matters in VFS Map Generation
1. **Catch Syntax Errors Silently**: Using `try/except` during `ast.parse()` ensures a broken file does not halt the entire project mapping process.
2. **Assign Inodes Before Relative Keying**: Extracting hardware inodes before computing relative paths guarantees physical identity is preserved regardless of path representations.
3. **Register Sensitive Vaults Explicitly**: Hard-coding critical security directories ensures empty folders receive Tier-5 protection before user files are placed in them.

---

## 6. Beginner Coder Q&A
**Q: Why parse AST instead of using regular expressions?**  
A: Regexes get confused by multiline functions, decorators, or commented-out code. The `ast` parser understands exact Python syntax without false positives.

**Q: What is `is_sensitive_vault`?**  
A: A flag in `raugus_map.json` that marks folders holding confidential exam questions or encryption keys, completely hiding them from lower-tier subagents.

**Q: Can this generator be run while the server is active?**  
A: Yes! The MCP tool `refresh_key_map()` executes this generator dynamically whenever structural updates occur.
