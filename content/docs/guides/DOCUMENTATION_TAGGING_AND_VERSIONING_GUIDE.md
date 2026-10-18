[//]: # (DOC_ID: SIRA-ARCH-TAG_VERSION_GUIDE | VERSION: v1.0 | SCOPE: ARCHITECTURE)

# Documentation Tagging, Identification, and Invariant Versioning Protocol

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-1)
## 1. Architectural Concept & Core Purpose

In large-scale, multi-repository platforms like the Siraugga Framework, Echoes of the World, and E-Profile, technical documentation quickly scales to hundreds of interconnected chapters. A common failure mode in growing documentation systems is **cross-reference degradation**:
- Files get renamed, renumbered, or moved between directories.
- Chapter titles change to improve readability.
- Inbound links break across project boundaries.
- Updating documentation creates uncertainty about which version is currently deployed.

To permanently solve these challenges while maintaining a distraction-free experience for humans and screen readers, the system implements the **Invariant Identity & Pure Markdown Metadata Standard**.

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-2)
## 2. The Invariant Identity vs. Mutable Version Principle

The foundation of this architecture is the strict decoupling of **Identity** from **Version**:

1. **`DOC_ID` (Persistent Identity)**:
   - Once generated, the canonical `DOC_ID` (such as `ECHO-DOC-04_26` or `SIRA-DEV-01_01`) NEVER changes.
   - It is immutable across file renames, chapter moves, and title modifications.
   - Inbound links, cross-project relational graphs, and automated indices cite the `DOC_ID` rather than fragile filesystem paths.

2. **`VERSION` (Evolution Marker)**:
   - When a document's technical explanation, code excerpts, or sections are updated, the `VERSION` increments (`v1.0` -> `v1.1`).
   - The identity remains invariant while the version signals fresh technical revisions.

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-3)
## 3. Pure CommonMark Reference Tagging (Zero UI & Screen Reader Clutter)

A strict requirement for this system is that **no technical metadata tags may appear in rendered HTML or interrupt screen reader speech streams**.

### Why Not HTML Comments (`<!-- ... -->`)?
While standard HTML comments are hidden from visual browsers, many Markdown sanitizers and custom processors either strip them aggressively, mangle them inside code fences, or leave empty DOM comment nodes that certain screen reader virtual buffers attempt to inspect.

### Why Not Inline HTML Spans (`<span id="...">`)?
Inline HTML elements violate the Clean Markdown protocol, add noise to raw text editing, and can interfere with syntax highlighting and screen reader element grouping.

### The Solution: CommonMark Link Reference Definitions
Metadata is authored using native CommonMark link reference definitions:

```markdown
[//]: # (DOC_ID: {PROJECT}-{COLLECTION}-{IDENTIFIER} | VERSION: v{MAJOR}.{MINOR} | SCOPE: {SCOPE})
```

And for section headings:

```markdown
[//]: # (SECTION_ID: {DOC_ID}-SEC-{SECTION_NUM})
## 1. Section Title
```

**How It Works**:
1. CommonMark parsers (including Python-Markdown, Mistune, and GitHub Flavored Markdown) treat `[//]: # (...)` as an unused reference link definition.
2. The parser **completely drops** the definition during HTML rendering.
3. The resulting HTML DOM contains zero raw tags, brackets, or label clutter.
4. Screen readers read the article text smoothly without hearing metadata noise.

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-4)
## 4. The Standardized Ecosystem Code Registry

Every document belongs to an ecosystem project and a functional collection:

### Project Code Registry
| Code | Ecosystem Project | Architectural Responsibility |
| :--- | :--- | :--- |
| **`ECHO`** | Echoes of the World | Foundational audio game engine, 3D spatial sound trigonometry, NVDA coordinate drivers. |
| **`SIRA`** | Siraugga Framework / DevCore | Sovereign agentic portal, zero-trust RBAC, Quart streaming bus, MCP resolvers, hot-patch sequences. |
| **`EPRF`** | E-Profile Portal | Cyber portfolio hub, profile provisioning, dynamic engine sandbox, admin surgery panel. |
| **`ENCR`** | EncryptMe | Cryptographic tools, PBKDF2/AES-GCM encryption, KMS seed phrase disaster recovery. |
| **`JOSH`** | JOSHY Audio Suite | Headless audio streaming, Nuitka C-compilation, Inno Setup installer packaging, global hotkeys. |
| **`ACCS`** | Accessible Apps Suite | WCAG 2.1 AA comboboxes, accessible video player, pywebview desktop wrapper. |

### Collection Code Registry
| Code | Collection Description | Typical Directory |
| :--- | :--- | :--- |
| **`MAN`** | The Manifesto & Origin Chronicles | `manifesto/` |
| **`DEV`** | 5-Pillar Architecture Devlog Suite | `devlog/` |
| **`TXT`** | Zero-Trust Cybersecurity Textbook | `textbook/`, `Siraugga_Textbook/` |
| **`OPS`** | Siraugga Master Operations Manual | `manual/` |
| **`ARCH`** | High-Level Architecture & Creation Guides | `guides/`, `05_FROM_SCRATCH...` |
| **`CORE`** | Audio Game Engine Core Specifications | `echoes/` |
| **`PORT`** | E-Profile Dedicated Technical Docs | `eprofile/` |
| **`VAULT`** | EncryptMe Cryptographic Specifications | `encrypt_me/` |
| **`PLAY`** | Audio Playback Suite Guides | `audio_suite/`, `Audio_pllayback_suite/` |
| **`BASH`** | Shell Isolation & Environment Guides | `bashbootrc...`, `bashrc...` |
| **`REF`** | Upstream Architecture References | `reference_docs/` |

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-5)
## 5. Heading Anchors and Section Deep-Linking

To enable direct deep-linking to specific subsections across documents without introducing DOM noise:

1. **Markdown Source**: The section identifier is stored right above each H2 (`##`) and H3 (`###`) heading:
   ```markdown
   [//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-5)
   ## 5. Heading Anchors and Section Deep-Linking
   ```

2. **Web Reader Engine (`e_profile/docs_mod.py`)**:
   During document rendering, the reader engine parses the heading hierarchy and attaches the section ID as an HTML element attribute:
   ```html
   <h2 id="SIRA-ARCH-TAG_VERSION_GUIDE-SEC-5">5. Heading Anchors and Section Deep-Linking</h2>
   ```

3. **Accessibility Benefit**:
   - The user and screen reader experience natural, clean heading text: `"5. Heading Anchors and Section Deep-Linking"`.
   - Browser URLs can link directly to `#SIRA-ARCH-TAG_VERSION_GUIDE-SEC-5`.

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-6)
## 6. How We Update Versions Effectively & Consistently (The Automated Engine)

Manual versioning leads to human error—authors forget to increment versions, mistype IDs, or leave sections untagged. To prevent this, the ecosystem includes an automated versioning engine: `scripts/doc_versioner.py`.

### Automated CLI Tool Commands

```bash
# 1. Audit documentation files for tagging compliance and ID collisions
python3 scripts/doc_versioner.py check docs/

# 2. Automatically detect git-modified markdown files and bump their minor version
python3 scripts/doc_versioner.py bump-changed .

# 3. Bump a specific document's minor version (e.g. v1.0 -> v1.1)
python3 scripts/doc_versioner.py bump docs/guides/SECURITY.md

# 4. Bump a major version for a complete architectural rewrite (v1.x -> v2.0)
python3 scripts/doc_versioner.py bump docs/guides/SECURITY.md --major

# 5. Apply canonical tags and section IDs across all files with collision prevention
python3 scripts/doc_versioner.py tag-all --recompute-id docs/
```

### Semantic Bumping Guidelines
1. **Minor Version (`v1.0 -> v1.1`)**:
   - Technical clarifications, typo corrections, updated code snippets.
   - Adding new subsections or diagrams.
   - Updating dependency or compiler flags.
2. **Major Version (`v1.x -> v2.0`)**:
   - Complete rewrite of the architectural module.
   - Deprecation or breaking shift in system protocols.

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-7)
## 7. The 4-Step Release & Sync Workflow

Whenever developers or AI agents finish modifying documentation:

```text
Step 1: Edit Markdown Documents
   │
   ▼
Step 2: Run Automated Version Bump
   │   $ python3 scripts/doc_versioner.py bump-changed .
   │   (Automatically increments VERSION, preserves DOC_ID, tags new headings)
   │
   ▼
Step 3: Regenerate Central Catalog
   │   $ python3 Central_Docs/scripts/sync_to_eprofile.py
   │   (Updates docs_catalog.json and relational graph)
   │
   ▼
Step 4: Verify Zero Collisions & Commit
       $ python3 scripts/doc_versioner.py check docs/
       $ git commit -m "docs: bump updated chapters" && git push
```

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-8)
## 8. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Raugus Virtual File System** | Raugus keys (`devcore.*`) enforce invariant symbolic identity over physical paths, mirroring how `DOC_ID` isolates document references from directory restructuring. | Architecture Guides |
| **Zero-Downtime Hot-Patching** | Hot-patch module recompilation enforces zero-restart updates, mirroring how invariant doc metadata permits live catalog reloading without link breakage. | Architecture Guides |
| **E-Profile Catalog Indexer** | `sync_to_eprofile.py` utilizes invariant `DOC_ID` and section tags to generate multi-dimensional topic graphs. | E-Profile Platform |

</details>

---

[//]: # (SECTION_ID: SIRA-ARCH-TAG_VERSION_GUIDE-SEC-9)
## 9. Beginner Coder Q&A

### Q1: Why do we use CommonMark reference link definitions instead of regular markdown comments?
**A:** Markdown doesn't have an official comment syntax. People often try HTML comments `<!-- comment -->`, but some Markdown renderers include HTML comments in the browser DOM. Screen readers navigating the DOM or reading raw HTML may announce comment text or punctuation. The `[//]: # (...)` syntax is a trick built on standard Markdown link definitions (`[label]: url "title"`). Because the label `//` is never referenced in a link, the Markdown engine discards the entire line during compilation.

### Q2: If I move a document to a different folder, should I change its `DOC_ID`?
**A:** **No.** That is the fundamental purpose of the Invariant Identity principle. The `DOC_ID` acts like a social security number or UUID for the document. Changing it breaks external links, bookmarked URLs, and cross-references.

### Q3: What happens if I forget to bump the version manually?
**A:** Simply run `python3 scripts/doc_versioner.py bump-changed .` before committing. The script queries `git status`, detects every markdown file you modified, increments its version number, and injects section tags for any new headings you wrote.
