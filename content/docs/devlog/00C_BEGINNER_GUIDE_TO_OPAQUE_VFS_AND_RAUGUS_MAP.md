[//]: # (DOC_ID: SIRA-DEV-00C_BEGINNER_GUIDE | VERSION: v1.0 | SCOPE: DEV)

# Pillar 00C: Beginner Guide to Opaque Virtual File Systems & Raugus Map

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Primer**: [`00B_BEGINNER_GUIDE_TO_ACCESSIBLE_WEBSOCKET_STREAMING.md`](/docs/devlog/00B_BEGINNER_GUIDE_TO_ACCESSIBLE_WEBSOCKET_STREAMING)
- **Next Primer**: [`00D_BEGINNER_GUIDE_TO_EPHEMERAL_PLUGINS_AND_CONTAINERS.md`](/docs/devlog/00D_BEGINNER_GUIDE_TO_EPHEMERAL_PLUGINS_AND_CONTAINERS)

---

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-1)
## What is an Opaque Virtual File System (VFS)?
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-1)

In standard programming, when you want to read or write a file, you pass a physical disk path like `/home/user/app/server.py` or `C:\Projects\app\server.py`.

In an autonomous AI environment, exposing physical paths is dangerous:
1. **Information Disclosure**: Physical paths reveal the username, operating system version, drive letters, and directory layout to the AI model and third-party prompts.
2. **Directory Traversal**: Physical paths invite relative escape attacks (`../../etc/passwd`).
3. **Host Fingerprinting**: Attackers can probe for system binaries by guessing path strings.

An **Opaque Virtual File System (VFS)** completely hides physical paths behind abstract, cryptographic keys.

---

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-2)
## The Raugus Map VFS Architecture
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-2)

Siraugga enforces the **Raugus Protocol**: no client or subagent ever sees or requests a real disk path. Instead, every module, function, and variable is cataloged in the **Raugus Map** under an opaque key:

```text
+-------------------------------------------------------------------------------+
|                             Client / Agent Request                            |
|             Request Key: "devcore.core.server.py::ws_endpoint"                |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                          Raugus Resolver Gatekeeper                           |
|  1. Key Lookup: Does key exist in raugus_map.json?                            |
|  2. Tier Clearance: Does caller have Tier 5 Admin clearance?                  |
|  3. AST Lock Check: Is the symbol locked as Read-Only?                        |
|  4. Sensitive Vault Boundary: Does it touch private credentials?              |
+---------------------------------------+---------------------------------------+
                                        |
                    +-------------------+-------------------+
                    | (Granted)                             | (Denied)
                    v                                       v
+---------------------------------------+   +-----------------------------------+
| Read/Write AST Symbol Content         |   | Throw KeyError / PermissionError  |
| (Physical path never returned)        |   | (Zero host inspection)            |
+---------------------------------------+   +-----------------------------------+
```

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-3)
### Key Formats
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-3)
- **Module Key**: `devcore.core.server.py`
- **Function / Class Symbol Key**: `devcore.core.server.py::ws_endpoint`
- **Variable Key**: `devcore.security.security_manager.py::TIER_SAFE_WORKSPACE`

---

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-4)
## Plain-English Glossary
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-4)

- **Virtual File System (VFS)**: An abstraction layer on top of a more concrete storage system, allowing applications to access files uniformly without knowing physical disk geometry.
- **Opaque Key**: A label or token that does not reveal any details about the physical resource it points to.
- **Abstract Syntax Tree (AST)**: A mathematical tree representation of Python source code structure, allowing the system to lock individual functions rather than entire files.
- **Micro-Segmentation**: Dividing access boundaries into granular units (e.g., an agent can edit function `A` but is blocked from touching function `B` in the same file).

---

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-5)
## Why Order Matters in Opaque VFS Lookups
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-5)

1. **Key Verification Before Path Resolution**:
   - The Resolver must check if the requested key exists in the internal registry *before* looking up any disk coordinates. If a requested key is missing, it immediately throws `KeyError` without touching the filesystem.
2. **Permission Clearance Before AST Splicing**:
   - The user's cryptographic tier must be verified *before* inspecting function line numbers. Unprivileged callers must never learn whether a sensitive symbol exists.
3. **AST Syntax Validation Before Committing Writes**:
   - When an agent updates code via `write_by_key`, the new code must compile cleanly via `ast.parse()` *before* being written to disk. Broken syntax is rejected at the gate.

---

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-7)

### Q: Does the Raugus Resolver replace Git?
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-7)
**A:** No. Git tracks version history across time. The Raugus Resolver enforces spatial security in real time, preventing unauthorized agents from reading or modifying locked symbols while the application is running.

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-8)
### Q: What happens if an agent tries to pass `../../etc/shadow` to `read_by_key`?
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-8)
**A:** The Resolver looks for `../../etc/shadow` in `raugus_map.json`, finds no matching key, and throws an immediate `KeyError`. The physical Linux filesystem is never interrogated.

[//]: # (SECTION_ID: SIRA-DEV-00C_BEGINNER_GUIDE-SEC-9)
### Q: Can an agent edit one function in a file while another is locked?
[//]: # (SECTION_ID: SIRA-DOC-00C_BEGINNER_G-SEC-9)
**A:** Yes! Because Raugus maps symbols down to exact line spans via Python's AST parser, function-level write locks permit safe edits to helper functions while protecting core security algorithms in the same file.
