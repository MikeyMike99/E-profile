# Automated Security & Tagging Audit Engine

The **Automated Security & Tagging Audit Engine** (`security_audit.py`) provides an automated, regression-resistant verification test suite for the E-Profile Web Portal and the Central Documentation Vault. It mirrors the Zero-Trust security auditing framework established in DevCore.

---

## 1. Audit Engine Overview

The audit suite executes **26 automated checks across 6 distinct security and operational stages** to guarantee that visitor access boundaries, editorial permissions, sensitive information redactions, and metadata tags are strictly maintained.

### Key Capabilities
- **In-Memory & Headless Execution**: Runs directly against the in-process Flask application context with zero port conflicts or background daemon requirements.
- **Granular Stage Isolation**: Supports selective stage verification via the `--stage <1-6>` flag for rapid targeted debugging.
- **Machine-Readable Diagnostics**: Provides a `--json` output mode for automated SIEM pipelines and CI/CD validation.
- **The Clean Workspace Protocol**: Synthetic canary files and release entries created during Stage 5 are automatically scrubbed upon test completion.

---

## 2. The 6 Automated Audit Stages

### Stage 1: Role-Based Access Control (RBAC) & Endpoint Authorization
Verifies that all server endpoints and DOM elements enforce strict role segregation:
- **RBAC-01**: Unauthenticated visitors are rejected with HTTP 403 when attempting to access the release scheduling endpoint (`POST /docs/api/admin/schedule`).
- **RBAC-02**: Unauthenticated visitors are rejected with HTTP 403 on the in-place file save endpoint (`POST /docs/api/admin/save`).
- **RBAC-03**: Unauthenticated visitors are rejected with HTTP 403 on the chapter creation endpoint (`POST /docs/api/admin/create`).
- **RBAC-04**: Unauthenticated visitors are rejected with HTTP 403 on the chapter delete/archive endpoint (`POST /docs/api/admin/delete`).
- **RBAC-05**: Visitor DOM verification confirms that no administrative components (`#modal-schedule`, `#modal-new-chapter`, `#admin-review-toolbar`, or `<textarea id="admin-raw-textarea">`) leak into unauthenticated client responses.
- **RBAC-06**: Admin session authentication confirms that full editorial controls, modals, and toolbars render upon login.

### Stage 2: Path Traversal (LFI) & Boundary Isolation
Guarantees that URL parameters and filesystem resolvers cannot escape the assigned workspace root:
- **TRAV-01**: Relative navigation sequences (`../`, encoded slashes `%2f`, and null byte attempts) in chapter routes are rejected safely.
- **TRAV-02**: The physical file resolution engine (`resolve_physical_file`) prevents directory traversal escapes outside the documentation root.
- **TRAV-03**: The admin save endpoint enforces path sanitization to prevent arbitrary server write exploits.

### Stage 3: Release Schedule & Anti-Overwhelm Visitor Staging
Protects public visitors from being overwhelmed with hundreds of raw technical documents by enforcing staged public rollouts:
- **STAG-01**: Validates `release_schedule.json` schema consistency, ensuring `"default_policy": "draft"`.
- **STAG-02**: Confirms that public visitor catalogs expose strictly published chapters (19 foundational chapters), hiding the remaining draft chapters.
- **STAG-03**: Direct URL access to an unreleased draft chapter serves an accessible holding notice rather than leaking confidential drafts.
- **STAG-04**: Time-based release verification guarantees that future-scheduled chapters remain hidden until the target date passes, unlocking automatically thereafter.

### Stage 4: Metadata Classification & 100% Tagging Integrity
Verifies complete categorization, security tiering, and relational graph consistency across all 303 chapters:
- **TAG-01**: 100% of chapters possess explicit Project Ownership tags (`siraugga`, `audio_suite`, `accessible_apps`, `echoes`, `encrypt_me`, `eprofile`).
- **TAG-02**: 100% of chapters are classified into topic taxonomy buckets (`security`, `infrastructure`, `accessibility_ui`, `workflow`, `cryptography`, `limitations`, `origin_story`, `changelog`).
- **TAG-03**: 100% of documents follow canonical `<PROJECT>-<COLLECTION>-<SLUG>` identification formatting.
- **TAG-04**: 100% of documents are classified into Security Clearance Tiers (Tier 1–3 Public, Tier 4 Proprietary, Tier 5 Admin).
- **TAG-05**: Dynamic sensitivity filters successfully sanitize proprietary and secret sections when rendered for Tier 1 public visitors while preserving verbatim content for Tier 5 admins.
- **TAG-06**: Every link in the automated cross-reference graph resolves to a valid, existing chapter in the multi-project catalog.

### Stage 5: In-Place Editing, File Creation & Safe Archiving
Validates live editorial management directly from the server:
- **EDIT-01**: Chapter creation endpoint generates a valid markdown document with auto-suggested slug formatting.
- **EDIT-02**: The created chapter is written physically to server disk storage.
- **EDIT-03**: The in-place raw markdown editor writes updates to disk and returns freshly rendered HTML without requiring server restarts.
- **EDIT-04**: Quick-toggle and schedule updates modify the active release status in real time.
- **EDIT-05**: Chapter deletion moves the physical file into `.archive/` with a timestamp and unregisters it from the active release registry.

### Stage 6: Multi-Destination Dual Persistence & Sync Consistency
Ensures alignment across git repositories:
- **SYNC-01**: Validates that `release_schedule.json` entries in `e_profile/content/docs/` match `Central_Docs/release_schedule.json`.
- **SYNC-02**: Verifies that `Central_Docs/scripts/sync_to_eprofile.py` compiles cleanly without AST syntax errors.

---

## 3. Running the Audit Suite

### Standard Full Audit
From the `e_profile` root directory:
```bash
python3 security_audit.py
```
Or from the `Central_Docs` root directory:
```bash
python3 scripts/audit_docs.py
```

### Verbose Diagnostic Mode
Shows line-by-line inspection details for every pass and fail:
```bash
python3 security_audit.py --verbose
```

### Targeted Single-Stage Execution
Execute any single stage (1 through 6):
```bash
python3 security_audit.py --stage 1  # RBAC & Authorization
python3 security_audit.py --stage 3  # Release Staging & Schedules
python3 security_audit.py --stage 4  # Metadata & Tagging Integrity
```

### Machine-Readable JSON Export
Output structured JSON for test logs or automated compliance monitors:
```bash
python3 security_audit.py --json
```
