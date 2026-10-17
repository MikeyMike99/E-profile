[//]: # (DOC_ID: SIRA-DOC-04_02 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 04.2: Architecture Solutions: The 5-Tier Zero-Trust Hierarchy

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_01_SIRAUGGA_CORE_SYSTEM_ARCHITECTURE.md`](/docs/devlog/04_01_SIRAUGGA_CORE_SYSTEM_ARCHITECTURE)
- **Next Architecture Chapter**: [`04_03_OPAQUE_VFS_AND_AST_DIFFING_ARCHITECTURE.md`](/docs/devlog/04_03_OPAQUE_VFS_AND_AST_DIFFING_ARCHITECTURE)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-1)

In multi-tenant agentic platforms where third-party developers, community modders, and autonomous AI agents collaborate, a single unhardened endpoint can compromise the entire host operating system.

This chapter presents the deep architectural design of Siraugga's **5-Tier Zero-Trust Hierarchy**, detailing role boundaries, cryptographic escrow, and workspace micro-segmentation.

---

## The 5 Architectural Tiers
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-2)

```text
+-------------------------------------------------------------------------------+
| Tier 5: Root Authority (Siraugga Engine & Cryptographic Vault)                |
| Clearance: Super Admin Only                                                   |
| Scope: Live module reloads, cryptographic key signing, server configuration.  |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| Tier 4: FORBIDDEN (Hardware & Version Control Internals)                      |
| Clearance: BLOCKED FOR ALL API ROLES (Hard Barrier)                           |
| Scope: .git/, venv/, .env, private SSH keys, operating system roots.         |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| Tier 3: Admin Telemetry & Diagnostic Logs                                     |
| Clearance: Admin Read-Only                                                    |
| Scope: upgrade.log, server_stdout.log, Master Alert Queue (MAQ) intrusion logs.|
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| Tier 2: Core Engine Code                                                      |
| Clearance: Admin-Gated (Hot-Patch Sequence Only)                              |
| Scope: server.py, agent_manager.py, security_manager.py, project_manager.py.   |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| Tier 1: Safe Workspace (Multi-Tenant Sandboxes)                               |
| Clearance: Public Developers, Game Modders, Subagent Swarms                   |
| Scope: Game assets, dialogue trees, quest JSON, Lua/Python scripts.          |
+-------------------------------------------------------------------------------+
```

---

## Role-Based Access Control (RBAC) Matrix
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-3)

| User Role | Tier 1 (Assets) | Tier 2 (Engine) | Tier 3 (Logs) | Tier 4 (Forbidden) | Tier 5 (Root) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`admin`** | Full Read/Write | In-Memory Patch | Read-Only | Hard-Blocked | Full Authority |
| **`gamedev`** | Full Read/Write | Invisible (403) | Invisible (403) | Hard-Blocked | Denied (403) |
| **`modder`** | Read-Only Assets | Invisible (403) | Invisible (403) | Hard-Blocked | Denied (403) |

---

## Workspace Confinement & The Jailed Agent
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-4)

When an unprivileged developer (`gamedev` or `modder`) prompts the AI:
1. **Isolated CWD**: The `agent_manager` sets `cwd` strictly to their designated project folder (`projects/game_demo/`).
2. **Container Sandboxing**: Enforces `--sandbox` on the CLI runner, preventing terminal commands from inspecting parent directories.
3. **No Skip Permissions**: The dangerous `--dangerously-skip-permissions` flag is permanently stripped for non-admin sessions.

---

## Why Order Matters in Multi-Tier Security
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-5)

1. **Verify Role Clearance Before Directory Listing**:
   - The security manager must filter files *during* the directory traversal loop, not on client delivery. If Tier 2 or Tier 4 files are sent to the client and hidden only via CSS, attackers can inspect raw JSON network payloads.
2. **Hard-Block Tier 4 Before Checking Admin Privileges**:
   - Tier 4 files (`.git/`, `.env`) are hard-blocked *even for administrators* via the web API. Admin updates to git internals must be done via direct terminal access, preventing accidental destruction of git trees via the web UI.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-6)

### Q: Why shouldn't an admin edit `.env` through the web portal?
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-7)
**A:** If an admin account's session token is ever hijacked via cross-site scripting (XSS), an attacker could immediately read all database passwords from `.env`. Blocking Tier 4 across all web APIs enforces defense-in-depth.

### Q: What is the difference between `gamedev` and `modder`?
[//]: # (SECTION_ID: SIRA-DOC-04_02-SEC-8)
**A:** `gamedev` users can write, edit, and create new game assets inside their designated folder. `modder` users have read-only access; they can test and review code, but save operations are blocked by the backend.
