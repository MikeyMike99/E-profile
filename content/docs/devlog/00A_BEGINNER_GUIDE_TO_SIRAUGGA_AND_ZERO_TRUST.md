[//]: # (DOC_ID: SIRA-DOC-00A | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 00A: Beginner Guide to Siraugga & Zero-Trust Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Next Primer**: [`00B_BEGINNER_GUIDE_TO_ACCESSIBLE_WEBSOCKET_STREAMING.md`](/docs/devlog/00B_BEGINNER_GUIDE_TO_ACCESSIBLE_WEBSOCKET_STREAMING)

---

## What is Siraugga?
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-1)

**Siraugga** is an autonomous, event-driven development engine and accessible web portal. It was created to bridge complex AI coding agents to web browsers, game development environments, and third-party modders without requiring server restarts or compromising host security.

### The Name and Philosophy
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-2)
In the developmental chatlogs, the system was initially called "The Agent" or "Antigravity." As the security architecture deepened, a generic name was no longer sufficient. The system required a name representing sovereign authority and defensive autonomy.

The name **Siraugga** is an architectural neologism:
- **SIR (High Privilege)**: Represents Root / Tier 5 administrator authority.
- **AU (Automation & Autonomy)**: Represents self-governing task execution without human micro-management.
- **ROG (Rogue Defense)**: Represents defensive autonomy—the ability to dynamically quarantine rogue processes and reject suspicious operations.
- **G (Going Forward)**: Momentum and continuous progress in development pipelines.
- **A (Advancements)**: Modern integration of next-generation concepts (MCP plugins, opaque VFS, AST hot-patching).

---

## The 5-Tier Zero-Trust Security Model
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-3)

Zero-Trust means **"never trust, always verify."** Even if an AI agent is running locally, it must never be granted blind access to system files, source code, or private keys.

Siraugga classifies all files and directories into five strict tiers:

```text
+-----------------------------------------------------------------+
| Tier 5: Root Authority (Siraugga Engine, Cryptographic Keys)     |
+-----------------------------------------------------------------+
| Tier 4: FORBIDDEN (Git Internals, Virtual Envs, .env Secrets)   |
+-----------------------------------------------------------------+
| Tier 3: Admin Logs (Execution traces, upgrade.log, audit SIEM)  |
+-----------------------------------------------------------------+
| Tier 2: Core Engine Code (server.py, agent_manager.py)          |
+-----------------------------------------------------------------+
| Tier 1: Safe Workspace (Game scripts, quests, JSON assets, docs)|
+-----------------------------------------------------------------+
```

### Tier Descriptions
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-4)
1. **Tier 1 (Safe Workspace)**: Safe for third-party modders and junior developers. Contains project assets, quests, dialogues, and configs.
2. **Tier 2 (Core Engine)**: The Python backend files. Accessible strictly to trusted engineers through validated hot-patches.
3. **Tier 3 (Admin Logs)**: Diagnostic traces and daemon logs. Read-only for administrators.
4. **Tier 4 (Forbidden)**: System-critical internals (`.git/`, `venv/`, `.env`, private SSH keys). Hard-blocked for all roles.
5. **Tier 5 (Root Authority)**: Full administrative clearance to reload the engine and manage high-level security keys.

---

## Plain-English Glossary
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-5)

- **Zero-Trust**: A security architecture where every request is authenticated and authorized against security policies before being fulfilled.
- **Subprocess**: An independent program launched and supervised by a parent program (e.g., Python launching an agent CLI).
- **RBAC (Role-Based Access Control)**: Restricting access to files and endpoints based on whether the user is an `admin`, `developer`, or `modder`.
- **Hot-Patching**: Swapping running code in memory without restarting the server or dropping active WebSocket connections.
- **Opaque VFS**: A virtual file system where real file paths are hidden behind abstract keys (e.g., `devcore.server` instead of physical paths).

---

## Why Order Matters in Zero-Trust Initialization
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-6)

1. **Firewall & RBAC Rules Before Subprocess Launch**:
   - The security manager must initialize and lock file boundaries *before* any AI subprocess or client connects. If an agent starts before rules are enforced, it could read or modify sensitive files during initialization.
2. **Path Sanitization Before File Operations**:
   - Path traversal defenses (`resolve_safe_path`) must execute *before* calling Python's `open()` or `os.path.exists()`. Inspecting files with unvalidated input exposes systems to path traversal exploits (`../../etc/passwd`).
3. **Authentication Before Streaming**:
   - WebSockets must validate the client's session token during the handshake *before* establishing an event stream. Unauthenticated streams leak terminal events.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-7)

### Q: Why not let the AI agent read whatever file it wants on my computer?
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-8)
**A:** When AI agents process complex prompts or download third-party community packages, they can be manipulated by prompt injections or malicious scripts. Restricting the agent to Tier 1 ensures it cannot accidentally delete your operating system files or expose private passwords.

### Q: What is the difference between Tier 2 (Core Engine) and Tier 4 (Forbidden)?
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-9)
**A:** Tier 2 engine files (`server.py`, `agent_manager.py`) can be inspected and updated by administrators via zero-restart hot-patches. Tier 4 files (`.git/`, `.env`, `venv/`) are never touched by API calls because modifying them risks repository corruption or credential leaks.

### Q: Why is this system called an "Autonomous" agent if it has so many rules?
[//]: # (SECTION_ID: SIRA-DOC-00A-SEC-10)
**A:** True autonomy requires guardrails. Just like an autopilot on an airplane needs strict flight corridors to operate safely without crashing, Siraugga needs deterministic security boundaries so it can solve tasks autonomously without human oversight.
