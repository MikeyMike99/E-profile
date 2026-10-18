[//]: # (DOC_ID: SIRA-DEV-02_36 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.36: Source Code Evidence: RAIA & The Semantic Tree Protocol (STP)

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-1)
## Overview & Context
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-1)
This document cites primary architectural and textbook specifications from `docs/Siraugga_Textbook/Chapter_08_Cybersecurity_Resilience.md` defining how Siraugga orchestrates multi-agent swarms using **RAIA (Redundant Array of Independent Agents)** and enforces **The Semantic Tree Protocol (STP)** to eliminate conversational feedback loops and single points of failure.

---

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-2)
## Source Citation 1: Redundant Array of Independent Agents (`docs/Siraugga_Textbook/Chapter_08_Cybersecurity_Resilience.md`)
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-2)

```markdown
# Location: docs/Siraugga_Textbook/Chapter_08_Cybersecurity_Resilience.md
# Lines 92-104

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-10)
## 10. RAIA (Redundant Array of Independent Agents)
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-10)

In the DevCore architecture, this concept perfectly translates to **RAIA (Redundant Array of Independent Agents)**.
The core Agent Orchestrator takes a massive generative logic task that would normally exhaust the context window 
of a single AI and intelligently spreads the execution out among a cluster of several parallel subagents.

Just as RAID solutions can be hardware or software-based, RAIA deployments can be processed physically on the 
Tier 2 Modder's local GPU hardware (Hardware-based RAIA) or efficiently routed through the centralized DevCore 
LLM API cloud (Software-based RAIA).
```

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-3)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-3)
- DevCore mitigates single-agent memory exhaustion and process termination by striping complex development tasks across an array of independent workers, preventing any single subagent crash from aborting the overarching project.

---

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-4)
## Source Citation 2: The Semantic Tree Protocol (STP) & Loop Suppression
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-4)

```markdown
# Location: docs/Siraugga_Textbook/Chapter_08_Cybersecurity_Resilience.md
# Lines 105-120

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-11)
## 11. The Semantic Tree Protocol (STP)
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-11)

When multiple redundant subagents are spawned into the same orchestration channel to solve a single generative 
task, they run the massive risk of autonomously responding to each other's outputs. This creates a devastating 
infinite hallucination loop, resulting in duplicate JSON frames and severe API token exhaustion.

The **Semantic Tree Protocol (STP)** addresses these critical vulnerabilities. Its core function is to strictly 
prevent infinite logic loops when dozens of redundant subagents interconnect within the same workspace. STP 
ensures that despite the physical presence of redundant stand-by subagents, the conversation remains entirely 
loop-free and only **one logical execution thread** runs at a given time. 

To achieve this, STP intentionally mutes (blocks) redundant subagents that could cause a loop. The backup subagents 
still physically exist in the server's memory to provide N+1 redundancy, but the Semantic Tree Protocol forcefully 
disables their ability to broadcast tool calls or messages into the overarching conversation. 
```

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-5)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-5)
- The Semantic Tree Protocol enforces deterministic execution by mathematically muting redundant execution paths in memory, activating hot-standby subagents only when an active primary worker fails.

---

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-3)
## 3. Why Order Matters in Swarm Topologies
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-3)
1. **Elect Primary Execution Root Before Dispatching Prompts**: STP must elect a single active root subagent before tasks are broadcast to prevent simultaneous duplicate writes.
2. **Quarantine Before Re-Election**: When a primary agent triggers an unhandled exception or token limit, its state must be snapshot and quarantined before un-muting the standby replica.

---

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-4)
## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-6)

### Why is it called "Semantic Tree Protocol"?
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-6)
It is named after the Spanning Tree Protocol (STP) used in computer networking. In Ethernet networks, STP prevents broadcast storms by disabling redundant network links. In AI swarms, the Semantic Tree Protocol disables redundant conversational links to prevent token exhaustion loops.

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-7)
### Does an STP-muted subagent still consume API tokens?
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-7)
No. An STP-muted subagent sits idle in server RAM waiting for an activation signal. It does not send requests to the LLM API until the primary agent fails and STP activates it.

---

[//]: # (SECTION_ID: SIRA-DEV-02_36-SEC-5)
## 5. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-02_36-SEC-5)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_40_SWARM_COLLAPSE_AND_CONVERSATIONAL_LOOP_TRAPS.md`](/docs/devlog/01_40_SWARM_COLLAPSE_AND_CONVERSATIONAL_LOOP_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_33_SWARM_FAILOVER_AND_LOOP_PREVENTION_LOGS.md`](/docs/devlog/03_33_SWARM_FAILOVER_AND_LOOP_PREVENTION_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_36_HIGH_AVAILABILITY_SWARM_RESILIENCY_ARCHITECTURE.md`](/docs/devlog/04_36_HIGH_AVAILABILITY_SWARM_RESILIENCY_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_39_RAIA_SWARM_SUPERVISOR_FROM_SCRATCH.md`](/docs/devlog/05_39_RAIA_SWARM_SUPERVISOR_FROM_SCRATCH)
