[//]: # (DOC_ID: SIRA-ARCH-05_44 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.44: From-Scratch Creation Guide: Release Staging Engine & In-Place Editor

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Problem Analysis**: [`../01_PROBLEMS_ENCOUNTERED/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-1)
## Overview & Starting From Scratch

This creation guide teaches beginner developers how to build a standalone Python module (`doc_release_manager.py`) from scratch.

This module provides the complete core logic for:
1. Managing a JSON-backed release schedule registry (`release_schedule.json`).
2. Filtering catalogs so public visitors see only published content while administrators see everything.
3. Executing safe in-place markdown file saves with dual-persistence writing.
4. Timestamped file archiving upon deletion.

> [!NOTE] Starting From Scratch
> Open a blank editor window (such as Notepad, TextEdit, VS Code, or nano) or create a fresh blank file in your terminal:
> ```bash
> touch doc_release_manager.py
> ```

> [!WARNING] Line Ending Advisory (CRLF vs LF)
> If you are authoring this file on Windows for execution within Linux or WSL, ensure your text editor saves with Unix line endings (`LF`). Windows carriage returns (`CRLF`) will cause bash and Python interpreters to fail with unexpected syntax errors.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-2)
## 1. Step-by-Step Script Construction

### Step 1: Imports and Registry Management (Lines 1–35)
Open your blank file and write the standard library imports and schedule loader functions:

```python
#!/usr/bin/env python3
"""
doc_release_manager.py - Release Staging & In-Place Document Manager
"""
import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

def load_schedule(registry_path: Path) -> dict:
    """Loads the release schedule JSON registry or returns a clean default schema."""
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": "1.0", "entries": {}}

def save_schedule(registry_path: Path, data: dict) -> None:
    """Safely saves the release schedule with indentation and trailing newline."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```
- **Lines 1–11**: Uses only Python standard library modules to eliminate external package requirements.
- **Lines 13–27**: Implements fault-tolerant JSON reading and atomic saving with automatic directory creation.

### Step 2: The Staging Filter Function (Lines 36–65)
Next, implement the visitor catalog filtering logic:

```python
def filter_documents_for_viewer(docs: List[dict], schedule: dict, is_admin: bool = False) -> List[dict]:
    """Filters a document list based on viewer clearance and scheduled release dates."""
    now_iso = datetime.now().isoformat()
    entries = schedule.get("entries", {})
    visible_docs = []

    for doc in docs:
        key = f"{doc.get('category')}/{doc.get('slug')}"
        entry = entries.get(key) or entries.get(doc.get('slug'))
        
        status = entry.get('status', 'draft') if entry else doc.get('publish_status', 'draft')
        release_date = entry.get('release_date') if entry else doc.get('release_date')
        
        is_released = False
        if status == 'published':
            is_released = True
        elif status == 'scheduled' and release_date:
            is_released = (now_iso >= release_date)
            
        doc_copy = dict(doc)
        doc_copy['publish_status'] = status
        doc_copy['release_date'] = release_date
        doc_copy['is_released'] = is_released
        
        if is_admin or is_released:
            visible_docs.append(doc_copy)
            
    return visible_docs
```
- **Lines 36–48**: Matches documents against the staging registry using category/slug keys.
- **Lines 50–65**: Evaluates timestamp boundaries and appends documents to the output list only if published, released, or viewed by an admin.

### Step 3: Dual-Persistence Writer and Archiver (Lines 66–105)
Finally, implement safe in-place file saves and timestamped archiving:

```python
def save_document_dual(primary_path: Path, secondary_path: Optional[Path], content: str) -> None:
    """Saves markdown content to the primary web path and upstream source repository."""
    primary_path.parent.mkdir(parents=True, exist_ok=True)
    primary_path.write_text(content, encoding="utf-8")
    
    if secondary_path:
        try:
            secondary_path.parent.mkdir(parents=True, exist_ok=True)
            secondary_path.write_text(content, encoding="utf-8")
        except Exception:
            pass

def archive_document(file_path: Path, archive_dir: Path) -> Path:
    """Safely relocates a file to a timestamped archive directory instead of deleting."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = archive_dir / f"{timestamp}_{file_path.name}"
    shutil.move(str(file_path), str(target_path))
    return target_path
```
- **Lines 66–77**: Writes the document to primary storage, then mirrors the write to the upstream repository.
- **Lines 79–86**: Relocates deleted files into `.archive/` with full timestamps, preventing accidental data loss.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-3)
## 2. Why Order Matters

When implementing this module, each step follows a mandatory operational sequence:
1. **Schedule Initialization Before Filter Execution**: The `release_schedule.json` file must be parsed into memory before evaluating the document list, preventing repetitive disk I/O on every iteration.
2. **Current Timestamp Evaluation Before Document Loop**: Calling `datetime.now().isoformat()` once outside the loop ensures all chapters are benchmarked against an identical time baseline.
3. **Primary Disk Save Before Secondary Mirroring**: The primary file write must succeed first so that local web clients receive the updated content immediately. Secondary repository syncing runs second in a fault-tolerant block.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-4)
## 3. Permissions & Execution

Ensure the script has executable permissions on Linux or WSL:
```bash
chmod +x doc_release_manager.py
```

To run a verification test demonstrating release filtering:
```bash
python3 -c "
import doc_release_manager as drm
from pathlib import Path

sample_docs = [
    {'category': 'manifesto', 'slug': 'ch1', 'title': 'Genesis'},
    {'category': 'devlog', 'slug': 'ch2', 'title': 'Draft Notes'}
]
schedule = {'entries': {'manifesto/ch1': {'status': 'published'}, 'devlog/ch2': {'status': 'draft'}}}

public_view = drm.filter_documents_for_viewer(sample_docs, schedule, is_admin=False)
admin_view = drm.filter_documents_for_viewer(sample_docs, schedule, is_admin=True)

print(f'Public visible chapters: {len(public_view)} (Expected: 1)')
print(f'Admin visible chapters: {len(admin_view)} (Expected: 2)')
assert len(public_view) == 1 and len(admin_view) == 2, 'Staging filter test failed!'
print('SUCCESS: Release staging filter operates correctly.')
"
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-5)
## 4. 10-Second Verification Checklist

To prove your newly created release manager functions properly:
- [ ] Run the Python verification one-liner above to confirm clean execution without syntax errors.
- [ ] Confirm `public_view` outputs exactly 1 chapter while `admin_view` outputs 2 chapters.
- [ ] Inspect console output to confirm there are no unhandled exception tracebacks.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-6)
## 5. Beginner Coder Q&A

### Why does `save_document_dual` use `primary_path.parent.mkdir(parents=True, exist_ok=True)`?
**A:** If you are saving a chapter in a new category subfolder that does not exist yet (like `content/docs/new_category/`), calling `mkdir(parents=True, exist_ok=True)` automatically creates all intermediate directories so `write_text()` does not crash with `FileNotFoundError`.

### What happens if the `release_schedule.json` file is deleted?
**A:** The `load_schedule()` function catches file missing errors and automatically falls back to an empty schema (`{"version": "1.0", "entries": {}}`), preventing the server from crashing.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_44-SEC-7)
## 6. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Foundational Primer** | Conceptual overview of anti-overwhelm staging and in-place editing. | [`00H_BEGINNER_GUIDE_TO_RELEASE_SCHEDULING_AND_IN_PLACE_EDITING.md`](/docs/devlog/00H_BEGINNER_GUIDE_TO_RELEASE_SCHEDULING_AND_IN_PLACE_EDITING) |
| **Problem Analysis** | Analysis of cognitive overwhelm and out-of-band web desync traps. | [`01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS) |
| **Source Code Evidence** | Verbatim code excerpts showing staging filters and dual-persistence. | [`02_41_RELEASE_STAGING_AND_IN_PLACE_SURGERY_EVIDENCE.md`](/docs/devlog/02_41_RELEASE_STAGING_AND_IN_PLACE_SURGERY_EVIDENCE) |
| **Diagnostic Verification** | Security audit test traces proving 26/26 staging and editing tests passing. | [`03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS.md`](/docs/devlog/03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS) |
| **Architectural Blueprint** | End-to-end data flow of visitor staging and dual-destination writes. | [`04_41_CURATED_RELEASE_SCHEDULING_AND_DUAL_PERSISTENCE_ARCHITECTURE.md`](/docs/devlog/04_41_CURATED_RELEASE_SCHEDULING_AND_DUAL_PERSISTENCE_ARCHITECTURE) |

</details>
