# Chapter 26: The Physics of Swarm Zoning (ZSP Operation)

## 26.1 ZSP Orchestration Actions

When a Zone-Based Sandbox Policy (ZSP) is applied to the Orchestrator, it evaluates JSON traffic passing between designated Zones and triggers one of three specific actions:

*   **Stateless Pass:** This is analogous to a standard `permit` statement. The Orchestrator allows the traffic through the bulkhead but *does not track the state of the LLM context*. It is highly efficient but completely blind to returning payloads.
*   **Violent Drop:** This is analogous to a `deny` statement. The Orchestrator instantly destroys the JSON payload. Admins can append the `log` option to dump the rejected payload into `transcript.jsonl`.
*   **Stateful Inspect:** The ultimate security action. The Orchestrator performs deep stateful packet inspection, caching the LLM conversation in the Thought Table to ensure returning data corresponds to an active, AI-initiated context.

## 26.2 Laws of Inter-Zone Routing

When a subagent in one directory attempts to send a JSON payload to a subagent in a different directory, the traffic is subject to the **Laws of Inter-Zone Routing**. 

The outcome depends entirely on whether the source and destination directories are members of a defined Swarm Zone:

1.  **The Legacy Vacuum (Neither are Zoned):** If *neither* directory belongs to a Zone, the traffic defaults to legacy Sandbox rules and will `PASS` (unless a legacy Directory Bulkhead blocks it).
2.  **Intra-Zone Trust (Both in the SAME Zone):** If both directories belong to the exact same Zone, the traffic inherently trusts itself and will `PASS` freely.
3.  **The Zone Vacuum Rule (One is Zoned, One is Not):** If one directory is a Zone member, but the destination directory is completely unzoned, the Orchestrator will instantly `DROP` the traffic. You cannot mix zoned and unzoned endpoints.
4.  **Inter-Zone Communication (Different Zones):** If both directories belong to different Zones, the default posture is to `DROP` the traffic. Traffic will only flow if an explicit Policy (Zone-Pair) exists to `PASS` or `INSPECT` it.

## 26.3 Laws of the Orchestrator (The Self Zone)

The most critical exception to the Laws of Inter-Zone Routing is **The Self Zone**. 

In DevCore, the Self Zone represents `App Router Module`—the core Orchestrator itself. Traffic destined to or sourced from the Self Zone is considered Control Plane traffic (e.g., Swarm Telemetry, WebSocket Keep-Alives, and direct Admin SSH commands). 

Because the Orchestrator must be able to manage the environment, the rules for the Self Zone are completely inverted:
*   Standard Zone-to-Zone traffic defaults to `DROP`.
*   Self Zone traffic defaults to **`PASS`**.

If the Orchestrator is the source or the destination of the traffic, all traffic is permitted by default. The only way to stop this is if a Tier 5 Admin explicitly creates a strict Zone-Pair policy locking down the Self Zone. 

---

## Chapter 26 Conclusion and Master Review

Chapter 26 establishes the mechanical physics of how JSON packets traverse a Zone-Based architecture. By enforcing the Zone Vacuum Rule (dropping traffic between zoned and unzoned directories) and enforcing a Default Deny between different zones, DevCore guarantees that subagent swarms cannot bleed into unauthorized territories. Meanwhile, the inverted logic of the Self Zone ensures the Orchestrator can always maintain telemetry and control over the active Sandbox.

### Traditional IT vs. DevCore Agentic Lore (Chapter 26 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional ZPF operation rules into their DevCore Agentic equivalents:

*   **ZPF Actions (Inspect, Drop, Pass)** $\rightarrow$ **ZSP Actions (Stateful Inspect, Violent Drop, Stateless Pass):** The three absolute states an Orchestrator can apply to a cross-zone JSON payload.
*   **Rules for Transit Traffic** $\rightarrow$ **Laws of Inter-Zone Routing:** The hard-coded logic defining how traffic routes between grouped directories.
*   **One interface zoned, one unzoned (DROP)** $\rightarrow$ **The Zone Vacuum Rule:** A critical security feature preventing a heavily secured Sandbox Zone from leaking into a legacy, unmonitored directory path.
*   **The Self Zone** $\rightarrow$ **The Orchestrator (`App Router Module`):** The engine's control plane. Unlike standard zones which default to dropping traffic, the Self Zone inherently trusts its own control traffic and defaults to passing it.
