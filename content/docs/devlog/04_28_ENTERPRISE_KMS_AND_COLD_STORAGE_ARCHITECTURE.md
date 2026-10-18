[//]: # (DOC_ID: SIRA-DEV-04_28 | VERSION: v1.0 | SCOPE: DEV)

# Enterprise KMS & Cold Storage Architecture

[//]: # (SECTION_ID: SIRA-DEV-04_28-SEC-1)
## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_28-SEC-1)
In a long-lived agentic development platform, sessions contain proprietary code, debugging traces, and user interactions. If session logs remain in plaintext, any local compromise exposes system history. However, naive encryption introduces the danger of permanent lockout if keys rotate.

The Enterprise KMS and Cold Storage Architecture (`security/keychain.py` and `security/cold_storage.py`) provides an enterprise two-tier key wrapping hierarchy and atomic cold-storage encryption.

```
+-------------------------------------------------------------+
|             Hardware Master Key (.devcore_master.key)       |
+-------------------------------------------------------------+
                              |
                     PBKDF2HMAC (100,000 Rounds)
                              |
                              v
+-------------------------------------------------------------+
|               Key Encryption Key (KEK / Fernet)             |
+-------------------------------------------------------------+
                              |
                     Wraps & Protects
                              |
                              v
+-------------------------------------------------------------+
|             Keychain Array (security/keychain.json)         |
|   [Wrapped DEK-1] (Legacy) -> Used for old sessions         |
|   [Wrapped DEK-2] (Active) -> Used for new sessions         |
+-------------------------------------------------------------+
                              |
                     Cold Storage Engine
                              |
                              v
+-------------------------------------------------------------+
|               Atomic Cold Storage Encryption                |
|      Encrypts brain transcripts via mkstemp + os.replace    |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_28-SEC-2)
## 2. Two-Tier Key Wrapping Hierarchy
[//]: # (SECTION_ID: SIRA-DOC-04_28-SEC-2)
1. **Master Key (`.devcore_master.key`)**: A high-entropy root key stored on the host filesystem.
2. **Key Encryption Key (KEK)**: Derived on-the-fly in process memory using PBKDF2HMAC with SHA-256 and 100,000 iterations. It is never stored on disk.
3. **Data Encryption Keys (DEKs)**: Symmetric Fernet AES keys used to encrypt individual files. All historical DEKs are wrapped with the KEK and stored in `security/keychain.json`.

---

[//]: # (SECTION_ID: SIRA-DEV-04_28-SEC-3)
## 3. Backwards-Compatible Key Ring Decryption
[//]: # (SECTION_ID: SIRA-DOC-04_28-SEC-3)
When decrypting historical session archives, the Keychain Manager unpacks all historical DEKs into a sequence of ciphers (`km.get_all_ciphers()`). The Cold Storage Manager iterates through the cipher ring until a key decrypts the file, ensuring zero data loss across key rotations.

---

[//]: # (SECTION_ID: SIRA-DEV-04_28-SEC-4)
## 4. Why Order Matters in KMS Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_28-SEC-4)
1. **Derive KEK Before Accessing DEKs**: The master key must be unlocked to derive the KEK before the keychain JSON file can be unwrapped.
2. **Check Ciphertext Header Before Encrypting**: Verifying that a file does not start with `b'gAAAAA'` prevents corrupting data with nested encryption.
3. **Atomic File Swapping on Disk**: Writing ciphertext to a temporary file before calling `os.replace()` guarantees that power or system crashes never leave half-encrypted files on disk.

---

[//]: # (SECTION_ID: SIRA-DEV-04_28-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_28-SEC-5)
**Q: What is key wrapping?**  
A: Encrypting one symmetric key (the DEK) with another symmetric key (the KEK), allowing key rings to be stored safely in JSON files.

**Q: What is Cold Storage?**  
A: Moving inactive or completed session transcripts into an encrypted, archived state to prevent unauthorized inspection.

**Q: Can an attacker who steals `keychain.json` read the transcripts?**  
A: No! The keys inside `keychain.json` are encrypted with the KEK. Without the physical `.devcore_master.key` file, the keychain cannot be unwrapped.
