[//]: # (DOC_ID: SIRA-DOC-04_03 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 04.3: Architecture Solutions: Opaque VFS & AST Diffing Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY.md`](/docs/devlog/04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY)
- **Next Architecture Chapter**: [`04_04_EXTENDING_SIRAUGGA_PLUGINS_AND_SERVICES.md`](/docs/devlog/04_04_EXTENDING_SIRAUGGA_PLUGINS_AND_SERVICES)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-1)

When AI coding swarms modify complex software, traditional whole-file overwrites or loose text-matching edits frequently cause accidental bugs and overwrite security checks.

This chapter details the architecture of the **Raugus Resolver MCP Server** and the **AST Diffing Engine**, demonstrating how Siraugga achieves sub-file granularity and function-level write locks.

---

## The Raugus Resolver MCP Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-2)

The Raugus Resolver is an official Model Context Protocol (MCP) server that sits between the AI agent and the host filesystem:

```text
+-------------------------------------------------------------------------------+
|                             AI Coding Subagent                                |
|    Requests tool: read_by_key("devcore.core.server.py::ws_endpoint")          |
+---------------------------------------+---------------------------------------+
                                        |  MCP stdio Protocol
                                        v
+-------------------------------------------------------------------------------+
|                        Raugus Resolver MCP Server                             |
|  1. Discovers and indexes workspace symbols using Python's 'ast' module       |
|  2. Enforces spatial RBAC clearance before returning code chunks              |
|  3. Validates syntax integrity on write operations                            |
+-------------------+---------------------------------------+-------------------+
                    |                                       |
                    v                                       v
+---------------------------------------+   +-----------------------------------+
|         Read / Write Operations       |   |         PreToolUse Hook           |
| - Key-only resolution                 |   | - raugus_hook.py interceptor      |
| - Line coordinate editing             |   | - Blocks edits to locked symbols  |
+---------------------------------------+   +-----------------------------------+
```

### The 5 Core MCP Tools
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-3)
1. **`search_keys(query, entry_type, user_tier)`**: Discovers valid symbols without exposing physical folder paths.
2. **`list_module_keys(module_key, user_tier)`**: Enumerates all functions and classes in a module along with their line spans.
3. **`read_by_key(key, user_tier)`**: Retrieves exact source code for a specific function or class.
4. **`write_by_key(key, new_code, user_tier)`**: Safely replaces a single function's implementation after AST syntax verification.
5. **`refresh_key_map(user_tier)`**: Re-indexes the workspace AST when new modules are created.

---

## The Semantic Hook Interception (AST Diffing)
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-4)

When agents use the coordinate-based line editor (`edit_lines`), Siraugga intercepts the tool call via `raugus_hook.py` before execution:
1. **Coordinate Mapping**: Maps `start_line` and `end_line` parameters into the AST symbol table.
2. **Lock Evaluation**: Checks if the target lines overlap with a locked, read-only function defined in `raugus_map.json`.
3. **Deterministic Block**: If an agent attempts to edit line 45 (which contains a locked authentication function), the hook aborts execution before the file is modified.

---

## Why Order Matters in AST Hooking
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-5)

1. **AST Diffing Before File Modification**:
   - The PreToolUse hook must calculate line range intersections *before* passing coordinates to `edit_lines`. Once lines are spliced on disk, malicious changes are already live.
2. **`ast.parse()` Before In-Memory Swap**:
   - On write operations, the new code snippet must parse into a valid syntax node *before* replacing the function in the file buffer. Broken syntax must never reach the filesystem.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-6)

### Q: What is an AST node?
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-7)
**A:** In Python, the interpreter converts code text into a tree of nodes (e.g., `FunctionDef`, `ClassDef`, `Assign`). This allows programs to inspect code mathematically rather than treating it as dumb strings.

### Q: Why is coordinate editing safer than character matching?
[//]: # (SECTION_ID: SIRA-DOC-04_03-SEC-8)
**A:** Exact character matching fails when indentation (tabs vs. spaces) or line endings differ. Coordinate editing replaces lines 25 through 40 deterministically, regardless of whitespace quirks.
