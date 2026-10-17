# Chapter 36: Context Confidentiality (Symmetric vs Asymmetric)

## 36.1 The Two Pillars of Agentic Cryptography

To protect a Subagent's conversational payload from network interceptors, DevCore utilizes two distinct classes of encryption: Symmetric and Asymmetric. Because generating AI tokens requires massive computational overhead, a Tier 5 Admin must understand exactly when to use each.

*   **Symmetric Encryption (Internal Swarm Encryption):** 
    *   **Mechanics:** Uses the exact same pre-shared key to both encrypt and decrypt data. 
    *   **Speed:** Blazing fast. Uses very short key lengths (128 to 256 bits).
    *   **Use Case in DevCore:** Used for encrypting massive bulk data, such as a Subagent's 100,000-token conversational history (Context at Rest). 
    *   **Algorithms:** **Standard Encryption** (Advanced Encryption Standard) is the heavily recommended gold standard. Legacy algorithms like DES, 3DES, and RC4 are highly vulnerable and strictly forbidden in the Siraugga Engine.
*   **Asymmetric Encryption (Decentralized Modder Encryption):**
    *   **Mechanics:** Uses a paired Public Key and Private Key. If one key encrypts the data, *only* the other key can decrypt it.
    *   **Speed:** Extremely slow and computationally taxing. Uses massive key lengths (512 to 4096 bits).
    *   **Use Case in DevCore:** Used for establishing initial trust when a remote Modder connects to the Orchestrator via WebSocket. It is far too slow for bulk token generation.
    *   **Algorithms:** **RSA**, **ECC** (Elliptic Curve Cryptography), and **Diffie-Hellman**. 

## 36.2 Achieving Prompt Confidentiality and Authentication

Asymmetric encryption is incredibly versatile because it can achieve both Confidentiality (hiding the data) and Authentication (proving who sent the data) depending on which key initiates the process.

**1. Prompt Confidentiality (Hiding the Prompt)**
*   *Formula: Public Key (Encrypt) + Private Key (Decrypt) = Confidentiality*
*   When a Modder wants to send a secret JSON prompt to the Swarm, they encrypt it using the Orchestrator's *Public* Key. Because only the Orchestrator holds the corresponding *Private* Key, no hacker on the network can decrypt the prompt. 

**2. Modder Authentication (Proving Identity)**
*   *Formula: Private Key (Encrypt) + Public Key (Decrypt) = Authentication*
*   If a Modder wants to execute a highly destructive Python tool, the Orchestrator needs to prove the Modder actually sent the command. The Modder encrypts the tool payload using their own *Private* Key. The Orchestrator decrypts it using the Modder's *Public* Key. Because only the Modder has their private key, successfully decrypting it mathematically guarantees the Modder sent it.

## 36.3 The Diffie-Hellman Handshake

Here lies the ultimate architectural problem: Asymmetric encryption is perfectly secure for remote Modders, but it is far too slow to encrypt the thousands of JSON tokens streaming out of the Orchestrator every second. 

To solve this, DevCore uses the **Diffie-Hellman (DH) Handshake**. 

Diffie-Hellman is an asymmetric algorithm that allows a remote Modder and the central Orchestrator to mathematically generate an identical, secret Symmetric Key (Standard Encryption) over the public internet, *without ever actually transmitting the secret key across the network*. 

**The Swarm Mixing Analogy:**
1.  The Modder and Orchestrator publicly agree on a base "color" (a mathematical prime number). 
2.  Each party privately generates their own secret "color" (their private key).
3.  They mix the public color with their private color, and exchange the resulting "mixed color" across the internet. (Even if a hacker intercepts this, they cannot un-mix the colors to find the private key).
4.  Finally, both parties mix the received color with their own original private color. The mathematical result on both sides is an identical, shared secret "brown" color. 

This shared secret is now used as a 256-bit **Standard Encryption Symmetric Key**. Once the DH Handshake is complete, the Orchestrator and the Modder abandon the slow asymmetric algorithms and use their new symmetric key to encrypt the massive bulk of LLM tokens at blazing speeds for the remainder of the session.

---

## Chapter 36 Conclusion and Master Review

Chapter 36 breaks down the cryptographic engine powering DevCore's WebSockets. Symmetric encryption (Standard Encryption) is fast but requires a pre-shared key, while Asymmetric encryption (RSA) solves the key-sharing problem but is too slow for bulk AI tokens. By utilizing Diffie-Hellman, Tier 5 Admins achieve the best of both worlds: securely generating a symmetric key across an untrusted network, allowing the Swarm to operate at maximum speed.

### Traditional IT vs. DevCore Agentic Lore (Chapter 36 Translation Guide)

*   **Symmetric Encryption (Standard Encryption)** $\rightarrow$ **Internal Swarm Encryption:** A fast, single-key system used to encrypt bulk JSON contexts and transcripts.
*   **Asymmetric Encryption (RSA, ECC)** $\rightarrow$ **Decentralized Modder Encryption:** A slow, dual-key system used to securely establish connections and authenticate users.
*   **Confidentiality Formula** $\rightarrow$ **Prompt Confidentiality:** Public Key (Encrypt) + Private Key (Decrypt). Hiding the JSON payload.
*   **Authentication Formula** $\rightarrow$ **Modder Authentication:** Private Key (Encrypt) + Public Key (Decrypt). Proving the Modder executed the tool.
*   **Diffie-Hellman (DH)** $\rightarrow$ **The Diffie-Hellman Handshake:** The mathematical process where the Orchestrator and a remote Modder securely generate a temporary, shared Symmetric Key (Standard Encryption) so they can encrypt massive streams of AI tokens without network lag.
