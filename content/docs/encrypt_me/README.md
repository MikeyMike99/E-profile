[//]: # (DOC_ID: ENCR-VAULT-README | VERSION: v1.1 | SCOPE: EncryptMe Multi-User Vault)

# encrypt_me (v3.0) User & System Guide

* **Developer:** Michael Robberts
* **Project Classification:** Independent Research & Development
* **License Type:** Temporary Evaluation License

---

## 1. Project Overview
[//]: # (SECTION_ID: ENCR-VAULT-README-SEC-1)
`encrypt_me` is a high-security, multi-user encryption utility. It allows a single file (or ZIP archive) to be shared among a team, where each member uses their own unique password to access the same data.

---

## 2. Security Specifications
[//]: # (SECTION_ID: ENCR-VAULT-README-SEC-2)
* **Encryption Standard:** AES-128/256 (Fernet) for high-level data confidentiality.
* **Key Protection:** PBKDF2HMAC with SHA256 (100,000 iterations).
* **Dynamic Metadata:** Every save event triggers a cryptographic refresh of the file header.
* **Binary Signature:** Proprietary MRSV binary handshake prevents processing of non-vault files.
* **Immobilizer Protocol:** Hard-coded kill-switch revokes decryption capabilities after evaluation period.

---

## 3. User Guide & Team Operations
[//]: # (SECTION_ID: ENCR-VAULT-README-SEC-3)
1. **To Encrypt:** Drag and drop any file into the `.exe`. Add team members and set passwords.
2. **To Decrypt:** Drag the `.vault` file into the `.exe`. Select Login (Option 1).
3. **The Editing Cycle:**
   * Select a registered user.
   * Enter password to decrypt to a secure memory buffer.
   * Perform modifications.
   * Save and re-encrypt automatically with rotated metadata.
4. **Emergency Recovery:**
   * Uses Identity-Gated Administrative Recovery (IGAR).
   * Generates a 64-character entropy pool and 6-digit positional map for out-of-band admin recovery.
