[//]: # (DOC_ID: SIRA-DEV-01_33 | VERSION: v1.0 | SCOPE: DEV)

# Inode Tampering & AST Key Drift Traps

[//]: # (SECTION_ID: SIRA-DEV-01_33-SEC-1)
## 1. The Problem: The Rename Evasion Trap
[//]: # (SECTION_ID: SIRA-DOC-01_33-SEC-1)
Traditional access control systems map security policies strictly to physical file paths (e.g., `/core/server.py`). However, autonomous subagents and shell tools can easily evade path-based filters through file renaming, symlinking, or moving files into temporary staging areas.

If an agent renames `core/server.py` to `core/server_temp.py`, naive path filters fail to recognize the target as a Tier-2 Core Engine file, allowing unauthorized modifications to administrative code.

```
+-------------------------------------------------------------+
|             Target File: core/server.py (Tier 2 Admin)      |
+-------------------------------------------------------------+
                              |
                     AGENT RENAMES FILE
                     mv core/server.py core/server_temp.py
                              |
                              v
+-------------------------------------------------------------+
|             Path Filter Checks: 'core/server_temp.py'       |
|             [BYPASS: Path Not in Blacklist Rule]            |
|       - Unauthorized code modifications applied!            |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_33-SEC-2)
## 2. The AST Line Drift Trap
[//]: # (SECTION_ID: SIRA-DOC-01_33-SEC-2)
When code access systems reference functions by line coordinates (e.g., "Function `handle_login` at lines 40-65"), any preceding edit introduces **Line Drift**. If three lines are added at line 10, modifying lines 40-65 now overwrites unrelated code, corrupting the file's syntax tree.

---

[//]: # (SECTION_ID: SIRA-DEV-01_33-SEC-3)
## 3. The Solution: Hardware Inodes & Dynamic AST Keys
[//]: # (SECTION_ID: SIRA-DOC-01_33-SEC-3)
Siraugga resolved this with the Raugus Map Indexer (`generate_raugusmap.py`):
1. **Hardware Inode Binding**: The generator inspects `os.stat(p).st_ino`. Even if an attacker or subagent renames or moves a file, its hardware inode remains identical, immediately exposing evasion attempts.
2. **Opaque AST Symbol Keys**: Code is indexed by semantic AST symbols (`module::function_name`) rather than static line numbers.
3. **Automated AST Re-indexing**: Before applying edits, the Raugus Resolver parses the live file AST to calculate exact current line boundaries dynamically.

---

[//]: # (SECTION_ID: SIRA-DEV-01_33-SEC-4)
## 4. Why Order Matters in AST Indexing
[//]: # (SECTION_ID: SIRA-DOC-01_33-SEC-4)
1. **Fetch Inode Before Checking Path Rules**: Inspecting the hardware inode first detects if a file has been swapped via symlink before evaluating access tiers.
2. **Parse AST Syntax Before Resolving Offsets**: Verifying that the target file has valid syntax ensures line numbers can be computed safely without exceptions.
3. **Update Raugus Map After Structural Renames**: Running `generate_raugusmap.py` immediately following structural changes ensures the virtual phonebook reflects live hardware state.

---

[//]: # (SECTION_ID: SIRA-DEV-01_33-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_33-SEC-5)
**Q: What is an inode (`st_ino`)?**  
A: An inode is a unique integer assigned by the filesystem to a specific physical file on disk. A file's name can change, but its inode number remains constant until the file is deleted.

**Q: Why is referencing functions by name better than by line numbers?**  
A: Because line numbers change every time someone adds comments or extra code above the function, while the function name remains consistent.

**Q: What does `generate_raugusmap.py` output?**  
A: It generates `security/raugus_map.json`, a phonebook mapping opaque keys (`devcore.*`) to hardware inodes, symbols, and RBAC tiers.
