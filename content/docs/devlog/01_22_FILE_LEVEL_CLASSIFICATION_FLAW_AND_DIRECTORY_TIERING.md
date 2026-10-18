[//]: # (DOC_ID: SIRA-DEV-01_22 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 01_22: File-Level Classification Flaw & Directory Tiering

In zero-trust role-based security, classifying files purely by filename or extension creates dangerous loopholes. This chapter reveals how flat file-matching allowed sandboxed agents to tamper with nested core configuration files, and how **Directory-Level Tiering** and **API Decoupling via Skills** restored strict isolation.

---

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-1)
## What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-1)

During an audit of the security manager's file classifier (`classify_file()`), a severe privilege escalation vector was uncovered:
- **Nested Core File Exposure**: A non-admin agent (role: `gamedev` / Tier 3) was able to edit `core/ui_config.json` and `templates/index.html` because the classifier only checked a flat list of filenames (`server.py`, `agent_manager.py`).
- **The Extension Trap**: Because files ended in `.json` or `.html`, the classifier assumed they were benign workspace data files (`TIER_SAFE_WORKSPACE`), completely ignoring that they resided inside the protected engine directory tree!
- **The Subagent Dilemma**: When the engine sealed off all core files, sandboxed subagents broke because they could no longer read backend code to learn how to save exams or media files.

---

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-2)
## Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-2)

The breakdown occurred due to shallow path inspection and missing API abstraction:
- **Flat List Matching**: The classifier performed simple equality checks (`if os.path.basename(path) in CORE_FILES:`). It did not evaluate parent directory components.
- **Unchecked Namespaces**: A file path is a hierarchy. If any parent directory is restricted, the entire subtree must inherit that restriction.
- **Direct Code Dependency**: Earlier plugins relied on the agent reading Python files directly to discover functions rather than communicating across an abstracted API boundary.

```
Vulnerable Flat Matching:
Path: core/ui_config.json ---> Checks basename: ui_config.json ---> Not in CORE_FILES ---> ALLOWED (Breach!)

Hardened Directory Tiering:
Path: core/ui_config.json ---> Scans parent parts: ['core'] ---> In CORE_DIRECTORIES ---> TIER_CORE_ENGINE (Blocked!)
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-3)

In recursive path classification, top-down directory validation guarantees containment:
1. **Resolve Canonical Realpath First**: Resolve symlinks using `os.path.realpath()` before checking directory parts to defeat symlink bypasses.
2. **Scan Directory Namespaces Before Extensions**: Check if any parent folder matches `CORE_DIRECTORIES` before examining file extensions.
3. **Enforce API Contracts (Skills) Over File Access**: Provide sandboxed agents with Antigravity Skills defining JSON schemas and HTTP endpoints instead of granting read access to server code.

---

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-4)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-5)

### What is Directory-Level Tiering?
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-5)
Instead of memorizing hundreds of individual file names, the security engine marks entire directories (like `core/` and `security/`) as forbidden zones. Any file created inside those folders automatically becomes protected.

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-6)
### How does a sandboxed agent work without seeing server code?
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-6)
Through **API Decoupling**. We give the agent an Antigravity Skill that explains: *"Send a POST request to `/api/plugin/exam/save` with this specific JSON format."* The agent doesn't need to know how the server works; it just sends the data.

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-7)
### What is the advantage of relocating workspaces to `playground/`?
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-7)
Putting user game projects into a dedicated `playground/` folder physically separates user files from the engine codebase, making accidental path overlap impossible.

---

[//]: # (SECTION_ID: SIRA-DEV-01_22-SEC-8)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-01_22-SEC-8)
- To see the primary source code implementation of directory tiering, read [`02_SOURCE_EVIDENCE/02_17_DIRECTORY_TIERING_AND_API_CONTRACT_EVIDENCE.md`](/docs/devlog/02_17_DIRECTORY_TIERING_AND_API_CONTRACT_EVIDENCE).
- To inspect diagnostic audit logs verifying directory tiering blocks, visit [`03_DIAGNOSTIC_TESTS/03_16_DIRECTORY_TIERING_AND_SANDBOX_JAIL_AUDIT_LOGS.md`](/docs/devlog/03_16_DIRECTORY_TIERING_AND_SANDBOX_JAIL_AUDIT_LOGS).
- To build the complete zero-trust RBAC engine from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH).
