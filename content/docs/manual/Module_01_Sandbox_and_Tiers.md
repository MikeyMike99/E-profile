# Module 1: The DevCore Sandbox & Tier Architecture

## What Will I Learn in this Module?
This module establishes the foundational security architecture of the Siraugga Engine. You will learn:
* **Asset Management & The Attack Surface:** How to identify, map, and classify every script, database, and daemon in the environment to eliminate blind spots.
* **The Danger of Autonomous Agents:** Why giving an AI access to a terminal requires strict isolation to prevent catastrophic Prompt Injection attacks.
* **The File Classification Tiers & RBAC:** The definitive explanation of the 5-Tier architecture and how it dictates exactly what a user or Subagent can see, read, and execute.
* **Sandbox Event Logging:** How to monitor activity deep inside the isolated execution environments.

---

## 1.1 Asset Management & The Siraugga Paradigm

When an empire expands, its shadow grows with it. Look at any massive organization—every new acquisition, every shiny new merger, just adds more doors that can be kicked down. Most of these corporate giants only have a vague, blurry idea of what they actually own, leaving massive blind spots in their armor.

Let's get one thing straight: every single device, script, database, and rogue laptop owned by the organization is an **asset**. Collectively, these assets form your **Attack Surface**. They are the bleeding targets that threat actors—both human and algorithmic—are constantly probing in the dark. You can't protect what you can't see.

### The Core Problem: The Danger of Autonomous Agents
As the industry pivots toward AI-driven development, a new, catastrophic vulnerability has emerged: the **Agentic Execution flaw**. When you give an AI Agent access to a terminal to write code or execute scripts, you are essentially handing root-level keys to a ghost. If a prompt injection attack succeeds, or if a third-party modder attempts a path-traversal attack, the Agent could be weaponized to format the server, steal environment variables, or rewrite the core engine.

**Siraugga** was built to solve this exact crisis. It is a Zero-Trust, event-driven orchestration framework designed to allow third-party developers and autonomous AI Agents to safely interact with a host system without ever compromising the core infrastructure. It achieves this through a philosophy of **Absolute Visibility** and **Hostile Sandboxing**.


## 1.2 The Five-Tier Access Control System (RBAC & The Sandbox)

To protect the mapped attack surface from Agentic Drift and rogue Modders, Siraugga enforces strict, non-negotiable **Role-Based Access Control (RBAC)** through a File Classification Tier system. 

Instead of simply trusting the perimeter, DevCore uses **Mandatory Agentic Control (MAC)**—the operating system intrinsically restricts files based on absolute security clearances. You cannot treat a sandboxed JSON game file with the same paranoia as a root orchestration script. 

The infrastructure is compartmentalized into the following definitive tiers:

*   **Tiers 1 & 2 (The Safe Workspace & Modders):** The playground for standard users and third-party Modders. Operational assets—game scripts, JSON state data (`npc_state.json`), and localized documentation—reside here. Agents spawned here are strictly sandboxed and physically incapable of looking beyond their assigned project directory.
*   **Tier 3 (Developers):** Jailed strictly to assigned game project folders. They have read/edit access to their safe workspace but are denied direct access to root files.
*   **Tier 4 (The Forbidden Zone / Admin Logs):** Daemon logs (`upgrade.log`), virtual environments (`venv/`), Git internals, and hidden `.env` credential files. These are hard-locked. If a Subagent attempts a path-traversal attack to access a Tier 4 asset, the connection is instantly severed.
*   **Tier 5 (The Core Engine & Admins):** The beating heart of the system (`App Router Module`, `Task Orchestrator Module`). These assets are completely invisible to anyone without absolute Tier 5 Administrator clearance. Admins have full, unfettered access to all workspaces and logs.

### The Semantic Firewall in Action (Examples of Access Control)
Rather than a traditional firewall that simply blocks IP ports, Siraugga uses a **Semantic Firewall (The Raugus Resolver)** to enforce these tiers dynamically by analyzing the *intent* of the payload.

**Examples of Tiered Enforcement:**
*   **Scrubbing Code and Keys (Tier 3 vs Tier 5):** When a Tier 5 Admin clicks an implementation plan artifact, they natively fetch the raw markdown file. However, when a Tier 3 Developer requests that same artifact, the Semantic Firewall intercepts the request. It spawns an invisible background Agent to read the plan, *scrubs out any exposed Root credentials, API keys, or Core Engine source code*, and only returns a sanitized, high-level technical summary to the Developer.
*   **The Semantic Mantrap:** When multiple Subagents attempt to modify the core database simultaneously, the firewall staggers the logic flow, ensuring only one authenticated Subagent enters the execution chamber at a time, trapping and purging any malicious subagent trying to piggyback on the thread.
*   **Agentic Clipping Levels:** If an AI fails an allowed tool call once, it is permitted to retry. But if it hits a "Clipping Level" of three consecutive errors, the firewall assumes the AI is hallucinating (Agentic Drift) and instantly terminates it.


## 1.3 Asset Accountability & Identity Management (IAM)

An orphaned asset or an unidentified Subagent is an invitation for disaster. Siraugga enforces strict, unyielding accountability. Every single information asset, every line of application software, and every AI process must be cryptographically chained to a verified owner.

### The Asset Identification Protocol
Before any asset or Subagent is mapped and secured, it must be ruthlessly categorized:
*   **The Data Custodian:** Every environment variable and JSON payload must have an assigned owner. If the data leaks, the Orchestrator knows exactly whose namespace was breached.
*   **The Execution Master:** Every script and automation module must be cryptographically bound to an operator. If a script attempts a privilege escalation, the system knows precisely who authorized the weapon.

### Agentic Identity Management
In traditional IAM, a user types a password to prove who they are. In the Siraugga framework, an AI Subagent does not have a password. Instead, its identity is established the moment it is spawned.
*   **Inherited Modder Identity:** If a Tier 2 Modder spawns a Subagent, that Subagent inherits the Modder's unique cryptographic ID. Any tool call the Subagent makes is billed and logged against the Modder's account.
*   **Agentic Archetypes (The Biological Hash):** The intrinsic identity of an AI is its System Prompt (e.g., `Research`, `Coding`). The Semantic Firewall uses this "biological hash" to ensure a `Research` agent cannot execute tools reserved for a `Coding` agent.


## 1.4 Sandbox Event Logging (HIDS)

While the File Classification Tiers prevent a Subagent from breaking out of the Sandbox, Tier 5 Admins still need to monitor what the Subagent is doing *inside* the isolated execution environment. 

To achieve this, the Orchestrator runs a Host-Based Intrusion Detection System (HIDS) inside the container. This system tracks five critical event logs:
1.  **Error:** A critical failure (e.g., the Sandbox crashed or ran out of memory).
2.  **Warning:** A non-critical issue (e.g., the Subagent is nearing its API token quota limit).
3.  **Information:** Standard operational telemetry (e.g., the Subagent successfully loaded a Python library).
4.  **Success Audit:** The Orchestrator successfully authenticated the Modder's PKI certificate before launching the Subagent.
5.  **Failure Audit:** The Subagent attempted to execute a forbidden tool and was blocked by the ACL.
