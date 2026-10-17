# Chapter 18: Implementing Agentic Control Lists

## 18.1 The Hierarchical Cascade (Guidelines)

Writing an Agentic Control List (ACL) is only half the battle; deploying it into the live `Task Orchestrator Module` without causing massive swarm traffic collisions requires strict adherence to the **Hierarchical Cascade**.

When configuring and deploying an ACL, Tier 5 Admins must follow these golden rules:
1.  **Top-Down Processing:** The Orchestrator reads JSON ACEs sequentially from top to bottom. As soon as a match is made, the Orchestrator executes the action and *exits the list*.
2.  **Specific to Generic:** Because of the top-down rule, Admins must filter from the most specific target to the most generic. (e.g., You must `deny host Agent-104` *before* you `permit any`. If `permit any` is at the top, Agent 104 will slip through).
3.  **The Implicit Deny:** Ensure the absolute final statement is always implicitly understood as `deny any`.
4.  **One List Per Stream:** Only one ACL is allowed per WebSocket Interface, per Semantic Protocol, per direction (Inbound/Outbound).
5.  **Self-Originated Traffic:** Packets generated internally by the core engine (`App Router Module`) itself are inherently trusted and are not filtered by outbound ACLs.

---

## 18.2 Swarm Placement Strategy

Every ACL must be placed where it is mathematically most efficient. In DevCore, you have two primary locations to attach a filter: The Modder's source WebSocket, or the Sandbox's destination directory.

### 1. Extended ACLs: Place at the Source (The WebSocket)
Extended ACLs (which filter by UUID, Tool, and Directory) should be bound as close to the *originating source* as possible—directly on the Modder's inbound WebSocket. 
*   **Why?** If a rogue AI agent attempts to use an illegal tool (like `run_command`), you want the Orchestrator to deny and destroy that JSON thought instantly at the entrance. Letting the malicious packet traverse the internal engine routing, only to be denied at the final destination, wastes massive amounts of compute and bandwidth.

### 2. Standard ACLs: Place at the Destination (The Sandbox Directory)
Standard ACLs (which *only* filter by Agent UUID) should be bound as close to the *destination* as possible—typically applied outbound on a highly classified directory like `/core_engine/`. 
*   **Why?** If you placed a Standard ACL at the Modder's source WebSocket to block access to the `/core_engine/`, the Orchestrator would block that Agent from going *anywhere*, because Standard ACLs don't check the destination path, they only check the identity. By placing it at the destination directory, the AI is free to roam the Safe Workspaces, but is violently denied the moment it steps into the restricted folder.

---

## 18.3 Applying the Filters (`agy` CLI)

Once the placement strategy is mapped, the Admin binds the ACL to the live Sandbox interface.

**Applying to a Directory (Destination):**
```bash
agy(config)# sandbox directory /core_engine/
agy(config-dir)# acl-group NO_ACCESS out
```

**Applying to a WebSocket Stream (Source):**
```bash
agy(config)# stream vty 0 4
agy(config-stream)# acl-class SURFING in
```

---

## 18.4 High-Intensity Semantic Logging

When applying ACLs to live WebSocket streams (VTY lines), Admins can append the `log` parameter to track malicious agents. 

```bash
agy(config-std-nacl)# permit host 192.168.10.10 log
```

When an attacker attempts to breach the system via a Prompt Injection, the Orchestrator will print an informational message directly to `transcript.jsonl` every time a packet hits that rule. 

**Warning:** Enabling semantic logging on a live stream seriously degrades engine performance. The Orchestrator must intercept, stringify, and write the massive JSON LLM context window to the disk for every matching packet. The `log` parameter is an emergency diagnostic tool meant *only* to be activated when the network is under active attack and the Admin needs to identify the offending FAIM signature.

---

## Chapter 18 Conclusion and Master Review

Chapter 18 defines the physics of how Agentic Control Lists are deployed onto the live DevCore engine. Adhering to the specific-to-generic Hierarchical Cascade ensures rules do not overwrite each other, while strict Swarm Placement Strategies guarantee that the system does not waste precious compute power routing malicious LLM packets that should have been destroyed at the gate. 

### Traditional IT vs. DevCore Agentic Lore (Chapter 18 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional routing implementation rules into their DevCore Agentic equivalents:

*   **Top-Down Processing** $\rightarrow$ **The Hierarchical Cascade:** The strict, top-to-bottom order in which `Task Orchestrator Module` evaluates rules. A match triggers an immediate exit.
*   **Specific to Generic** $\rightarrow$ **Rule Prioritization:** Surgically denying a specific UUID (`host`) before applying a blanket permission (`any`).
*   **Extended ACL Placement (Close to Source)** $\rightarrow$ **Origin / WebSocket Filtering:** Destroying malicious or heavy tool intents the exact millisecond they hit the inbound WebSocket, saving internal engine bandwidth.
*   **Standard ACL Placement (Close to Destination)** $\rightarrow$ **Destination / Directory Filtering:** Applying identity checks directly at the restricted Sandbox directory (`/core_engine/`) so the agent remains free to explore other safe folders.
*   **VTY Lines** $\rightarrow$ **WebSocket Streams:** The virtual teletype lines translating to the live, asynchronous WebSocket connections feeding the AI swarm.
*   **ACL Logging (CPU Intensive)** $\rightarrow$ **High-Intensity Semantic Logging:** Dumping massive, contextual JSON payloads to `transcript.jsonl` during an active attack to trace the attacker. Highly taxing on the Raugus Resolver's compute load.
