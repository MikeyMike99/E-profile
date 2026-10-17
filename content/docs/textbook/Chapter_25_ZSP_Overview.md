# Chapter 25: Designing Zone-Based Sandbox Policies

## 25.1 The Shift from Directories to Zones

The primary motivation for DevCore network security professionals to migrate from legacy Directory-Based Bulkheads to **Zone-Based Sandbox Policies (ZSP)** is structure and ease of use. 

In a classic DevCore Sandbox, security policies are applied directly to the physical file paths (`/playground/assets/`). If a Modder generates ten new folders for their assets, the Admin must write ten new bulkhead rules.

In a ZSP topology, interfaces (directories) are assigned to conceptual **Security Zones**. If an Admin creates a new directory and assigns it to the `Private_Asset_Zone`, the AI subagents operating in that new folder can instantly pass JSON traffic to all other subagents in the `Private_Asset_Zone` freely. The Admin does not have to write a single new security rule.

## 25.2 The Benefits of Swarm Zones

Transitioning to a ZSP topology offers several critical benefits for managing massive AI Swarms:

*   **Decoupled from UUID ACLs:** ZSPs are not strictly dependent on matching thousands of individual Agent UUIDs. Security is based on the *Zone*, not the individual agent identity.
*   **Zero-Trust Posture:** The default Sandbox posture is to block all inter-zone traffic unless explicitly allowed.
*   **Swarm Classification Policy Language (SCPL):** ZSP policies are incredibly easy to read and troubleshoot because they use **SCPL** (the DevCore equivalent to Cisco's C3PL). SCPL is a structured method that creates traffic policies based on *Events, Conditions, and Actions* rather than strict network numbers. This provides infinite scalability.
*   **Virtual & Physical Grouping:** Temporary in-memory virtual paths and permanent physical paths can be grouped into the exact same Zone.
*   **Unidirectional Logic:** Policies are applied to unidirectional traffic moving between the zones. (e.g., A policy allowing traffic from the `Asset_Zone` to the `Script_Zone` does *not* automatically allow traffic in the reverse direction).

## 25.3 The Absolute Binding Rule

When an Admin is deciding whether to implement a legacy Directory Bulkhead or a Zone-Based Sandbox Policy, it is critical to note that both models *can* be enabled concurrently on the Orchestrator. 

However, they cannot be combined on a single directory. A directory path (e.g., `/game_demo/npc/`) cannot be simultaneously configured as a ZSP Zone member *and* possess a legacy Directory Bulkhead. It must be strictly one or the other. 

## 25.4 ZSP Orchestration Steps

Designing a Zone-Based Sandbox Policy for a massive game project involves four critical orchestration steps:

1.  **Determine the Semantic Zones:** Identify which directories require similar security functions (e.g., group all level-design folders into a `Map_Zone`).
2.  **Establish Inter-Zone Policies:** Determine the security relationships between the zones. (Should the `Map_Zone` be allowed to query the `Asset_Zone`?)
3.  **Design the Sandbox Topology:** Map out the physical infrastructure. Which zones face the untrusted Public WebSockets, and which represent the internal Sandbox DMZ?
4.  **Merge Swarm Requirements:** Identify subsets of AI behaviors within the zones and merge their JSON traffic requirements into unified SCPL rules.

---

## Chapter 25 Conclusion and Master Review

Chapter 25 breaks down the philosophy of why Zone-Based Sandbox Policies (ZSP) are superior to classic directory firewalls. By grouping directories into unified conceptual zones, Tier 5 Admins can automatically grant trust to new folders without manually configuring fresh bulkheads. Paired with the event-driven logic of SCPL, ZSPs are the only viable method for securing infinitely scalable AI swarms.

### Traditional IT vs. DevCore Agentic Lore (Chapter 25 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional Zone-Based Policy Firewall concepts into their DevCore Agentic equivalents:

*   **Zone-Based Policy Firewalls (ZPF)** $\rightarrow$ **Zone-Based Sandbox Policies (ZSP):** The evolutionary step of applying bulkheads to conceptual zones rather than physical paths.
*   **C3PL (Common Classification Policy Language)** $\rightarrow$ **SCPL (Swarm Classification Policy Language):** A structured, readable language used by DevCore to create policies based on Events, Conditions, and Actions rather than rigid Agent UUIDs. 
*   **Classic Firewall vs ZPF** $\rightarrow$ **Directory-Based Bulkheads vs Zone-Based Policies:** The rule that you can run both architectures on the server, but you cannot bind a physical directory to both simultaneously.
*   **Unidirectional Traffic** $\rightarrow$ **Unidirectional Logic:** The rule that a policy permitting traffic from Zone A to Zone B does not implicitly permit traffic from Zone B to Zone A.
