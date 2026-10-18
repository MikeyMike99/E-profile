[//]: # (DOC_ID: SIRA-DEV-04_16 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 04_16: Autonomous Self-Healing Boot Architecture

An architectural guide to Siraugga's **Pre-Flight Supervisor & 3-Tier Self-Healing Loop**—ensuring continuous server availability by detecting syntax errors, performing instant rollbacks, and spawning headless auto-repair agents.

---

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-1)
## Architectural Overview & Topology
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-1)

In conventional web development, a single missing colon or unclosed parenthesis in a server file crashes the process at startup, leaving users with a dead connection.

Siraugga solves this via a **Dual-Layer Gateway and 3-Tier Self-Healing Pipeline**:

```
┌─────────────────────────────────────────────────────────────┐
│                 SUPERVISOR GATEWAY (PORT 5000)              │
│  • Always active. Never dies.                               │
│  • Proxies traffic to internal worker on Port 5001          │
│  • Serves "Self-Healing in Progress" during restarts        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Triggers Pre-Flight Check
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 PHASE 1: PRE-FLIGHT COMPILATION             │
│  • Runs py_compile over core engine modules                 │
│  • Promotes validated staged patches from core/patches/     │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
         All Files Valid                Syntax Error Caught
               │                               │
               ▼                               ▼
    ┌──────────────────────┐        ┌─────────────────────────────┐
    │     PHASE 2: BOOT    │        │   TIER-1: INSTANT RESTORE   │
    │  Launch Quart Worker │        │  • Restores from backups/   │
    │   on Port 5001       │        │  • Execution time: <5ms     │
    └──────────────────────┘        └──────────────┬──────────────┘
                                                   │
                                     Backup Missing or Corrupted
                                                   │
                                                   ▼
                                    ┌─────────────────────────────┐
                                    │ TIER-2: AI AUTO-REPAIR LOOP │
                                    │ • Spawns headless agent     │
                                    │ • Passes exact crash trace  │
                                    │ • AI rewrites broken syntax │
                                    │ • Gateway re-runs Phase 1   │
                                    └─────────────────────────────┘
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-2)
## The 3 Tiers of Self-Healing Explained
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-2)

1. **Pre-Flight Staging Quarantine**:
   - Any patch staged in `core/patches/` is compiled before it touches live files. If invalid, it is quarantined immediately.
2. **Tier-1 Deterministic Rollback (<5ms)**:
   - If an existing live module fails compilation, the gateway copies the last known working backup from `core/backups/`.
3. **Tier-2 Autonomous AI Repair**:
   - If no backup is available, the supervisor spawns a headless CLI agent with the command:
     `agy "Fix the syntax error in core/server.py based on this traceback: <TRACEBACK>"`
   - The agent repairs the file, exits, and the supervisor re-verifies the fix before booting.

---

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-3)

In autonomous self-healing, recovery sequence protects stability:
1. **Quarantine Staged Patches Before Core Engine Scan**: Broken patches must be filtered out first so they cannot contaminate the engine scan.
2. **Attempt Tier-1 Backup Restore Before AI Dispatch**: A backup copy restores in 3 milliseconds without consuming AI tokens. Always exhaust deterministic recovery before invoking LLM agents.
3. **Bind External Proxy Before Starting Internal Worker**: Running Port 5000 first ensures web clients receive informative status updates even if Port 5001 is repairing itself.

---

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-4)
## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-4)

To run pre-flight diagnostics and self-healing before starting your server:

```python
from core.bootstrap_gateway import run_preflight_checks

def safe_start_application():
    # Step 1: Run pre-flight diagnostics
    results = run_preflight_checks(spawn_agent=True, quiet=False)
    
    # Step 2: Check health verdict
    if not results.get("failed_files"):
        print("[Boot] Pre-flight passed! Starting live web service...")
        # Step 3: Launch Quart / Hypercorn ASGI server
        import hypercorn.asyncio
        # hypercorn.asyncio.run(...)
    else:
        print("[Boot ERROR]: Self-healing could not resolve syntax errors.")
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-6)

### What is a "Headless Agent"?
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-6)
A headless agent is an AI that runs entirely from the command line without opening a browser or chat window. It receives a task, modifies the code, and exits silently.

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-7)
### Will this loop forever if the AI can't fix the bug?
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-7)
No. The supervisor enforces a strict retry limit (`max_retries = 2`). If the file fails compilation twice, it halts and requests human assistance.

---

[//]: # (SECTION_ID: SIRA-DEV-04_16-SEC-8)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_16-SEC-8)
- To understand why server crashes prompted this self-healing architecture, read [`01_PROBLEMS_ENCOUNTERED/01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES.md`](/docs/devlog/01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES).
- To inspect primary source citations of the pre-flight supervisor, view [`02_SOURCE_EVIDENCE/02_16_SELF_HEALING_BOOTSTRAP_AND_TRACEBACK_REPAIR_EVIDENCE.md`](/docs/devlog/02_16_SELF_HEALING_BOOTSTRAP_AND_TRACEBACK_REPAIR_EVIDENCE).
- To build the complete self-healing pre-flight supervisor from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_18_PREFLIGHT_AUTONOMOUS_SELF_HEALER_FROM_SCRATCH.md`](/docs/devlog/05_18_PREFLIGHT_AUTONOMOUS_SELF_HEALER_FROM_SCRATCH).
