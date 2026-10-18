[//]: # (DOC_ID: SIRA-DEV-04_41 | VERSION: v1.0 | SCOPE: DEVLOG)

# Pillar 04.41: Solutions & Architecture: Curated Release Scheduling & Dual Persistence

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Problem Analysis**: [`../01_PROBLEMS_ENCOUNTERED/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS)

---

[//]: # (SECTION_ID: SIRA-DEV-04_41-SEC-1)
## 1. System Overview & Architectural Purpose

The **Curated Release Scheduling and Dual Persistence Architecture** bridges production web publishing with sovereign local development.

It solves the dual challenges of public reader cognitive overwhelm and data desynchronization by establishing:
1. An automated staging engine that paces chapter releases over time while holding internal drafts private.
2. An accessible in-place raw markdown editor enabling zero-restart content editing and chapter management directly in the browser.
3. A synchronized dual-destination write architecture ensuring changes made on the web server immediately propagate back into the upstream repository.

```
+-----------------------------------------------------------------------------------+
|                  CURATED RELEASE & DUAL PERSISTENCE ARCHITECTURE                  |
+-----------------------------------------------------------------------------------+
| 1. Visitor Layer (Role-Based Access Control):                                     |
|    - Public Visitor: Scans release_schedule.json -> Only 'published' rendered    |
|    - Direct Draft Request: Intercepted -> Displays accessible holding screen      |
|    - Super Admin: Clearance Granted -> Unrestricted view of all 300+ chapters     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 2. In-Place Editorial Engine (docs_mod.py):                                       |
|    - Status & Schedule API: Updates release_schedule.json dynamically             |
|    - Raw Markdown Editor: In-place editing via native accessible textarea         |
|    - Safe Archiver: Moves deleted files to .archive/YYYYMMDD_HHMMSS_<slug>.md     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 3. Dual-Persistence Synchronization Layer:                                        |
|    - Primary Target: Writes to local e_profile/content/docs/<category>/<slug>.md  |
|    - Secondary Target: Writes to upstream Central_Docs/projects/<proj>/<slug>.md  |
|    - Result: Zero git overwrite desync during automated downstream sync runs       |
+-----------------------------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_41-SEC-2)
## 2. Core Architectural Components

### 1. Release Schedule Staging Registry (`release_schedule.json`)
The staging registry maintains state for every chapter across the ecosystem:
```json
{
  "version": "1.0",
  "entries": {
    "manifesto/01_Echoes_in_the_Void": {
      "status": "published",
      "release_date": null,
      "updated_at": "2026-10-18T09:54:58"
    },
    "devlog/01_35_OWASP_DAST_VULNERABILITIES": {
      "status": "scheduled",
      "release_date": "2026-11-15T00:00:00",
      "updated_at": "2026-10-18T09:54:58"
    }
  }
}
```
This lightweight, file-backed registry enables instant schedule updates with zero database dependencies or process restarts.

### 2. In-Place Raw Markdown Surgery
Unlike heavy third-party WYSIWYG editors that inject messy HTML spans and break screen reader forms, our in-place editor uses a native `<textarea class="artifact-raw-editor">` styled to match the cyber-theme:
- **Instant Raw Editing**: Preserves exact CommonMark formatting and line 1 metadata.
- **Asynchronous Live Compilation**: On save, the backend returns rendered HTML, word counts, and estimated read times via JSON.
- **Screen Reader Focus Management**: Automatically moves keyboard focus to the editor upon activation, ensuring smooth assistive navigation.

### 3. Dual-Destination Write Bridge
To guarantee that web edits persist across git pulls and automated synchronizations, `docs_api_admin_save` writes directly to two destinations:
- **Destination A**: `e_profile/content/docs/<category>/<slug>.md` (Served immediately by the Flask/Quart application).
- **Destination B**: `Central_Docs/projects/siraugga_framework/<category>/<slug>.md` (Committed into the central authoring repository).

---

[//]: # (SECTION_ID: SIRA-DEV-04_41-SEC-3)
## 3. Why Order Matters in the Editorial Pipeline

The sequence of actions during in-place editing enforces strict safety invariants:

1. **RBAC Clearance Verification First**: The server must verify administrator clearance (`session.get('admin')`) before touching filesystem I/O. Rejecting unauthenticated requests early prevents unauthorized disk inspection.
2. **Path Resolution & Jailing Before File Access**: Slugs must be canonicalized through `resolve_physical_file()` to confirm the path resides within the authorized documentation directory before writing.
3. **Local Write Before Remote Dual-Persistence**: The local web application file must be updated first to guarantee immediate availability for visitors. The secondary write to `Central_Docs` is executed second in a guarded block.
4. **HTML Re-Compilation Before Response Dispatch**: The server parses the newly saved text, applies sensitivity filters, and returns rendered HTML in the HTTP response, allowing the browser to update the reading pane seamlessly without a page reload.

---

[//]: # (SECTION_ID: SIRA-DEV-04_41-SEC-4)
## 4. Beginner Coder Q&A

### Why do we use JSON for `release_schedule.json` instead of SQLite?
**A:** Because JSON files are plain text, human-readable, and trivially version-controlled in Git. When the release schedule changes, the git diff clearly highlights which chapter was published or scheduled without opaque binary database migrations.

### How does the editor handle concurrent edits?
**A:** In our sovereign development model, only the verified super-administrator possesses editorial clearance. The lightweight file-locking mechanisms implemented in `Central_Docs` prevent write collisions across background synchronizations.

---

[//]: # (SECTION_ID: SIRA-DEV-04_41-SEC-5)
## 5. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Foundational Primer** | Introduction to anti-overwhelm release staging and dual-persistence. | [`00H_BEGINNER_GUIDE_TO_RELEASE_SCHEDULING_AND_IN_PLACE_EDITING.md`](/docs/devlog/00H_BEGINNER_GUIDE_TO_RELEASE_SCHEDULING_AND_IN_PLACE_EDITING) |
| **Problem Analysis** | Analysis of cognitive overwhelm and out-of-band web desync traps. | [`01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS) |
| **Source Code Evidence** | Verbatim code excerpts showing staging filters and dual-persistence. | [`02_41_RELEASE_STAGING_AND_IN_PLACE_SURGERY_EVIDENCE.md`](/docs/devlog/02_41_RELEASE_STAGING_AND_IN_PLACE_SURGERY_EVIDENCE) |
| **Diagnostic Verification** | Security audit test traces proving 26/26 staging and editing tests passing. | [`03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS.md`](/docs/devlog/03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS) |
| **From-Scratch Creation Guide** | Line-by-line guide building the release scheduler and in-place editor. | [`05_44_RELEASE_SCHEDULER_AND_IN_PLACE_EDITOR_FROM_SCRATCH.md`](/docs/devlog/05_44_RELEASE_SCHEDULER_AND_IN_PLACE_EDITOR_FROM_SCRATCH) |

</details>
