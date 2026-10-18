[//]: # (DOC_ID: SIRA-DEV-00H | VERSION: v1.0 | SCOPE: DEVLOG)

# Pillar 00H: Beginner Guide to Release Scheduling & In-Place Editing

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Companion Problem Breakdown**: [`../01_PROBLEMS_ENCOUNTERED/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS)

---

[//]: # (SECTION_ID: SIRA-DEV-00H-SEC-1)
## 1. What Is Release Scheduling & In-Place Editing?

When developers complete a massive technical project, the natural temptation is to publish everything simultaneously. In our case, the Siraugga Framework, Echoes of the World, and E-Profile archive encompasses over 300 technical chapters, forensic logs, and architecture manuals.

However, publishing 300+ documents at once introduces a severe user experience failure: **visitor cognitive overwhelm**. When prospective employers, technical recruiters, or fellow developers land on a documentation portal and see an endless wall of hundreds of complex blueprints, they suffer choice paralysis and often leave without reading a single word.

**Release Scheduling and In-Place Editing** is the architectural solution:
1. **Curated Rollout**: The platform maintains a curated release schedule (`release_schedule.json`) that presents only foundational, essential chapters to public visitors, while holding experimental drafts in reserve.
2. **Scheduled Publication**: Chapters can be scheduled for future release dates, creating an engaging, paced publication rollout.
3. **In-Place Editorial Control**: When the administrator reviews documentation in the browser, they can toggle release status, edit raw Markdown in place, add new chapters, or safely archive files with zero server restarts or terminal intervention.

```
Visitor Experience (Curated & Welcoming):
[Public Visitor] ──► [Curated Catalog: 19 Foundational Chapters] ──► Clear, Focused Reading!

Admin Experience (Full Sovereignty):
[Admin Login] ──► [Full Catalog: 300+ Chapters] ──► [In-Place Editor & Release Scheduler]
```

---

[//]: # (SECTION_ID: SIRA-DEV-00H-SEC-2)
## 2. The Anti-Overwhelm Staging Concept

Rather than treating documentation as a binary choice between "completely secret" and "dumped publicly all at once," our system implements three distinct document states in `release_schedule.json`:

1. **`published`**:
   - The document is live and accessible to all public visitors.
   - Listed in the public sidebar and search catalog.
2. **`draft`**:
   - Visible and editable exclusively by logged-in administrators (Tier 5).
   - Completely invisible to public visitors in sidebar navigation and search results.
3. **`scheduled`**:
   - Assigned an ISO release timestamp (e.g. `2026-11-01T00:00:00`).
   - Remains in draft mode until the system clock passes the release timestamp, after which it automatically becomes visible to visitors.
   - If a visitor navigates directly to a scheduled document URL, they are greeted by an accessible, informative holding notice detailing when the chapter will be published.

---

[//]: # (SECTION_ID: SIRA-DEV-00H-SEC-3)
## 3. Dual-Persistence In-Place Markdown Surgery

A common failure in web-based documentation editors is **storage desynchronization**. If an author edits a file through a web portal, the changes are saved to the web server's local disk. However, if the development repository (`Central_Docs`) is hosted elsewhere, the next automated build or git sync will overwrite the web server edits with old repository code.

To permanently prevent this, our in-place editor implements **Dual-Persistence Writing**:
1. When the admin clicks **Save Document**, the backend writes the updated content to the web application target path (`e_profile/content/docs/...`).
2. Simultaneously, the backend identifies the corresponding source path in the central authoring repository (`Central_Docs/projects/...`) and writes the changes there as well.
3. Both repositories remain 100% in sync, ensuring zero work is lost during future sync passes.

---

[//]: # (SECTION_ID: SIRA-DEV-00H-SEC-4)
## 4. Beginner Coder Q&A

### How does the server know which chapters to hide from public visitors?
**A:** When `docs_mod.py` loads the documentation catalog, it checks the user's session. If the user is not logged in as admin, the `filter_catalog_for_viewer()` function filters out any chapter whose `publish_status` is not `published` or whose scheduled release date is in the future.

### What happens if an admin deletes a chapter by mistake?
**A:** The deletion endpoint (`/api/admin/delete`) does not use destructive permanent deletion (`os.remove`). Instead, it moves the markdown file to a timestamped archive folder (`content/docs/.archive/YYYYMMDD_HHMMSS_<slug>.md`), allowing instantaneous recovery if needed.

---

[//]: # (SECTION_ID: SIRA-DEV-00H-SEC-5)
## 5. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Problem Analysis** | Traps of cognitive overwhelm, URL bypasses, and dual-sync race conditions. | [`01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS.md`](/docs/devlog/01_45_VISITOR_COGNITIVE_OVERWHELM_AND_IN_PLACE_EDIT_RACE_TRAPS) |
| **Source Code Evidence** | Verbatim route handlers and scheduling logic in `docs_mod.py`. | [`02_41_RELEASE_STAGING_AND_IN_PLACE_SURGERY_EVIDENCE.md`](/docs/devlog/02_41_RELEASE_STAGING_AND_IN_PLACE_SURGERY_EVIDENCE) |
| **Diagnostic Verification** | Multi-stage security and staging audit logs (26/26 PASS). | [`03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS.md`](/docs/devlog/03_38_RELEASE_SCHEDULE_AND_IN_PLACE_SURGERY_AUDIT_LOGS) |
| **Architectural Blueprint** | End-to-end data flow of visitor staging and dual-persistence. | [`04_41_CURATED_RELEASE_SCHEDULING_AND_DUAL_PERSISTENCE_ARCHITECTURE.md`](/docs/devlog/04_41_CURATED_RELEASE_SCHEDULING_AND_DUAL_PERSISTENCE_ARCHITECTURE) |
| **From-Scratch Creation Guide** | Step-by-step tutorial building the release scheduler and editor from scratch. | [`05_44_RELEASE_SCHEDULER_AND_IN_PLACE_EDITOR_FROM_SCRATCH.md`](/docs/devlog/05_44_RELEASE_SCHEDULER_AND_IN_PLACE_EDITOR_FROM_SCRATCH) |

</details>
