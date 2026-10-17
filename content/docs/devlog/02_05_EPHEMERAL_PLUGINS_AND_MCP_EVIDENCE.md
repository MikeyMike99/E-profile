# Pillar 02.5: Source Evidence: Ephemeral Plugins & MCP Protocols

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_04_FORENSIC_VAULT_AND_PII_SCRUBBING_EVIDENCE.md`](/docs/devlog/02_04_FORENSIC_VAULT_AND_PII_SCRUBBING_EVIDENCE)
- **Next: Diagnostic Tests**: [`../03_DIAGNOSTIC_TESTS/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS.md`](/docs/devlog/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS)

---

## Overview

This chapter documents verbatim source citations from Siraugga's Model Context Protocol (MCP) server plugins (`.agents/plugins/line_editor/server.py`) and the system directives enforcing the Zero-Modification Plugin Architecture (`.agents/rules/EXAM_APPLICATION.md`).

---

## Source 1: The MCP Coordinate Line Editor (`edit_lines`)

- **Source File**: `<project_root>/.agents/plugins/line_editor/server.py`
- **Location**: Lines 21–75

```python
def edit_lines(target_file: str, start_line: int, end_line: int, new_code: str) -> str:
    """Edit a block of lines in a file by line coordinates (1-indexed).
    Lines are 1-indexed. start_line and end_line are inclusive."""
    
    if start_line < 1:
        return "Error: start_line must be >= 1"
    if start_line > end_line:
        return "Error: start_line cannot be greater than end_line"

    with open(target_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    idx_start = start_line - 1
    idx_end = end_line  # Slicing is exclusive of upper bound

    replacement_lines = [l + '\n' for l in new_code.splitlines()]
    lines[idx_start:idx_end] = replacement_lines

    with open(target_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return f"Successfully replaced lines {start_line} through {end_line} in {target_file}"
```

### What This Source Proves
1. **Zero Character-Matching Failures**: Replaces fragile string-matching tools (`replace_file_content`) with deterministic line coordinate slicing.
2. **Atomic Splicing**: Slices Python lists in memory before committing changes back to disk, avoiding file corruption during partial writes.

---

## Source 2: The Zero-Modification Template Mandate

- **Source File**: `<project_root>/.agents/rules/EXAM_APPLICATION.md`
- **Location**: Core Directives

```markdown
# Exam Application Core Directives

**CRITICAL RULE FOR ALL AGENTS:**
You are strictly forbidden from directly modifying the core HTML, JavaScript, or CSS 
templates of the Exam Application (e.g., exam_application.html or exam_builder.html).

**The Blueprint Concept:**
The exam_application.html file and its JavaScript are strictly fixed blueprints/templates.
- Do NOT search for hidden codebase features or try to hack the JS to add "extended modifications."
- The JSON payload (exam_temp.json) IS the modification template. Adding textboxes, timers, 
  dropdowns, and changing the flow is achieved entirely by injecting the correct JSON structure.
- You simply inject temporary JSON files to dictate how the front-end renders.
```

### What This Source Proves
1. **Immutability Defense**: Prevents AI coding swarms from breaking accessible frontend templates.
2. **Schema-Driven Flexibility**: All dynamic features (timers, quiz replenishment, scoring) are declared purely through JSON data structures.

---

## Why Order Matters in Splicing & Plugins

1. **Bounds Validation Before Reading File Content**:
   - `start_line` and `end_line` bounds must be checked *before* loading massive file buffers. If an invalid coordinate is passed, early validation aborts immediately, saving RAM.
2. **Format Normalization Before Rendering**:
   - `format_exam.py` must sanitize generated JSON payloads *before* the UI iframe fetches the data, ensuring corrupt JSON never crashes client JavaScript.

---

## Beginner Coder Q&A

### Q: Why do AI agents struggle with standard `replace_file_content`?
**A:** `replace_file_content` requires an exact character-by-character string match. If an editor changes a tab to 4 spaces or adds a trailing newline, the search fails with "Target content not found." Coordinate-based line editing completely eliminates this trap.

### Q: What is an MCP Tool?
**A:** Model Context Protocol (MCP) is an open standard that allows AI agents to securely call external tools and scripts via standard input and output (`stdio`).
