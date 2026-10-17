# Chapter 23: Sandbox Architectural Topologies

## 23.1 The Sandbox Topologies

Firewall design in DevCore is primarily about dictating where a Modder's WebSocket connection is allowed to physically terminate. By establishing rigid boundaries between the untrusted public connections and the highly trusted orchestration files, Tier 5 Admins construct the physical layout of the Sandbox.

There are three common architectural topologies utilized in the Siraugga Engine:
1.  **The Binary Topology (Private and Public)**
2.  **The Safe Workspace Topology (The DMZ)**
3.  **Role-Based Sandbox Zones (ZPF)**

## 23.2 The Binary Topology (Private and Public)

The most basic topology divides the environment into exactly two domains:
*   **The Trusted Domain (Inside):** The `/core_engine/` and internal `App Router Module` processes.
*   **The Untrusted Domain (Outside):** The public internet and Modder WebSockets.

In a Binary Topology, traffic originating from the internal engine is permitted to travel out to the internet (e.g., to query an LLM API), and the returning data is trusted. However, any unprompted traffic originating from the outside and attempting to access the `core_engine` is violently blocked.

## 23.3 The Safe Workspace Topology (The DMZ)

For a Game Engine, the Binary Topology is too restrictive; third-party Modders need a place to upload assets and write scripts without being blocked by the firewall. This requires a three-tiered architecture known as the **Safe Workspace Topology** (the Demilitarized Zone, or DMZ).

1.  **The Core Engine (Inside):** Strictly locked down.
2.  **The Public WebSockets (Outside):** Untrusted Modder connections.
3.  **The Safe Workspace (DMZ):** The `/playground/` directories.

In this architecture, Modders are selectively permitted to connect to the Safe Workspace (DMZ) to upload assets and run isolated AI agents. Those agents are permitted to query the public internet (LLMs) to generate code. However, traffic originating from the Safe Workspace and attempting to cross into the Core Engine is strictly blocked. The DMZ acts as a heavily monitored quarantine zone. 

## 23.4 Role-Based Sandbox Zones (ZPF)

As a game project scales, Admins often manage dozens of different Safe Workspaces (e.g., `/assets/`, `/levels/`, `/npc_scripts/`). Writing individual bulkheads between every single folder is inefficient. Instead, DevCore uses **Role-Based Sandbox Zones** (Zone-Based Policy Firewalls).

A "Zone" is a group of directories that share a similar security classification. 
*   **Intra-Zone Trust:** By default, AI subagents operating in directories within the *same* Zone can share files and JSON context completely freely. 
*   **Inter-Zone Blocks:** By default, traffic attempting to cross from one Zone to another (e.g., from the Asset Zone to the NPC Script Zone) is blocked unless an explicit bulkhead permits it.

**The Self Zone:** The only exception to the "deny all" zone rule is the **Self Zone**. In DevCore, the Self Zone is the Orchestrator itself (`App Router Module`). Traffic destined to or sourced from the Orchestrator (such as internal telemetry and transcript logging) requires highly specialized control plane policies.

## 23.5 Defense-in-Depth Swarm Defense

Relying on a single bulkhead is reckless. A secure Sandbox employs a **Defense-in-Depth** (Layered Defense) approach, often utilizing a *Screened Subnet*. 

When an untrusted Modder connects to DevCore, their payload must survive a gauntlet:
1.  **Perimeter Edge:** A Stateless Agentic Filter rapidly drops spoofed UUIDs.
2.  **The Raugus Proxy (Bastion Host):** The payload hits a hardened proxy located in the DMZ, which scrubs the prompt for malicious semantics.
3.  **Interior Screening:** A Stateful Thought Firewall verifies the payload belongs to an active LLM context before finally letting it touch the internal systems.

**The Human Limitation:** While this layered defense stops technical exploits, bulkheads cannot protect against everything. Firewalls cannot stop an intrusion if a Tier 5 Admin intentionally goes rogue, nor can they replace standard physical backups if the hardware running the `core_engine` catches fire.

---

## Chapter 23 Conclusion and Master Review

Chapter 23 defines the blueprints of the DevCore Sandbox. By graduating from a simple Binary Topology to a Safe Workspace DMZ, Admins can safely host untrusted Modder code without risking the core engine. Grouping these directories into Role-Based Zones allows massive AI swarms to collaborate efficiently, while a Defense-in-Depth gauntlet ensures no single failure compromises the engine. 

### Traditional IT vs. DevCore Agentic Lore (Chapter 23 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional firewall topologies into their DevCore Agentic equivalents:

*   **Private and Public** $\rightarrow$ **The Binary Topology:** A basic 2-domain split between the internal `core_engine` (Private) and the Modder WebSockets (Public).
*   **Demilitarized Zone (DMZ)** $\rightarrow$ **The Safe Workspace:** A semi-trusted 3rd domain (e.g., `/playground/`) where untrusted Modders and AI agents can safely execute code without touching the core engine.
*   **Zone-Based Policy Firewalls (ZPF)** $\rightarrow$ **Role-Based Sandbox Zones:** Grouping similar directories together. Subagents within the same Zone can communicate freely.
*   **The Self Zone** $\rightarrow$ **The Orchestrator (`App Router Module`):** The core routing process itself, which requires specialized control plane policies to handle telemetry.
*   **Bastion Host / Screened Subnet** $\rightarrow$ **The Raugus Proxy / Defense-in-Depth:** A hardened proxy server located inside the Safe Workspace that scrubs semantic prompts before they reach the deeper interior network.
