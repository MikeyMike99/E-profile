[//]: # (DOC_ID: SIRA-TXT-CH13 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 13: AAA Usage and Operation

To maintain the absolute integrity of a live, multiplayer game state, the DevCore network must ruthlessly control who is allowed to connect and what they are mechanically capable of doing once inside. These design requirements form the backbone of the **Siraugga Network Security Policy**, governed dynamically by the `Access Control Module`. 

The policy specifies exactly how Tier 5 Admins, Tier 2 Modders, and autonomous AI subagents navigate the Sandboxes. Furthermore, it mandates the implementation of a rigid accounting system that tracks every login, every WebSocket JSON delta, and every terminal command executed by the AI swarm.

This scalable security framework is defined by the **AAA Architectural Framework** (Authentication, Authorization, and Accounting).

---

## 13.1 The AAA Triad (The Agentic Credit Card)
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-13_1)

To understand AAA in the context of DevCore, we compare it to a corporate credit card issued to an AI subagent:

1.  **Authentication (Who are you?):** Modders and AI subagents must mathematically prove their identity. DevCore centralizes this via cryptographic keys and the FAIM (Federated Agentic Identity Management) system.
2.  **Authorization (How much can you spend?):** Once authenticated, the Orchestrator determines which resources the entity can access. For an AI, this defines its **Agentic Tool Whitelist** (e.g., "Agent UUID-104 is authorized to access `game_demo/` using the `view_file` tool only").
3.  **Accounting (What did you spend it on?):** Accounting records every action the user or AI takes. In DevCore, if an AI burns 10,000 LLM tokens executing a bash script, the accounting system logs exactly what files were accessed, how long the operation took, and what specific code was altered.

---

## 13.2 Centralized Agentic Authentication
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-13_2)

DevCore implements AAA services using a **Server-Based (Centralized) Authentication** model. 

Instead of trusting local game clients, remote Tier 2 Modders and their spawned AIs connect directly to the central Siraugga Orchestrator (`App Router Module`). This central AAA system independently maintains databases for the three AAA functions. It evaluates incoming connections, verifies the cryptographic tokens, and dictates access. 

When a subagent needs to communicate with the central Orchestrator, it utilizes one of two primary agentic protocols, adapted from traditional IT frameworks:

### RADI vs. TACAS+ (The Protocol Showdown)
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-1)

*   **RADI (Rapid Agentic Data Interchange - based on RADIUS):** 
    *   **Transport:** Uses lightweight UDP / fast JSON WebSockets.
    *   **Functionality:** Combines Authentication and Authorization into a single rapid step, but separates accounting. 
    *   **Security:** Only encrypts the password/token in the access-request packet; the remaining JSON payload (username, authorized services) is sent in cleartext to maximize speed. 
    *   **Customization & Use Case:** It has no option to authorize commands on a per-agent basis. It is utilized purely for low-level, high-speed NPC chatbots where extensive accounting logs are kept, but granular terminal authorization isn't required.
*   **TACAS+ (Terminal Access Control Agentic System - based on TACACS+):**
    *   **Transport:** Uses highly reliable TCP.
    *   **Functionality:** Strictly separates Authentication, Authorization, and Accounting, allowing for modular, ultra-secure architecture.
    *   **Security:** Encrypts the entire body of the packet. Uses bidirectional Semantic CHAP (Challenge Handshake).
    *   **Customization & Use Case:** Allows the Orchestrator to authorize specific terminal commands (e.g., `run_command` in `wsl.exe`) on a per-agent basis. This is the mandatory protocol for Tier 5 Admins and highly privileged `Coding` subagents that alter the `TIER_SAFE_WORKSPACE`.

---

## 13.3 AAA Accounting Logs and The Transcript Ledger
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-13_3)

In a Zero-Trust architecture, Auth and Authorization keep the doors locked, but **Accounting** is how you catch a thief who already has the keys. Centralized AAA ensures that records from all Sandboxes are sent to a centralized repository, drastically simplifying the forensic auditing of AI actions.

In DevCore, AAA Accounting data is collected and reported directly into the **Agentic Transcript Logs** (e.g., `transcript.jsonl` and `transcript_full.jsonl`). 

Whenever a Modder or an AI subagent connects, the accounting process generates a `start` message. When the connection closes or the AI terminates, a `stop` message is recorded. The Siraugga framework collects three primary types of accounting data:

1.  **Connection Accounting:** Captures information about all outbound connections made by the client (e.g., when a Modder opens a WebSocket stream to the server).
2.  **System Accounting:** Captures all system-level events (e.g., when a Tier 5 Admin triggers the `POST /api/reload` endpoint to hot-patch the core engine).
3.  **EXEC / Command Accounting:** The most critical log in DevCore. The central Orchestrator keeps a hyper-detailed ledger of exactly what the authenticated AI does in the terminal sandbox. It logs the exact timestamp, the agent's UUID, and the exact `run_command` bash strings executed by the AI.

### Physical Topology vs. Sandbox Topology
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-2)
In traditional networking, a physical topology maps out Server Room 2158 connecting via cables to IT Office 2159 and remote Classrooms. 

In DevCore, this physical topology maps directly to the **Sandbox Isolation Topology**:
*   **The Server Room (Host OS):** The physical Linux machine running the master Quart `App Router Module` and maintaining the immutable accounting logs in `[LOCAL_BRAIN_VAULT]/`.
*   **The Remote Classrooms (Modder Workspaces):** The isolated `/playground/` directories where Tier 2 Modders and AI agents execute their logic. The accounting logs track exactly how much data crosses the "cables" (WebSockets) between the untrusted workspaces and the core Server Room, providing irrefutable evidence against any rogue agent or cybercriminal attempting malicious actions.

---

## Chapter 13 Conclusion and Master Review
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-3)

Chapter 13 codifies the operational mechanics of the Zero-Trust Architecture. It dictates exactly *how* the Siraugga framework manages its massive, decentralized swarm of Tier 2 Modders and autonomous AI subagents. By utilizing a Centralized AAA framework, the Orchestrator maintains absolute dominion over who enters the system, what tools they are permitted to wield, and exactly how many computational tokens they are allowed to burn. 

The structural translation of traditional networking protocols into the agentic sphere (RADI vs TACAS+) provides Tier 5 Admins with the flexibility to prioritize low-latency for in-game NPCs while simultaneously enforcing military-grade encryption for critical core engine modifications. Finally, the Accounting logs—the immutable Agentic Transcripts—serve as the ultimate forensic ledger, ensuring that no AI action goes unrecorded.

### Traditional IT vs. DevCore Agentic Lore (Chapter 13 Translation Guide)
[//]: # (SECTION_ID: SIRA-TXT-CH13-SEC-4)

To maintain absolute clarity, here is the master translation of traditional cybersecurity terms into their DevCore Agentic equivalents established in this chapter:

*   **The AAA Framework** $\rightarrow$ **The Agentic Triad:** The core operational philosophy governing AI behavior: Identity (Authentication), Tool Whitelists (Authorization), and Token/Action Tracking (Accounting).
*   **Centralized AAA Server** $\rightarrow$ **The Siraugga Orchestrator (`App Router Module`):** The master backend that independently evaluates WebSocket connections and enforces access control across all isolated Sandbox nodes.
*   **RADIUS** $\rightarrow$ **RADI (Rapid Agentic Data Interchange):** A lightweight, unencrypted protocol utilized exclusively for high-speed, low-latency NPC chatbot generation where granular terminal authorization is not required.
*   **TACACS+** $\rightarrow$ **TACAS+ (Terminal Access Control Agentic System):** The fully encrypted, TCP-based protocol utilized for Tier 5 Admins and privileged `wsl.exe` subagents, requiring strict per-command authorization.
*   **AAA Accounting Logs** $\rightarrow$ **Agentic Transcript Logs (`transcript.jsonl`):** The immutable ledger that collects every piece of usage data, start/stop events, and token burn rates from the swarm.
*   **EXEC (Command) Accounting** $\rightarrow$ **Bash String Logging:** The meticulous tracking of every single `run_command` executed by an AI agent inside the Linux terminal, preserving forensic evidence of any malicious activity.
*   **Physical Topology (Server Rooms vs Classrooms)** $\rightarrow$ **Sandbox Topology:** The Host OS (the central physical machine running Quart) acting as the Server Room, connected via WebSockets to the isolated Modder Workspaces (the remote Classrooms).
