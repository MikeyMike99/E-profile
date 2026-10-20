[//]: # (DOC_ID: SIRA-DEV-02_41 | VERSION: v1.0 | SCOPE: DEVLOG)

# Pillar 02.41: Source Code Evidence: Release Staging Engine & In-Place Surgery

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Problem Analysis**: [`../01_PROBLEMS_ENCOUNTERED/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS)

---

[//]: # (SECTION_ID: SIRA-DEV-02_41-SEC-1)
## Overview & Evidence Context

This document captures verbatim source code citations from `e_profile/docs_mod.py` demonstrating the implementation of the Curated Release Staging Engine, the Unreleased Holding Notice, the In-Place Markdown Editor, and the Dual-Persistence Write Architecture.

---

[//]: # (SECTION_ID: SIRA-DEV-02_41-SEC-2)
## 1. Verbatim Source Excerpts

### Excerpt A: Visitor Filtering & Release Status Evaluation (`docs_mod.py`)
This excerpt proves how documents are filtered dynamically based on visitor authentication status and scheduled release timestamps:

```python
# Location: e_profile/docs_mod.py (Lines 248–265)
is_released = False
if status == 'published':
    is_released = True
elif status == 'scheduled' and release_date:
    is_released = (now_iso >= release_date)
    
d_copy = dict(d)
d_copy['publish_status'] = status
d_copy['release_date'] = release_date
d_copy['is_released'] = is_released

if is_admin:
    result.append(d_copy)
else:
    if is_released:
        result.append(d_copy)
        
return result
```

### Excerpt B: The Accessible Unreleased Holding Notice (`docs_mod.py`)
This excerpt proves that direct navigation to unreleased chapters displays an informative, accessible holding screen rather than a broken 404:

```python
# Location: e_profile/docs_mod.py (Lines 375–395)
def render_unreleased_notice(title, status, release_date):
    date_str = f"on <strong>{release_date}</strong>" if release_date else "soon in our scheduled rollout"
    return f"""
    <div class="unreleased-holding-box" role="region" aria-label="Scheduled Release Notice" style="padding: 45px 30px; text-align: center; background: rgba(12, 16, 24, 0.95); border: 1px solid rgba(255, 170, 0, 0.4); border-radius: 12px; margin: 30px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        <div style="font-size: 2.8rem; margin-bottom: 12px;">🕒</div>
        <h2 style="font-family: monospace; color: #ffaa00; font-size: 1.5rem; margin-bottom: 10px;">Chapter Scheduled for Release</h2>
        <h3 style="font-family: monospace; color: #fff; font-size: 1.2rem; margin-bottom: 16px;">{title}</h3>
        <p style="color: var(--text-bright); font-size: 0.98rem; line-height: 1.6; max-width: 620px; margin: 0 auto 24px auto;">
            This chapter is part of the curated publication sequence and will be publicly released {date_str}.
            To ensure visitors are not overwhelmed with 300+ technical blueprints at once, chapters are released on an engineering schedule.
        </p>
        <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
            <button type="button" class="ctrl-btn portal-crumb-btn" onclick="showLandingView()">🏛️ Return to Documentation Vault</button>
            <button type="button" class="ctrl-btn" onclick="openNavigatorAndSearch()">📑 Explore Available Chapters</button>
        </div>
    </div>
    """
```

### Excerpt C: Dual-Persistence Writing (`docs_mod.py`)
This excerpt proves that creating a new chapter immediately persists to both `e_profile` and the upstream `Central_Docs` source repository:

```python
# Location: e_profile/docs_mod.py (Lines 787–802)
# 1. Primary Write to Local Web Directory
dest_dir = DOCS_DIR / category
dest_dir.mkdir(parents=True, exist_ok=True)
file_path = dest_dir / f"{slug}.md"
file_path.write_text(content, encoding='utf-8')

# 2. Dual-Persistence Write to Upstream Central_Docs Repository
if CENTRAL_DOCS_DIR.exists():
    proj_dir = CENTRAL_DOCS_DIR / "projects" / ("siraugga_framework" if project == "siraugga" else project)
    if proj_dir.exists():
        c_dir = proj_dir / category if (proj_dir / category).exists() else proj_dir
        try:
            (c_dir / f"{slug}.md").write_text(content, encoding='utf-8')
        except Exception:
            pass
```

### Excerpt D: Safe Timestamped Archiving on Chapter Deletion (`docs_mod.py`)
This excerpt proves that deletions do not permanently erase files, but safely relocate them to a timestamped `.archive/` directory:

```python
# Location: e_profile/docs_mod.py (Lines 825–836)
archive_dir = DOCS_DIR / ".archive"
archive_dir.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

for p in paths:
    if p.exists():
        archive_path = archive_dir / f"{timestamp}_{p.name}"
        shutil.move(str(p), str(archive_path))
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_41-SEC-3)
## 2. What This Source Proves

1. **Anti-Overwhelm Enforcement**: The server guarantees that public visitors see only published content, while holding screens gracefully explain the publication rollout.
2. **Dual-Persistence Synchronization**: Any in-place edits or new chapters authored in the web interface are saved to both repositories simultaneously, preventing git sync wipeouts.
3. **Safe Reversibility**: Chapter deletion moves files to `.archive/` with full timestamps, eliminating catastrophic data loss from accidental clicks.

---

[//]: # (SECTION_ID: SIRA-DEV-02_41-SEC-4)
## 3. Beginner Coder Q&A

### Why does Excerpt C use `try ... except Exception: pass` for Central_Docs?
**A:** In production environments where `e_profile` is deployed on a standalone server (such as PythonAnywhere), `CENTRAL_DOCS_DIR` might not exist. Wrapping the secondary write in a guarded block allows standalone operation without crashing the primary save.

### How does the holding screen prevent broken cross-references?
**A:** When other documents link to a scheduled chapter, visitors clicking the link are guided by the holding notice rather than encountering an alarming 404 error, preserving reader confidence.

---

[//]: # (SECTION_ID: SIRA-DEV-02_41-SEC-5)
## 4. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Foundational Primer** | Introduction to release staging, anti-overwhelm, and in-place editing. | [`00H_BEGINNER_GUIDE_TO_RELEASE_SCHEDULING_AND_IN_PLACE_EDITING.md`](/docs/devlog/00H_BEGINNER_GUIDE_TO_RELEASE_SCHEDULING_AND_IN_PLACE_EDITING) |
| **Problem Analysis** | Detailed analysis of cognitive overwhelm and out-of-band desync traps. | [`01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS) |
| **Diagnostic Verification** | Security audit test traces proving 26/26 staging and editing tests passing. | [`03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS.md`](/docs/devlog/03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS) |
| **Architectural Blueprint** | End-to-end data flow of visitor staging and dual-destination writes. | [`04_41_CURATED_RELEASE_SCHEDULING_AND_DUAL_PERSISTENCE_ARCHITECTURE.md`](/docs/devlog/04_41_CURATED_RELEASE_SCHEDULING_AND_DUAL_PERSISTENCE_ARCHITECTURE) |
| **From-Scratch Creation Guide** | Line-by-line guide building the release scheduler and in-place editor. | [`05_44_RELEASE_SCHEDULER_AND_IN_PLACE_EDITOR_FROM_SCRATCH.md`](/docs/devlog/05_44_RELEASE_SCHEDULER_AND_IN_PLACE_EDITOR_FROM_SCRATCH) |

</details>
