[//]: # (DOC_ID: SIRA-ARCH-05_43 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.43: From-Scratch Creation Guide: Invariant Tagging Validator & AST Anchor Injector

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Problem Analysis**: [`../01_PROBLEMS_ENCOUNTERED/01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS.md`](/docs/devlog/01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-1)
## Overview & Starting From Scratch

This creation guide teaches you how to build a standalone Python utility script (`validate_metadata_tags.py`) from scratch.

This script scans any directory of markdown documents, validates that every file begins with a proper CommonMark `DOC_ID` definition on line 1, checks that headings are capped at H2 and H3 for screen readers, and tests that heading anchors can be generated cleanly without DOM pollution.

> [!NOTE] Starting From Scratch
> Open a blank editor window (such as Notepad, TextEdit, VS Code, or nano) or create a fresh blank file in your terminal:
> ```bash
> touch validate_metadata_tags.py
> ```

> [!WARNING] Line Ending Advisory (CRLF vs LF)
> If you are authoring this file on Windows for execution within Linux or WSL, ensure your text editor saves with Unix line endings (`LF`). Windows carriage returns (`CRLF`) will cause bash and Python interpreters to fail with unexpected syntax errors.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-2)
## 1. Step-by-Step Script Construction

### Step 1: Core Imports and Metadata Patterns (Lines 1–25)
Open your blank file and write the standard library imports and compiled regular expressions:

```python
#!/usr/bin/env python3
"""
validate_metadata_tags.py - Invariant Metadata & Section Anchor Validator
"""
import sys
import os
import re
from pathlib import Path
from typing import List, Tuple, Dict

# Canonical regex patterns for CommonMark reference definitions
RE_DOC_ID = re.compile(
    r'^\[//\]:\s*#\s*\(\s*DOC_ID:\s*([A-Z0-9_\-]+)\s*\|\s*VERSION:\s*([^|\s]+)\s*\|\s*SCOPE:\s*([^)]+)\)',
    re.IGNORECASE
)
RE_SECTION_ID = re.compile(r'\[//\]:\s*#\s*\(\s*SECTION_ID:\s*([^)]+)\)', re.IGNORECASE)
RE_H4_PLUS = re.compile(r'^(#{4,6})\s+(.+)$')
```
- **Lines 1–7**: Standard Python imports without third-party dependencies so the script runs anywhere.
- **Lines 9–17**: Compiled regular expressions that identify the canonical `DOC_ID` metadata header and illegal H4+ headers.

### Step 2: The Document Validation Logic (Lines 26–55)
Next, implement the file inspection function:

```python
def validate_markdown_file(file_path: Path) -> Tuple[bool, List[str]]:
    """Audits a single markdown file for metadata and accessibility compliance."""
    errors = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"Failed to read file: {e}"]

    lines = content.splitlines()
    if not lines:
        return False, ["File is empty."]

    # 1. Line 1 Invariant Header Verification
    line_1 = lines[0].strip()
    if not RE_DOC_ID.match(line_1):
        errors.append("Line 1 must contain a valid CommonMark DOC_ID definition: [//]: # (DOC_ID: ... | VERSION: ... | SCOPE: ...)")

    # 2. Heading Cap Verification (Screen Reader Protection)
    in_code_block = False
    for idx, line in enumerate(lines, start=1):
        s_line = line.strip()
        if s_line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if RE_H4_PLUS.match(s_line):
            errors.append(f"Line {idx}: Heading exceeds H3 ceiling. Headings must be capped at ## and ###.")

    return len(errors) == 0, errors
```
- **Lines 26–36**: Reads the file safely and checks for empty content.
- **Lines 38–41**: Validates that line 1 contains the invariant metadata definition.
- **Lines 43–54**: Iterates through lines, skipping code blocks, to ensure no headings violate the H3 ceiling.

### Step 3: Directory Walker and CLI Entrypoint (Lines 56–85)
Finally, write the main execution loop:

```python
def main():
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(f"[*] Scanning markdown files in {target_dir.resolve()}...")

    total_files = 0
    passed_files = 0

    for md_file in sorted(target_dir.rglob("*.md")):
        if any(ignored in str(md_file) for ignored in [".git", "venv", "node_modules"]):
            continue
        total_files += 1
        is_valid, errors = validate_markdown_file(md_file)
        if is_valid:
            passed_files += 1
            print(f"  [PASS] {md_file.name}")
        else:
            print(f"  [FAIL] {md_file.name}")
            for err in errors:
                print(f"         - {err}")

    print("\n" + "=" * 50)
    print(f"SUMMARY: {passed_files}/{total_files} documents compliant.")
    print("=" * 50)
    sys.exit(0 if passed_files == total_files else 1)

if __name__ == "__main__":
    main()
```
- **Lines 56–78**: Recursively discovers all markdown files, ignoring virtual environments and version control directories.
- **Lines 80–84**: Outputs a clear summary and returns a clean exit code (`0` for success, `1` for failures) suitable for CI/CD or pre-commit hooks.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-3)
## 2. Why Order Matters

When implementing this validator, each component depends on the preceding logic:
1. **Regex Compilation Before File Iteration**: Pre-compiling `RE_DOC_ID` and `RE_H4_PLUS` outside the loop prevents redundant compilation overhead across hundreds of files.
2. **Code Block Toggle Before Heading Evaluation**: The `in_code_block` state must be updated before testing heading patterns, otherwise documentation examples inside code fences would trigger false positive heading violations.
3. **Line 1 Evaluation Before Full Scan**: Checking line 1 immediately identifies completely un-tagged legacy files without requiring unnecessary parsing of downstream sections.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-4)
## 3. Permissions & Execution

Ensure the script has executable permissions on Linux or WSL:
```bash
chmod +x validate_metadata_tags.py
```

To run the validator against your documentation folder:
```bash
python3 validate_metadata_tags.py docs/
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-5)
## 4. 10-Second Verification Checklist

To verify that your newly created validator works properly:
- [ ] Run `python3 validate_metadata_tags.py --help` or run it on a valid markdown file to confirm execution without syntax errors.
- [ ] Create a dummy file with an illegal `#### Header` and confirm the script outputs `[FAIL]` and exits with code 1.
- [ ] Confirm clean terminal output without unhandled tracebacks.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-6)
## 5. Beginner Coder Q&A

### Why does the script use `sys.exit(1)` when a document fails?
**A:** Returning exit code `1` alerts shell scripts, Makefile runners, and Git pre-commit hooks that a failure occurred, allowing automated pipelines to automatically block non-compliant commits before they reach the repository.

### Can this script be extended to automatically fix broken headers?
**A:** Yes. In `audit_doc_structure.py`, the auto-remediation flag (`--fix`) uses regex replacement to replace `####` with `###` and inject missing metadata tags automatically.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_43-SEC-7)
## 6. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Foundational Primer** | Conceptual overview of invariant identity and link reference definitions. | [`00G_BEGINNER_GUIDE_TO_INVARIANT_METADATA_AND_CANONICAL_TAGGING.md`](/docs/devlog/00G_BEGINNER_GUIDE_TO_INVARIANT_METADATA_AND_CANONICAL_TAGGING) |
| **Problem Analysis** | Full breakdown of link rot and screen reader acoustic spam traps. | [`01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS.md`](/docs/devlog/01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS) |
| **Source Code Evidence** | Verbatim production excerpts of AST heading anchor injection. | [`02_40_COMMONMARK_REFERENCE_PARSER_AND_AST_ANCHORS_EVIDENCE.md`](/docs/devlog/02_40_COMMONMARK_REFERENCE_PARSER_AND_AST_ANCHORS_EVIDENCE) |
| **Diagnostic Verification** | Terminal execution traces proving zero HTML residue and DOM compliance. | [`03_37_METADATA_TAG_INTEGRITY_AND_SCREEN_READER_DOM_LOGS.md`](/docs/devlog/03_37_METADATA_TAG_INTEGRITY_AND_SCREEN_READER_DOM_LOGS) |
| **Architectural Blueprint** | End-to-end architecture of the multi-dimensional tagging and catalog pipeline. | [`04_40_CANONICAL_METADATA_AND_SECTION_INVARIANT_ARCHITECTURE.md`](/docs/devlog/04_40_CANONICAL_METADATA_AND_SECTION_INVARIANT_ARCHITECTURE) |

</details>
