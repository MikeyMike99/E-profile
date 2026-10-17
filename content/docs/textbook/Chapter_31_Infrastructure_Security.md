# Chapter 31: Orchestrator Infrastructure Security

## 31.1 The Software-Defined Swarm

The foundation of DevCore is the Orchestrator's infrastructure—the physical CPU, memory, and storage that compute the AI Subagents. 

Because of the volatile nature of Subagent Virtualization (SVs), where hundreds of virtual contexts are spawned and destroyed every minute, traditional hardware firewalls are useless. You cannot plug a physical firewall cable into a subagent that only exists in RAM for 30 seconds.

To secure the Orchestrator infrastructure, DevCore relies on **Software-Defined Swarm Networks (SDSN)**. Instead of physical cables, Tier 5 Admins apply virtual Agentic Bulkheads (Security Groups) directly to the virtualized subagents. This allows for absolute network isolation without the constraints of physical hardware, preventing subagents from bleeding context into each other.

## 31.2 The BYOK Responsibility Matrix

When a Tier 5 Admin hosts the Siraugga Engine for a community of developers, security becomes a shared burden. This is known as the **BYOK (Bring Your Own Key) Responsibility Matrix**.

The Admin (acting as the Service Provider) is responsible for the physical services they offer, but the Modder (the Client) is responsible for the rest. The exact split depends on which Engine-as-a-Service model is deployed:

| Security Responsibility | Infrastructure (IaaS) | Sandbox (PaaS) | Swarm (SaaS) |
| :--- | :--- | :--- | :--- |
| **Physical Orchestrator Hardware** | Admin | Admin | Admin |
| **Host Operating System** | Admin | Admin | Admin |
| **Network Control** | Modder | Shared | Admin |
| **Agentic Tools / Applications** | Modder | Shared | Admin |
| **Identity Management (RBAC)** | Modder | Shared | Shared |
| **Endpoints (WebSockets)** | Modder | Modder | Shared |
| **JSON Prompt Data** | **Modder** | **Modder** | **Modder** |

*Critical Note: Regardless of how much infrastructure the Admin provides, the Modder is ALWAYS responsible for the security of their own JSON Prompt Data.*

## 31.3 Defense-in-Depth for the Orchestrator

Securing the physical foundation of the Swarm requires a Defense-in-Depth strategy applied directly to the Orchestrator's operating layers. 

Tier 5 Admins implement the following architectural safeguards:
*   **Virtual Private Sandboxes (VPS):** Allocating private `/playground/` directories that are logically isolated from the rest of the host's filesystem.
*   **Transcript Flow Logs:** Continuously monitoring `transcript.jsonl` to track the exact flow of JSON payloads crossing individual zone bulkheads.
*   **Swarm Tunnels (VPNs):** Using encrypted tunnels to provide remote Modders secure WebSocket access to the Orchestrator, or to connect two separate bare-metal Orchestrators together in a multi-host scenario.
*   **RBAC Services (IAM):** Enforcing the 5-Tier DevCore Access Control system to manage user credentials. Proper RBAC configuration is the absolute baseline required to protect Orchestrator resources from being abused by rogue Modders.

---

## Chapter 31 Conclusion and Master Review

Chapter 31 defines the physical and virtual boundaries of the Orchestrator. Because traditional hardware cannot keep up with rapidly spawning AI contexts, Software-Defined Swarm Networks (SDSN) are required. Furthermore, the BYOK Responsibility Matrix explicitly defines who is at fault when an attack succeeds: The Admin protects the metal, but the Modder protects the data.

### Traditional IT vs. DevCore Agentic Lore (Chapter 31 Translation Guide)

To maintain absolute clarity, here is how the traditional Cloud Infrastructure domains map directly to the DevCore Engine:

*   **Software-Defined Networks (SDN)** $\rightarrow$ **Software-Defined Swarm Networks (SDSN):** The ability to apply virtual bulkheads to AI subagents without relying on physical routing hardware.
*   **Cloud Service Provider (CSP)** $\rightarrow$ **Tier 5 Admin (Host):** The person hosting the DevCore engine.
*   **Cloud Client** $\rightarrow$ **Modder:** The remote developer connecting to the swarm.
*   **Shared Responsibility Model** $\rightarrow$ **The BYOK Responsibility Matrix:** The table defining who secures what (IaaS, PaaS, SaaS). The Modder ALWAYS secures their own Prompt Data.
*   **Virtual Private Cloud (VPC)** $\rightarrow$ **Virtual Private Sandbox (VPS):** A logically isolated workspace (like `/playground/game_demo/`).
*   **Flow Logs** $\rightarrow$ **`transcript.jsonl` Flow Logs:** Tracking traffic that crosses Swarm Zones.
*   **Identity and Access Management (IAM)** $\rightarrow$ **RBAC Services:** The 5-Tier Role-Based Access Control system.
