# Pillar 04.6: Architecture Solutions: Pre-Flight Self-Healing Supervisor

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_05_SOVEREIGN_AI_AND_OFFLINE_BROKER_RECIPES.md`](/docs/devlog/04_05_SOVEREIGN_AI_AND_OFFLINE_BROKER_RECIPES)
- **Next Architecture Chapter**: [`04_07_THE_VOICE_OF_SIRAUGGA_CINEMATIC_TTS_ARCHITECTURE.md`](/docs/devlog/04_07_THE_VOICE_OF_SIRAUGGA_CINEMATIC_TTS_ARCHITECTURE)

---

## Overview

In mission-critical developer portals, a backend crash caused by a malformed patch or an unhandled exception should never destroy the user's browser session.

This chapter presents the architectural blueprint of the **Bootstrap Gateway & Pre-Flight Self-Healing Supervisor** (`core/bootstrap_gateway.py`), which guarantees dual-layer uptime and automatic crash recovery.

---

## The Dual-Layer Gateway Blueprint

```text
+-------------------------------------------------------------------------------+
|                           Accessible Web Client                               |
|                  Connects to http://127.0.0.1:5000 (WebSocket)                |
+---------------------------------------+---------------------------------------+
                                        |  (Permanent connection; never dropped)
                                        v
+-------------------------------------------------------------------------------+
|                       Dual-Layer Bootstrap Gateway (Port 5000)                |
|  - Runs independently as a lightweight, indestructible Quart proxy            |
|  - Maintains client_listener loop even during backend crash / restart         |
|  - Monitors backend health via internal loopback queries                      |
+-------------------+---------------------------------------+-------------------+
                    |                                       |
     (Healthy Flow) |                                       | (Crash Detected)
                    v                                       v
+---------------------------------------+   +-----------------------------------+
|     Live Backend Engine (Port 5001)   |   |     Self-Healing Supervisor       |
|  - Server logic, AI orchestration     |   |  1. Intercepts backend death      |
|  - Hot-patching and API routes        |   |  2. Reverts bad patch from backup |
|                                       |   |  3. Restarts backend on Port 5001 |
+---------------------------------------+   +-----------------------------------+
```

---

## The 3 Supervisor Pillars

### 1. Pre-Flight Syntax Compilation Gating
Before any server process launches, `run_preflight_checks()` compiles all Python modules in `core/`, `agents/`, and `security/`:
- If a syntax error is discovered, the boot sequence halts *before* port binding.
- Logs the exact line number of the syntax error to prevent zombie port locks.

### 2. Dual-Layer Uptime Decoupling
- The **Gateway** owns public **Port 5000**.
- The **Core Engine** runs on private loopback **Port 5001**.
- If the Core Engine crashes, the Gateway buffers the user's incoming chat messages in memory while initiating an automated restart.

### 3. Automated Crash Healing (`heal_crash`)
When the supervisor detects a backend crash:
- Scans `core/patches/` and `core/backups/`.
- Restores the last known stable snapshot.
- Revives the backend daemon and reconnects the internal proxy pipe.

---

## Why Order Matters in Gateway Supervision

1. **Bind Gateway Port Before Spawning Backend**:
   - Port 5000 must be claimed by the stable Gateway process *before* starting the backend on Port 5001. If the backend fails to boot, Port 5000 remains online to display helpful diagnostics.
2. **Never Cancel Client Listener During Backend Failover**:
   - The Gateway's internal WebSocket task must only cancel the *backend forwarding* worker during a crash. Cancelling `client_listener` closes the browser socket, forcing the user to manually refresh.

---

## Beginner Coder Q&A

### Q: Why run two ports (5000 and 5001) instead of one?
**A:** If a single server on Port 5000 crashes, your browser displays "Connection Refused", and all active state is lost. Running a proxy on Port 5000 and the server on Port 5001 isolates the browser from server crashes.

### Q: How long does self-healing restart take?
**A:** Because Python restarts locally in memory and reads pre-compiled bytecode, the supervisor can revive the backend in under 500 milliseconds.
