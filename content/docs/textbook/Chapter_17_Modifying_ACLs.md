# Chapter 17: Modifying Agentic Control Lists

## 17.1 Hot-Patching Agentic Filters

After an Agentic Control List (ACL) is deployed to the active Orchestrator, it often requires modification. A Tier 5 Admin might realize an ACE (Agentic Control Entry) is accidentally blocking a legitimate QA Agent from testing a level, or worse, a typo in a UUID has left the `core_engine` exposed. 

Because DevCore strictly adheres to a **Zero-Restart Policy**, shutting down `App Router Module` to fix a typo is unacceptable. It drops all active WebSocket connections and disrupts the live game state. Instead, Admins must "hot-patch" the ACLs while the AI Swarm continues to operate. 

There are two primary methods for hot-patching an active ACL:
1.  **The Crucible Purge (Text Editor Method)**
2.  **Agentic Sequence Injection (Sequence Number Method)**

---

## 17.2 The Crucible Purge (Text Editor Method)

The Crucible Purge is the brute-force method of updating an Agentic Control List. If an ACL has dozens of complex rules and multiple typos are discovered, it is often safer to pull the entire list offline, fix it in a text editor, and push it back.

For example, assume a Standard ACL was deployed to deny rogue AI subagents from the `19.168.10.10` subnet, but the Admin made a typo and missed the `2` in `192`:

```bash
agy# show run | section acl
acl standard 1 deny 19.168.10.10
acl standard 1 permit 192.168.10.0 0.0.0.255
```
Because appending new rules simply adds them to the absolute bottom of the list (below the permit), the Admin must:
1.  Copy the ACL output into an offline text editor.
2.  Fix the UUID/Subnet typo in the safety of the Staging Crucible.
3.  **Purge the active ACL** from the Orchestrator completely (`no acl standard 1`).
4.  Paste the corrected list back into the live `agy` CLI.

**The Danger:** The split-second between Step 3 and Step 4 leaves the Sandbox entirely unprotected (or completely locked down, depending on the implicit deny state). 

---

## 17.3 Agentic Sequence Injection (Sequence Numbers)

To avoid the dangerous exposure window of a full Purge, DevCore supports **Agentic Sequence Injection**. 

When the `Task Orchestrator Module` compiles an ACL, it automatically assigns a mathematical **Sequence Number** to every single ACE, typically incrementing by 10 (e.g., 10, 20, 30). This allows Admins to perform surgical strikes on an active list without bringing the rest of the security filter down.

While the `show run` command hides these numbers, they can be exposed using the specific `show acl` command:

```bash
agy# show acl
Standard Agentic Access List 1
   10 deny 19.168.10.10
   20 permit 192.168.10.0, wildcard bits 0.0.0.255
```

If the Admin spots the typo at Sequence 10, they do not need to delete the entire ACL. They simply enter the configuration mode, surgically delete Sequence 10, and inject the corrected rule back into the exact same slot.

```bash
agy# conf t
agy(config)# acl standard 1
agy(config-std-nacl)# no 10
agy(config-std-nacl)# 10 deny host 192.168.10.10
agy(config-std-nacl)# end
```

The Orchestrator instantly updates the in-memory ACL. The AI Swarm experiences zero downtime, and the `core_engine` remains completely secure.

---

## Chapter 17 Conclusion and Master Review

Chapter 17 outlines the critical administrative procedures required to maintain a live, Zero-Trust environment. Mistakes in security configurations are inevitable, but bringing down the entire game server to fix them is a relic of older architectures. By utilizing Agentic Sequence Injection, Tier 5 Admins can surgically rewrite the rules of reality for the AI Swarm without ever breaking the WebSocket streams.

### Traditional IT vs. DevCore Agentic Lore (Chapter 17 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional ACL modification methods into their DevCore Agentic equivalents:

*   **Text Editor Method** $\rightarrow$ **The Crucible Purge:** The brute-force method of ripping an entire ACL out of the active router (Orchestrator), editing it offline, and pasting it back in. It carries the risk of a split-second security blackout.
*   **Sequence Number Method** $\rightarrow$ **Agentic Sequence Injection:** The surgical method of targeting an individual ACE by its numerical index, allowing Admins to hot-patch security rules on the fly.
*   **Sequence Numbers (10, 20, 30)** $\rightarrow$ **Agentic Sequence Numbers:** The automatic index IDs assigned to every rule by `Task Orchestrator Module` to allow for zero-downtime injection and deletion.
*   **`show access-lists`** $\rightarrow$ **`agy show acl`:** The command used to expose the hidden Sequence Numbers of the active swarm filters.
