# Chapter 16: Configuring Agentic Control Lists

## 16.1 Crafting the Agentic Policy

Before a Tier 5 Admin configures a complex Agentic Control List (ACL) in the live engine, strict deployment procedures must be followed. A single typo in an ACL can instantly sever the connection for an entire Modder Swarm or accidentally grant an AI root access.

When configuring an ACL for the `Task Orchestrator Module`, it is mandated that you:
1.  **Draft Offline:** Use a text editor to write out the specifics of the security policy.
2.  **Add Remarks:** Always include explicit `remark` commands to document *why* the ACL was created.
3.  **Test in the Crucible:** Always thoroughly test the ACL in the Staging Crucible to ensure it doesn't trigger an accidental Semantic Mantrap lock-out.

## 16.2 Standard and Extended ACL Syntax (`agy` CLI)

DevCore allows Admins to configure these lists via the native `agy` Command Line Interface. While legacy configurations used arbitrary numbers, **Named ACLs** are the absolute standard.

### Standard Named Agentic ACLs
Standard ACLs filter strictly based on the Agent's identity (UUID) or the Modder's subnet. To enter the standard configuration mode:

```bash
agy(config)# acl standard NO-ACCESS
agy(config-std-nacl)# remark Deny all rogue agents from Modder Block 192.168.1.0
agy(config-std-nacl)# deny 192.168.1.0 0.0.0.255
agy(config-std-nacl)# permit any
agy(config-std-nacl)# exit
```

### Extended Named Agentic ACLs
Extended ACLs are significantly more complex. They filter by Identity (UUID) *and* by Semantic Directory (similar to network Protocols and Ports). 

```bash
agy(config)# acl extended NO-CORE-ACCESS
agy(config-ext-nacl)# remark Deny core engine access for this specific agent
agy(config-ext-nacl)# deny tcp host Agent-104 any eq /core_engine/
agy(config-ext-nacl)# permit tcp host Agent-104 any eq /playground/
```
*Note: The `log` keyword can be appended to the end of any ACE. This forces the Orchestrator to generate an informational message in `transcript.jsonl` every time the rule is matched. Because logging is computationally expensive, it should only be used for active security auditing.*

## 16.3 Translating Ports to Semantic Directories

In traditional networking, extended ACLs filter based on Internet Protocols (TCP, UDP) and Port Numbers (80 for HTTP, 22 for SSH). In DevCore, these concepts translate directly to **Semantic Directories governed by the Raugus Resolver**.

When defining an Extended ACL, the Orchestrator maps standard network ports to explicit physical directories in the Sandbox:
*   **Port 80 / 443 (HTTP/HTTPS) $\rightarrow$ The Safe Workspace (`/playground/game_demo/`)**: The standard, front-facing directories where Modders and AIs build the game assets.
*   **Port 22 (SSH) $\rightarrow$ The Core Engine (`/core_engine/`)**: The root orchestration directories containing `App Router Module` and security logic. The most dangerous "port," heavily restricted to Tier 5 Admins.
*   **Port 21 (FTP) $\rightarrow$ The Asset Vaults (`/assets/`)**: Dedicated directories for heavy binary file transfer and 3D models.

An Admin can configure the ACL using either the absolute directory path or its mathematically mapped port number. Both commands achieve the exact same path restriction through the Raugus Resolver:
```bash
agy(config)# acl extended 100 permit tcp any any eq /playground/game_demo/
!or...
agy(config)# acl extended 100 permit tcp any any eq 80
```

## 16.4 Stateful Agentic Firewalls (The `established` Keyword)

Perhaps the most critical security feature in the DevCore filtering engine is the `established` keyword, a 1st-generation firewall feature adapted to prevent **Prompt Injections**.

If an AI subagent is permitted to search the web or query an external API (like an untrusted Modder's database), the system faces a severe vulnerability: the external server could send back a malicious payload designed to hijack the AI's context window.

By appending the `established` keyword to an inbound ACL, the Orchestrator implements a **Stateful Agentic Firewall**. 
*   The AI is permitted to send a request *out* to the public network.
*   The web server is permitted to send the exact returning reply *in*.
*   However, if the external web server (or a malicious user) attempts to arbitrarily initiate a *new* connection to inject commands into the AI's prompt, **it is violently denied.** 

The `established` parameter dictates that a match only occurs if the returning JSON segment belongs to an existing, AI-initiated thought process. Without this parameter, the AI would be completely exposed to external hijackers.

---

## Chapter 16 Conclusion and Master Review

Chapter 16 translates the dense syntax of legacy networking ACLs directly into the native Siraugga `agy` command line. By mapping traditional network ports to physical Sandbox directories via the Raugus Resolver, Tier 5 Admins can utilize standard ACL syntax to effortlessly lock down sensitive core engine files while leaving the `playground` folders open for the Swarm. Additionally, the introduction of the `established` keyword provides the framework its ultimate defense against external prompt injections, ensuring that the AI dictates the conversation, not the internet.

### Traditional IT vs. DevCore Agentic Lore (Chapter 16 Translation Guide)

To maintain absolute clarity, here is the master translation of traditional ACL syntax terminology into their DevCore Agentic equivalents established in this chapter:

*   **Offline Drafting** $\rightarrow$ **The Staging Crucible:** The strict rule that Admins must draft and test all JSON ACLs offline before deploying them to the live engine.
*   **Standard / Extended Syntax** $\rightarrow$ **The `agy` CLI ACL Syntax:** Replaces Cisco syntax with the native `agy acl` commands to manage the AI swarm.
*   **Internet Ports (80, 22, 21)** $\rightarrow$ **Semantic Directories:** The Raugus Resolver maps traditional ports to strict Sandbox paths.
    *   **Port 80/443 (HTTP/HTTPS)** $\rightarrow$ **The Safe Workspace (`/playground/game_demo/`)**
    *   **Port 22 (SSH)** $\rightarrow$ **The Core Engine (`/core_engine/`)**
    *   **Port 21 (FTP)** $\rightarrow$ **The Asset Vaults (`/assets/`)**
*   **TCP Established** $\rightarrow$ **Stateful Agentic Firewalls:** A security mechanic preventing Prompt Injections. It allows returning data from an AI-initiated web search, but violently denies any unsolicited external data from hijacking the AI's context window.
