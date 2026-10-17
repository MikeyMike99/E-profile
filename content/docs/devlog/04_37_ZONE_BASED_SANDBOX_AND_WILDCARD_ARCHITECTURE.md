[//]: # (DOC_ID: SIRA-DOC-04_37 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 04.37: Architectural Blueprint: Zone-Based Sandbox Policies & Wildcard Masking

## Executive Summary
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-1)
This blueprint details the architectural solution for filesystem access control in DevCore, transitioning from fragile file-level rules to robust **Zone-Based Sandbox Policies (ZSP)** and **Semantic Wildcard Masking**, as codified in Chapters 14 through 27 of the Siraugga Security Textbook.

---

## 1. Zone-Based Security Topology
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-1)

```
Incoming File Request (Relative Path):
                     │
                     ▼
Canonical Path Jail (`os.path.realpath`) ──► Outside Workspace? ──► [403 Forbidden]
                     │
                     ▼
Directory Segment Inspection (`parts = norm_path.split('/')`)
                     │
     ├── In `FORBIDDEN_NAMES` or `startswith('.')`? ──► TIER_FORBIDDEN (Hard Block)
     │
     ├── In `CORE_DIRECTORIES` (`core/`, `security/`)? ──► TIER_CORE_ENGINE (Admin Only)
     │
     ├── Matches `*.log`? ──────────────────────────► TIER_ADMIN_LOG (Admin Read-Only)
     │
     └── Valid Extension in `playground/<proj>`? ──► TIER_SAFE_WORKSPACE (Read/Write)
```

---

## 2. Core Functional Layers
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-2)

### 1. The Canonical Jail (`resolve_safe_path`)
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-1)
- Resolves all symlinks and relative tokens (`.`, `..`) to absolute physical paths.
- Enforces strict string-prefix verification to ensure the target path cannot escape the base workspace root.

### 2. The Directory-Level Tiering Classifier (`classify_file`)
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-2)
- Replaces individual file-name matching with structural path hierarchy analysis.
- Treats core directories (`core/`, `security/`, `plugins/`, `scripts/`) as atomic security zones; any file inside these zones automatically inherits Tier 5 administrative clearance.
- Eliminates subfolder injection vulnerabilities.

### 3. The Strict Implicit Deny Gate
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-3)
- Enforces an explicit whitelist of allowed file extensions (`.py`, `.json`, `.lua`, `.js`, `.ts`, `.md`, `.txt`, `.html`, `.css`).
- Any unclassified file, unknown extension, or executable binary (.exe, .so, .dll) is rejected by default.

---

## 3. Why Order Matters in Path Jailing
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-3)
1. **Canonicalize Prior to Inspection**: You must collapse `..` path tokens before running tier classification.
2. **Directory Checks Prior to Extension Checks**: A directory restriction must always take precedence over an allowed file extension.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-4)

### Why is path traversal so dangerous?
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-2)
If path traversal is not blocked, a user or agent could ask for `../../../../etc/passwd` or `../../.env` and read database passwords, API keys, or system credentials.

### What is a Security Zone?
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-3)
A Security Zone is a group of files and directories that share the exact same trust level and permissions, making security rules simple, predictable, and scalable.

---

## 5. Reusable Quick-Start Recipe (2-Minute Deployment)
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-5)
1. Initialize Security Manager: `sec = SecurityManager()`.
2. Wrap all file operations: `safe_path = sec.resolve_safe_path(user, requested_path)`.
3. Read/write safely using `safe_path`.

---

## 6. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-04_37-SEC-6)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_41_ZONE_BASED_POLICIES_AND_SEMANTIC_WILDCARD_TRAPS.md`](/docs/devlog/01_41_ZONE_BASED_POLICIES_AND_SEMANTIC_WILDCARD_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_37_ZONE_BASED_SANDBOX_POLICY_EVIDENCE.md`](/docs/devlog/02_37_ZONE_BASED_SANDBOX_POLICY_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_34_ZONE_SANDBOX_AND_WILDCARD_EVALUATION_LOGS.md`](/docs/devlog/03_34_ZONE_SANDBOX_AND_WILDCARD_EVALUATION_LOGS)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_40_ZONE_BASED_SANDBOX_FILTER_FROM_SCRATCH.md`](/docs/devlog/05_40_ZONE_BASED_SANDBOX_FILTER_FROM_SCRATCH)
