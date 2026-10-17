# Module 5: Agentic Cryptography & Trust Systems

## What Will I Learn in this Module?
This module explains the cryptographic foundations that allow decentralized Modders and AIs to trust each other over the web. You will learn:
* **The Orchestrator Cipher Suite:** How Symmetric and Asymmetric encryption protect the WebSocket tunnel.
* **The Encryption Paradox:** Why strong encryption actually creates blindspots for the NGPF.
* **The Modder PKI Trust System:** How the Orchestrator acts as the Root Certificate Authority (CA) to assign Tier-based credentials.
* **Agentic Digital Signatures:** How tools are mathematically signed to ensure non-repudiation.

---

## 5.1 The Orchestrator Cipher Suite
Because the DevCore engine allows third-party Modders to connect to the host server globally via WebSockets, that connection must be mathematically sealed to prevent packet sniffing. This is achieved through the **Orchestrator Cipher Suite**.

The cipher suite utilizes a hybrid cryptographic approach:
1.  **Asymmetric Encryption (RSA/Public Key):** Used purely for the initial handshake. The Modder's browser and the Orchestrator exchange public keys to securely establish their identities. This is highly secure but incredibly CPU-intensive.
2.  **Symmetric Encryption (Standard Encryption):** Once the asymmetric handshake is verified, the two parties agree on a single, shared "session key." All subsequent JSON telemetry and tool calls are encrypted symmetrically using this session key, allowing for blisteringly fast execution without burning CPU cycles.

### The Encryption Paradox
While the cipher suite guarantees that outside hackers cannot intercept the WebSockets, it introduces the **Encryption Paradox**. Because the tunnel is perfectly encrypted, standard perimeter firewalls cannot see the JSON payloads inside. The prompt injections are effectively cloaked in encryption. This is why the Next-Gen Prompt Firewall (NGPF) must sit *behind* the decryption layer on the host, where it can inspect the raw text before it hits the Subagent.

## 5.2 The Modder PKI Trust System
How does the Orchestrator know that the person connecting to the WebSocket is actually an authorized Tier 3 Modder and not a random script kiddie? It uses a **Public Key Infrastructure (PKI) Trust System**.

In this system, the DevCore Orchestrator acts as the **Root Certificate Authority (Root CA)**. 
When a Modder is hired, the Orchestrator generates a digital certificate that explicitly lists their assigned Tier (e.g., Tier 3 Developer) and mathematically signs it with the Orchestrator's private key. When the Modder connects, they present this certificate. Because the certificate is mathematically bound to the Orchestrator's root authority, the server implicitly trusts it and assigns them to their Tier 3 Sandbox.


## 5.3 Agentic Digital Signatures & Non-Repudiation
When a Modder or a Subagent executes a high-risk tool call (such as `write_to_file` or `run_command`), the Orchestrator must be absolutely certain that the payload was not altered in transit by a Man-in-the-Middle (MitM) attack.

To solve this, DevCore utilizes **Agentic Digital Signatures**. 

Before the JSON tool call is sent, the Subagent hashes the payload and encrypts that hash using its private key. When the Orchestrator receives the tool call, it decrypts the signature using the Subagent's public key. If the hashes match, two things are mathematically proven:
1.  **Integrity:** The tool call was not tampered with. Not a single character was changed.
2.  **Non-Repudiation:** Because only the specific Subagent (and its parent Modder) possessed the private key used to sign the payload, they cannot deny executing the command. If a malicious script is compiled, the mathematical proof leads directly back to the Modder.

## 5.4 Certificate Revocation (CRL & OCSP)
What happens when a Tier 3 Developer goes rogue and their Agentic Digital Signatures are found all over a malicious breach? Their access must be instantly terminated.

The Orchestrator utilizes a **Certificate Revocation List (CRL)** and the **Online Certificate Status Protocol (OCSP)**. When a Modder's PKI certificate is revoked by a Tier 5 Admin, their unique ID is immediately broadcasted to the CRL. Every time a Subagent attempts to connect to the WebSocket, the Semantic Firewall checks the OCSP. If the Modder's certificate has been revoked, the firewall drops the connection and all active Subagents associated with that Modder are instantly terminated.
