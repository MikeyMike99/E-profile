# The encrypt_me (v3.0) Cryptographic Architecture

## 1. Overview & Classification
* **Developer:** Michael Robberts
* **Project Classification:** Independent Research & Development
* **Status:** Proprietary Zero-Knowledge Recovery Tool
* **Core Function:** High-security, multi-user encryption utility utilizing a split-key architecture to secure files and archives (.vault).

## 2. Core Cryptographic Specifications
* **Algorithm:** AES-128/256 (Fernet) for data-at-rest confidentiality.
* **Key Derivation (KDF):** PBKDF2HMAC with SHA-256. Enforces 100,000 iterations to mitigate GPU-accelerated brute-force attacks.
* **Salting:** Every registered user record is protected by a cryptographically secure 16-byte random salt.
* **Immobilizer:** The tool features a hard-coded time-bomb (`check_immobilizer()`) that instantly kills the process and prevents decryption if the execution date surpasses the evaluation license date.

## 3. The Identity-Gated Administrative Recovery (IGAR)
The most critical feature of this tool is its **Zero-Knowledge Shadow Bridge**. It completely eliminates the massive liability of a global "Master Password". 

If a user loses their password, there is no master key stored on disk to recover the data. Instead, the tool relies on an offline, cryptographic challenge-response protocol:
1. **The Manifest Generation:** When a file is encrypted, the system generates a 64-character Entropy Pool (`Cipher`) and a 6-digit Positional Map (`Secret_Key`). 
2. **The Recovery Vault:** The true Master Key is encrypted using a `recovery_pass` derived entirely from slicing the Cipher using the Map indices. 
3. **Identity Verification:** To even view the Cipher and Map, the user must prove their identity by entering a valid, pre-registered username.
4. **The Offline Challenge:** The user sends the Cipher and Map to the Developer out-of-band. The Developer calculates the one-time `Recovery Token` and sends it back.
5. **Metadata Rotation:** To prevent token-replay attacks, the moment the file is unlocked and saved, the entire Cipher, Map, and Token are mathematically rotated and regenerated. The old token becomes permanently useless.

## 4. Integration into the Antigravity Engine
This tool is perfect for securing the **Global Forensic Vault** and **Data in Transit**:
* **Encryption (Agent-Accessible):** The Antigravity Agent can use this tool to autonomously wrap `transcript.jsonl` files and system event logs into `.vault` files before transmitting them to AWS Glacier. The Agent generates the vault, but it does *not* possess the recovery token or the master key.
* **Decryption (Super Admin Only):** By wrapping this utility into an Agent Tool (e.g., an MCP Server), we enforce strict RBAC. The `vault_decrypt` command will programmatically reject execution unless the Agent's session flag verifies they are running as `super_admin`. 
