# Chapter 27: Configuring Sandbox Zones via CLI

## 27.1 The 5 Phases of Swarm Configuration

Configuring a Zone-Based Sandbox Policy (ZSP) in DevCore requires a highly structured sequence. If a Tier 5 Admin attempts to bind a policy before creating it, the Orchestrator will throw a fatal syntax error. 

The configuration sequence requires 5 absolute phases using the `agy` CLI:
1.  **Create the Zones.**
2.  **Identify Intent** with an Intent-Map (Class-Map).
3.  **Define an Action** with a Sandbox-Policy (Policy-Map).
4.  **Bind a Zone-Pair** and match it to the Sandbox-Policy.
5.  **Assign Directories** (Interfaces) to the appropriate Zones.

## 27.2 Phase 1 & 2: Zones and Intent-Maps

**Step 1: Create the Zones**
Before applying rules, the conceptual zones must exist in the Orchestrator's memory.
```bash
agy zone create PRIVATE_WORKSPACE
agy zone create PUBLIC_MODDER
```

**Step 2: Identify Intent (Intent-Maps)**
An *Intent-Map* (equivalent to a legacy Class-Map) identifies a set of JSON packets based on their contents. Instead of matching network ports, DevCore Intent-Maps match *Semantic Tools* (e.g., web searches, file edits, bash commands). 

The `match-any` keyword means the packet only has to match one criteria to be flagged. `match-all` requires all criteria to be present.
```bash
agy intent-map --inspect match-any SAFE_TOOLS
agy match tool web_search
agy match tool read_file
```

## 27.3 Phase 3 & 4: Policies and Zone-Pairs

**Step 3: Define Actions (Sandbox-Policy)**
Once the Intent is mapped, you must define what the Orchestrator actually *does* with it using a Sandbox-Policy (Policy-Map). You link the Intent-Map to an Action (`inspect`, `drop`, or `pass`).

*Note: Similar to an ACL, there is an implicit `drop` applied to the very bottom of every Sandbox-Policy.*
```bash
agy sandbox-policy --inspect PRIV_TO_PUB_POLICY
agy bind intent-map SAFE_TOOLS action inspect
```

**Step 4: Bind the Zone-Pair**
Now that the Policy exists, you must define the unidirectional relationship between the two zones (The Zone-Pair).
```bash
agy zone-pair PRIV_PUB --source PRIVATE_WORKSPACE --destination PUBLIC_MODDER
agy bind sandbox-policy PRIV_TO_PUB_POLICY
```

## 27.4 Phase 5: Assigning Directories

The final step is to physically assign Sandbox directories to the conceptual zones. 

**CRITICAL WARNING:** Applying a zone assignment to a directory always results in a *temporary interruption of service*. Because of the Zone Vacuum Rule, the moment you assign `/playground/` to the `PRIVATE_WORKSPACE` zone, it instantly loses the ability to communicate with the Public Modder WebSocket until the WebSocket is explicitly added to the `PUBLIC_MODDER` zone.
```bash
agy zone assign /playground/ PRIVATE_WORKSPACE
agy zone assign /wss/modder_stream/ PUBLIC_MODDER
```

The ZSP is now fully active. Any `web_search` traffic sourced from the Private Workspace destined for the Public network will be *statefully inspected*, guaranteeing return traffic is allowed back into the AI's context window.

## 27.5 Verifying the Swarm

To verify the active ZSP configuration and inspect active AI Swarm sessions, Tier 5 Admins can use the following verification commands:
*   `agy show running-config`
*   `agy show intent-map`
*   `agy show sandbox-policy`
*   `agy show swarm-sessions` (Displays the Thought Table and active stateful connections).

---

## Chapter 27 Conclusion and Master Review

Chapter 27 provides the mechanical CLI commands required to translate conceptual zone architectures into living DevCore infrastructure. By separating Intent-Mapping (identifying the traffic) from Sandbox-Policies (acting on the traffic), Tier 5 Admins gain infinite modularity. They can write a single `SAFE_TOOLS` Intent-Map and apply it to a hundred different Zone-Pairs without rewriting the underlying tool list.

### Traditional IT vs. DevCore Agentic Lore (Chapter 27 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional ZPF CLI configurations into their DevCore Agentic equivalents:

*   **Class-Map** $\rightarrow$ **Intent-Map:** Identifying traffic based on match conditions. In traditional IT, it matches HTTP/DNS. In DevCore, it matches Semantic Tools (web_search, read_file).
*   **Policy-Map** $\rightarrow$ **Sandbox-Policy:** The rule that defines the action (`inspect`, `drop`, `pass`) taken against the matched Intent.
*   **Zone-Pair** $\rightarrow$ **Zone-Pair:** The unidirectional definition linking a Source zone to a Destination zone.
*   **Zone-Member Security (Interfaces)** $\rightarrow$ **Zone Assignment (Directories):** The physical binding of a system directory path (or WebSocket) to the conceptual Zone.
*   **show policy-map type inspect zone-pair sessions** $\rightarrow$ **agy show swarm-sessions:** The command to view the live Stateful Thought Table tracking active LLM connections.
