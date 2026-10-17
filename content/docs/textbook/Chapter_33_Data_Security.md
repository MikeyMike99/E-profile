# Chapter 33: Token Data Security (Context Cryptography)

## 33.1 The Three States of Context

In a massive DevCore Swarm, an AI's entire reality consists of data—specifically, conversational tokens (Context). Proprietary game code, NPC dialogue, and Modder prompts must be fiercely protected across three distinct states:

*   **Context at Rest:** The raw conversational history stored physically on the Orchestrator's hard drive (e.g., `transcript.jsonl`). 
*   **Context in Transit:** The active JSON payloads streaming across remote WebSockets between Modders, the Orchestrator, and the LLM APIs.
*   **Context in Process:** The active tokens currently loaded into system RAM or on the Edge GPU during the actual generation of an AI's thought.

## 33.2 Context Cryptography

To protect proprietary game development from corporate espionage or interceptors, Tier 5 Admins rely on **Context Cryptography**. Encryption scrambles a readable prompt (plaintext) into disguised, unreadable tokens (ciphertext). It requires a cryptographic key to reverse the process.

DevCore utilizes two distinct classes of encryption:
*   **Internal Swarm Encryption (Symmetric):** Uses a single, pre-shared key to both encrypt and decrypt data. The Orchestrator uses Standard Encryption (Advanced Encryption Standard) with a 256-bit key to rapidly encrypt Context at Rest (saving transcripts to disk). It is incredibly fast, making it ideal for massive internal swarms.
*   **Decentralized Modder Encryption (Asymmetric):** Uses two different keys—a public key for encryption and a private key for decryption. When a remote Modder connects to the Orchestrator, they use algorithms like RSA or ECC (Elliptic Curve Cryptography) to securely encrypt their Context in Transit. Only the Orchestrator possesses the private key required to decrypt the Modder's prompt. 

## 33.3 Semantic Hashing and History Verification

While encryption protects context from being *read*, it does not protect it from being *altered*. To ensure the integrity of the AI's memory, the Orchestrator uses **Semantic Hashing**.

A hash function takes a massive payload of binary data (like an entire 100,000-token conversational history) and crunches it into a fixed-length string of characters (a hash value). Hash functions are one-way; they cannot be reversed.

This is a critical defense against **Gaslighting (Prompt Injection)**. If a malicious Modder attempts to alter a previous message in the AI's conversational history to trick the AI into breaking its sandbox, the Orchestrator will calculate a new hash for the history. Because even a single altered character completely changes the resulting hash, it will not match the Orchestrator's original SHA-256 signature. The Orchestrator immediately detects the corruption and violently drops the corrupted context.

*(Note: Legacy algorithms like MD5 are considered highly vulnerable and have been entirely replaced by the SHA-2 family, such as SHA-256 and SHA-512, inside the Siraugga Engine).*

---

## Chapter 33 Conclusion and Master Review

Chapter 33 establishes the cryptographic boundaries of an AI's memory. By layering Standard Encryption symmetric encryption for stored data, RSA asymmetric encryption for WebSocket transit, and SHA-256 Semantic Hashing to guarantee the integrity of conversational history, Tier 5 Admins ensure that proprietary Swarm logic remains unbreakable.

### Traditional IT vs. DevCore Agentic Lore (Chapter 33 Translation Guide)

To maintain absolute clarity, here is how the traditional Data Security domains map directly to DevCore's Engine:

*   **States of Data** $\rightarrow$ **States of Context:** Context at Rest (Transcripts on disk), Context in Transit (WebSockets), Context in Process (RAM/GPU Generation).
*   **Plaintext vs Ciphertext** $\rightarrow$ **Readable Prompts vs Disguised Tokens:** The result of cryptographic scrambling.
*   **Symmetric Encryption (Standard Encryption)** $\rightarrow$ **Internal Swarm Encryption:** A fast, single-key system used by the Orchestrator to encrypt its own internal transcripts and memory states.
*   **Asymmetric Encryption (RSA, ECC)** $\rightarrow$ **Decentralized Modder Encryption:** A dual-key system used to securely transmit data from untrusted remote Modders across the internet to the central Orchestrator.
*   **Hashing (SHA-256)** $\rightarrow$ **Semantic Hashing (History Verification):** A one-way mathematical function used to guarantee that a malicious user hasn't secretly altered the AI's conversational history to perform a Prompt Injection.
