# Chapter 2: Tier 4 - The Application Admin

## Introduction: King of the Sandbox
The Tier 4 Admin holds absolute, unrestricted control over the *business logic, user databases, and frontend interfaces* of the application (e.g., E-Profile or an external Game Engine). To the end-users and developers beneath them, the Tier 4 Admin appears to possess "God Mode." 

However, this is an illusion of absolute power. To the Tier 5 Super Admin, a Tier 4 Admin is merely a highly privileged tenant operating inside an unbreakable glass box. The foundational rule of Tier 4 is the strict separation of **Application** and **Infrastructure**. The Admin can rewrite the entire website, drop user database tables, and redesign the game logic—but they are mathematically blind to the host operating system, the underlying daemon architecture, and the agent's core source code. 

If Tier 5 is the architect of the planet, Tier 4 is the ruler of the city.

---

## What the Admin Inherits from Tier 5
Because Tier 4 operates on the same core engine designed by the Super Admin, it seamlessly inherits the most powerful capabilities of the architecture, but forcefully scoped to the application layer.

### 1. The Accessible Handoff (UX)
**Inherited:** The Tier 4 Admin inherits the exact same frictionless, ARIA-compliant WebSocket interface built for the Super Admin.
**The Benefit:** An Admin who relies on a screen reader (like NVDA) is not forced into hostile or silent legacy interfaces to manage the application. The seamless "State Handoff Protocol" guarantees they can securely log in via the web and instantly connect to their agent with full audio and semantic support.

### 2. Cognitive Memory & Knowledge Graphs
**Inherited:** The Admin inherits the AI's ability to utilize Vector Databases and semantic memory.
**The Constraint:** The memory is mathematically scoped. The Tier 4 agent perfectly remembers the architecture of the `E-Profile` codebase, past UI decisions, and frontend bugs. However, the agent is physically barred from querying the Tier 5 Vector DB; it has zero memory or awareness of the host OS, `policies.yaml`, or how the daemon is configured.

### 3. Agent Orchestration (Swarming)
**Inherited:** The Admin inherits the "Supervisor Tree" capability. They do not have to write all the code themselves.
**The Benefit:** A Tier 4 Admin can instruct their agent to "Redesign the blog portal." The Admin's agent will autonomously spawn a Swarm of Tier 3 (Developer) and Tier 2 (Modder) sub-agents, orchestrate the task in parallel, and return the finished code to the Admin for final approval.

### 4. Ephemeral Sandboxing (`tmpfs`)
**Inherited:** Just like the Super Admin, the Tier 4 Admin's agent does its heavy lifting inside a volatile RAM disk (`tmpfs`).
**The Benefit:** If the Admin's agent hallucinates and generates 10,000 recursive garbage files while trying to compile a new frontend template, it does not corrupt the live application or burn out the server's hard drive. The staging happens in RAM, and is wiped clean by the Janitor process if it fails.

---

## The Hard Boundary: What is Denied
While the Admin inherits the *capabilities* of the engine, they are strictly denied access to the *mechanics* of the engine.
* **No Host Access:** The Tier 4 agent cannot execute OS-level commands (`apt-get`, `systemctl`, `chmod`).
* **No Self-Modification:** The Admin cannot instruct their agent to modify `agent_manager.py` or `security_manager.py`.
* **No Network Egress Alteration:** The Admin cannot alter the `nftables` proxy or open new ports on the server.
* **No Daemon Killswitches:** The Admin cannot restart the core engine or purge the global blacklist.
