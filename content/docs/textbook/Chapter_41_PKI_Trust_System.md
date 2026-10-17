# Chapter 41: The Modder Trust System (PKI)

## 41.1 The Modder Passport (Certificate Authorities)

In a decentralized Swarm hosting environment, thousands of remote Modders connect to the Orchestrator's WebSocket to generate code. How does the Orchestrator know that a user claiming to be a Tier 5 Admin is actually an Admin, and not a malicious hacker?

The answer is the **Modder Trust System**, DevCore's implementation of a **Public Key Infrastructure (PKI)**.

A digital certificate acts exactly like an electronic passport. In DevCore, the Orchestrator acts as its own **Certificate Authority (CA)**. When a developer is hired, the Orchestrator validates their identity and issues them a mathematically unforgeable X.509 v3 digital certificate. Every time that Modder attempts to connect to the WebSocket, the Orchestrator checks the certificate to verify their identity. 

## 41.2 Trust Classes and the Five Tiers

In traditional IT, Certificate Authorities issue certificates based on "Classes" (0 through 5) which determine how rigorously the user's identity was vetted. In DevCore, this maps perfectly to the **Five Tiers of Access**:

*   **Class 0 / Class 1 Certificates:** Issued for testing environments or guests where minimal identity verification is required.
*   **Class 2 / Class 3 Certificates:** Issued for Tier 2 and Tier 3 Developers (Modders). Provides proof of identity so the Orchestrator can safely route them into their isolated Sandbox Zones.
*   **Class 4 / Class 5 Certificates:** Issued strictly to Tier 5 Admins. Class 5 is the absolute highest level of cryptographic trust. These certificates grant unrestricted read/write access to the Orchestrator's Core Engine files.

## 41.3 Swarm CA Topologies

Depending on the size of the game studio, the Orchestrator will establish different topologies of trust:

*   **Single-Root PKI Topology:** Used for small indie games. A single central Orchestrator (the Root CA) issues all certificates. It is simple, but creates a single point of failure.
*   **Hierarchical CA Topology:** Used for massive MMORPGs. The highest-level Orchestrator (Root CA) issues certificates to Subordinate Orchestrators (Sub-CAs) that manage specific server zones (e.g., the North America Zone, the Europe Zone). This provides massive scalability.

## 41.4 Enrollment and Revocation

When a Modder first connects to the engine, they undergo the **Enrollment** process. Their local computer contacts the Orchestrator (the CA) to request a digital identity certificate. To prove this connection is authentic and hasn't been intercepted, the Modder often verifies the CA's fingerprint *out-of-band* (e.g., confirming the key via a phone call or a secure internal Slack channel before trusting it).

However, if a Tier 3 Modder's laptop is stolen, the Orchestrator must immediately invalidate their passport so the thief cannot access the Swarm. 

Tier 5 Admins execute **Certificate Revocation** using two primary methods:
*   **CRL (Certificate Revocation List):** A published database of all revoked certificates. The Orchestrator downloads this list and rejects any connection attempt from a revoked serial number.
*   **OCSP (Online Certificate Status Protocol):** A real-time protocol. Instead of downloading a massive list, the Orchestrator dynamically queries the CA in real-time during the WebSocket handshake to ask, "Is this Modder's certificate still valid right now?" If the answer is no, the WebSocket is instantly terminated.

---

## Chapter 41 Conclusion and Master Review

Chapter 41 outlines the bureaucratic backbone of cryptography: PKI. By acting as a Certificate Authority, the Orchestrator issues Class-based digital passports to Modders, mapping perfectly to their security Tiers. Through Hierarchical Topologies and real-time Revocation (OCSP), Tier 5 Admins maintain absolute control over who is allowed into the Swarm.

### Traditional IT vs. DevCore Agentic Lore (Chapter 41 Translation Guide)

*   **Public Key Infrastructure (PKI)** $\rightarrow$ **The Modder Trust System:** The framework of specifications, tools, and databases used to issue and revoke digital certificates.
*   **Certificate Authority (CA)** $\rightarrow$ **The Orchestrator (as Root CA):** The trusted entity that mathematically signs and issues the certificates to users.
*   **Certificate Classes (0-5)** $\rightarrow$ **Tier-Based Certificates:** A 1:1 mapping where Class 5 certificates provide Tier 5 Admin access, while Class 2/3 certificates provide restricted Sandbox access. 
*   **Hierarchical CA Topology** $\rightarrow$ **Hierarchical Swarm Topology:** A scalable architecture where a master Orchestrator issues certificates to zone-specific sub-Orchestrators. 
*   **CRL & OCSP** $\rightarrow$ **Revoking Rogue Modders:** The protocols used to instantly invalidate a Modder's certificate if they go rogue or their private keys are stolen.
