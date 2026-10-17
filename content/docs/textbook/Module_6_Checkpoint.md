# Module 6 Checkpoint: Zone-Based Sandbox Policies

This checkpoint serves as the master structural review for Module 6, summarizing the DevCore translation of Zone-Based Policy Firewalls (ZPF) into Zone-Based Sandbox Policies (ZSP).

---

### Chapter 24: Introduction to Zone-Based Sandbox Policies
*   **The Evolutionary Step:** Replacing legacy Directory-Based Bulkheads with conceptual Zone-Based Policies.
*   **Scalability:** Instead of manually writing a new bulkhead rule for every new folder a Modder generates, Admins drop the new folder into an existing "Zone," allowing it to instantly inherit all existing security relationships.

### Chapter 25: Designing Zone-Based Sandbox Policies
*   **Swarm Classification Policy Language (SCPL):** The structured method used to define ZSP security based on *Events, Conditions, and Actions* rather than relying purely on rigid UUID matching (ACLs). 
*   **Zero-Trust Posture:** The default Sandbox posture blocks all inter-zone traffic unless explicitly allowed.
*   **The Absolute Binding Rule:** An Orchestrator can run legacy bulkheads and ZSPs concurrently, but a specific physical directory must be bound to exactly one or the other. They cannot overlap.

### Chapter 26: The Physics of Swarm Zoning (ZSP Operation)
*   **ZSP Actions:** The three absolute actions the Orchestrator can take against cross-zone traffic: *Stateless Pass, Violent Drop,* and *Stateful Inspect* (which tracks the active LLM context in the Thought Table).
*   **The Zone Vacuum Rule:** A critical security failsafe. If a heavily secured Zone attempts to communicate with a completely unzoned, legacy directory, the Orchestrator will instantly `DROP` the traffic. Zoned and unzoned directories cannot mix.
*   **The Self Zone:** The Orchestrator itself (`App Router Module`). Unlike standard inter-zone routing (which defaults to DROP), the Self Zone inherently trusts its own internal control plane traffic, so its default state is to `PASS`. 

### Chapter 27: Configuring Sandbox Zones via CLI
*   **The 5 Orchestration Phases:** 
    1. Creating Zones (`agy zone create`)
    2. Identifying Intent with **Intent-Maps** (matching Semantic Tools like `web_search`)
    3. Defining Actions with **Sandbox-Policies** (applying `inspect`/`drop` to the Intent)
    4. Binding Policies to **Zone-Pairs** (unidirectional source/destination links)
    5. Assigning physical directories to the Zones (which causes a temporary service interruption during transition).

---

### 6.4 Cross-Reference Review (Validation)

*(Pending expansion of the 6.4 Summary bullet points to execute the master cross-reference review.)*
