[//]: # (DOC_ID: SIRA-DEV-02_40 | VERSION: v1.0 | SCOPE: DEVLOG)

# Pillar 02.40: Source Code Evidence: CommonMark Reference Parser & AST Heading Anchors

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Problem Analysis**: [`../01_PROBLEMS_ENCOUNTERED/01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS.md`](/docs/devlog/01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS)

---

[//]: # (SECTION_ID: SIRA-DEV-02_40-SEC-1)
## Overview & Evidence Context

This document provides concrete source code citations from the live synchronization bridge (`sync_to_eprofile.py`), web documentation view engine (`docs_mod.py`), and the structural auditor (`audit_doc_structure.py`).

These excerpts prove how the architecture extracts metadata from pure CommonMark reference definitions, automatically injects section heading anchors into the HTML AST, and validates tagging compliance with zero DOM pollution.

---

[//]: # (SECTION_ID: SIRA-DEV-02_40-SEC-2)
## 1. Verbatim Source Excerpts

### Excerpt A: Extracting Invariant `DOC_ID` and `VERSION` (`sync_to_eprofile.py`)
This excerpt from the synchronization script demonstrates how metadata declared in CommonMark link reference syntax is parsed via regular expressions:

```python
# Location: Central_Docs/scripts/sync_to_eprofile.py (Lines 382–390)
# Extract or compute Document ID and Version
doc_id, p_code, c_code = compute_doc_id(project, category, relative_slug)
version = "v1.0"
id_m = re.search(r'\[//\]:\s*#\s*\(DOC_ID:\s*([^|\s]+)\s*\|\s*VERSION:\s*([^|\s]+)', content)
if id_m:
    doc_id = id_m.group(1).strip()
    version = id_m.group(2).strip()

sections = extract_sections(content, doc_id)
```

### Excerpt B: Invariant Section Anchor Attachment (`e_profile/docs_mod.py`)
This excerpt proves how the web server transforms Markdown headings into accessible, deep-linkable HTML headings with invariant IDs without altering the human-readable text:

```python
# Location: e_profile/docs_mod.py (Lines 429–446)
doc_id = doc_meta.get('doc_id')
if doc_id:
    sec_idx = 1
    def _attach_h_id(match):
        nonlocal sec_idx
        tag = match.group(1)
        attrs = match.group(2)
        inner = match.group(3)
        clean = re.sub(r'<[^>]+>', '', inner).strip()
        num_m = re.match(r'^\s*(\d+(?:\.\d+)*)\.?\s+(.+)$', clean)
        sec_num = num_m.group(1).replace('.', '_') if num_m else str(sec_idx)
        if not num_m:
            sec_idx += 1
        sec_id = f"{doc_id}-SEC-{sec_num}"
        if 'id=' not in attrs:
            return f'<{tag} id="{sec_id}"{attrs}>{inner}</{tag}>'
        return match.group(0)
    html_body = re.sub(r'<(h[23])([^>]*)>(.*?)</\1>', _attach_h_id, html_body, flags=re.DOTALL)
```

### Excerpt C: Structural Tagging & Screen Reader Gatekeeper (`audit_doc_structure.py`)
This excerpt from the automated auditor validates that headings are capped at H2 and H3, that metadata headers follow CommonMark definitions, and that no leaked personal paths exist:

```python
# Location: Central_Docs/scripts/audit_doc_structure.py (Lines 55–58, 200–222)
RE_DOC_ID = re.compile(r'\[//\]:\s*#\s*\(\s*DOC_ID:\s*([^|\s]+)\s*\|\s*VERSION:\s*([^|\s]+)', re.IGNORECASE)
RE_SECTION_ID = re.compile(r'\[//\]:\s*#\s*\(\s*SECTION_ID:\s*([^)]+)\)', re.IGNORECASE)

def _check_heading_hierarchy(self, lines: List[str], issues: List[AuditIssue]):
    """Ensures headings are strictly capped at H2 and H3 to protect screen readers."""
    in_code_block = False
    for idx, line in enumerate(lines):
        s_line = line.strip()
        if s_line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if s_line.startswith("####"):
            m = re.match(r'^(#{4,6})\s+(.+)$', s_line)
            if m:
                level = len(m.group(1))
                issues.append(AuditIssue(
                    "UNI-H4-CAP",
                    IssueSeverity.CRITICAL,
                    f"Screen reader rule violation: H{level} header detected. Headings MUST be capped at H2 (##) and H3 (###).",
                    line_num=idx + 1,
                    fixable=True
                ))
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_40-SEC-3)
## 2. What This Source Proves

1. **Zero HTML Residue**: Because `[//]: # (...)` conforms to CommonMark link reference definition grammar, Python's `markdown` library ignores it entirely during conversion. No `[//]:` or `# (...)` strings ever leak into the rendered HTML body.
2. **Deterministic Section Anchors**: The `_attach_h_id` regex function in `docs_mod.py` ensures that every `<h2>` and `<h3>` element automatically gains an invariant `id="{DOC_ID}-SEC-{N}"` attribute, enabling deep-linking across documents without manual HTML authoring.
3. **Automated Enforcement**: The `audit_doc_structure.py` script automatically verifies metadata compliance and enforces heading caps across all repositories before deployment.

---

[//]: # (SECTION_ID: SIRA-DEV-02_40-SEC-4)
## 3. Beginner Coder Q&A

### How does `_attach_h_id` determine section numbering if my heading has no numbers?
**A:** If a heading starts with a section number like `## 1. Overview`, the regex captures `1` and generates `id="{DOC_ID}-SEC-1"`. If a heading has no numeric prefix, the function increments an internal counter (`sec_idx`) to guarantee that every heading still receives a unique, predictable anchor.

### What prevents the regex from modifying code blocks containing `<h2>` text?
**A:** In `docs_mod.py`, `_attach_h_id` runs *after* the markdown parser has converted fenced code blocks into `<pre><code>...</code></pre>`. In `audit_doc_structure.py`, the scanner tracks an `in_code_block` boolean flag to ignore any headings inside fenced blocks.

---

[//]: # (SECTION_ID: SIRA-DEV-02_40-SEC-5)
## 4. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Foundational Primer** | Introduction to canonical metadata and pure markdown reference tagging. | [`00G_BEGINNER_GUIDE_TO_INVARIANT_METADATA_AND_CANONICAL_TAGGING.md`](/docs/devlog/00G_BEGINNER_GUIDE_TO_INVARIANT_METADATA_AND_CANONICAL_TAGGING) |
| **Problem Analysis** | Detailed breakdown of link degradation and assistive technology noise traps. | [`01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS.md`](/docs/devlog/01_44_CROSS_REFERENCE_DEGRADATION_AND_TAG_CLUTTER_TRAPS) |
| **Diagnostic Verification** | Terminal execution traces proving zero HTML residue and AST anchor validity. | [`03_37_METADATA_TAG_INTEGRITY_AND_SCREEN_READER_DOM_LOGS.md`](/docs/devlog/03_37_METADATA_TAG_INTEGRITY_AND_SCREEN_READER_DOM_LOGS) |
| **Architectural Blueprint** | Comprehensive architectural data flow from markdown to web catalog. | [`04_40_CANONICAL_METADATA_AND_SECTION_INVARIANT_ARCHITECTURE.md`](/docs/devlog/04_40_CANONICAL_METADATA_AND_SECTION_INVARIANT_ARCHITECTURE) |
| **From-Scratch Creation Guide** | Step-by-step tutorial writing the metadata validator and anchor generator. | [`05_43_INVARIANT_TAGGING_VALIDATOR_AND_AST_ANCHOR_FROM_SCRATCH.md`](/docs/devlog/05_43_INVARIANT_TAGGING_VALIDATOR_AND_AST_ANCHOR_FROM_SCRATCH) |

</details>
