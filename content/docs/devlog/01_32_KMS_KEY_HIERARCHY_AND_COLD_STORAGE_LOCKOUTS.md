[//]: # (DOC_ID: SIRA-DEV-01_32 | VERSION: v1.0 | SCOPE: DEV)

# KMS Key Hierarchy & Cold Storage Lockout Traps

[//]: # (SECTION_ID: SIRA-DEV-01_32-SEC-1)
## 1. The Problem: The Key Rotation Amnesia Trap
[//]: # (SECTION_ID: SIRA-DOC-01_32-SEC-1)
In enterprise cryptography, encrypting sensitive data with a single static key creates a catastrophic vulnerability: if the key is compromised, all data past, present, and future is exposed. To mitigate this, security policies mandate frequent key rotation.

However, naive key rotation introduces the **Historical Lockout Trap**. When the encryption engine rotates to a new Data Encryption Key (DEK), any historical files or session transcripts encrypted with the old DEK become completely undecryptable unless the old keys are securely archived.

```
+-------------------------------------------------------------+
|               Historical Session Transcript                 |
|             Encrypted with DEK-1 (January 2026)             |
+-------------------------------------------------------------+
                              |
                     KEY ROTATION OCCURS
                     Active Key Shifts to DEK-2
                              |
                              v
+-------------------------------------------------------------+
|                Attempting to Decrypt with DEK-2             |
|          [FATAL: InvalidToken / Cryptographic Failure]      |
|    - Old key discarded from configuration                   |
|    - Historical transcripts permanently locked              |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_32-SEC-2)
## 2. Double-Encryption and Non-Atomic Writes
[//]: # (SECTION_ID: SIRA-DOC-01_32-SEC-2)
Two additional fatal traps plagued initial cold-storage prototypes:
1. **Double-Encryption**: If the backup routine ran twice, it re-encrypted already encrypted ciphertext. Decrypting only peeled off the outer layer, leaving files in a corrupted state.
2. **Partial Write Crashes**: Directly opening the target file in write mode (`open(file, 'wb')`) wiped the plaintext before writing the ciphertext. If power cut or Python crashed mid-write, data was permanently erased.

---

[//]: # (SECTION_ID: SIRA-DEV-01_32-SEC-3)
## 3. The Solution: Tiered Keychain & Atomic Swapping
[//]: # (SECTION_ID: SIRA-DOC-01_32-SEC-3)
Siraugga resolved this with the Enterprise Keychain (`security/keychain.py`) and Cold Storage Manager (`security/cold_storage.py`):
1. **Two-Tier Key Hierarchy**: The hardware master key (`.devcore_master.key`) derives a Key Encryption Key (KEK) using PBKDF2HMAC (100,000 rounds). The KEK wraps an array of historical DEKs in `security/keychain.json`.
2. **Historical Key Ring Decryption**: When unlocking archives, the engine tests all historical DEKs sequentially until the valid key decrypts the file.
3. **Prefix Guarding**: Files starting with Fernet's `b'gAAAAA'` magic prefix are skipped to prevent double encryption.
4. **Atomic Swapping**: Files are encrypted to a temporary file (`tempfile.mkstemp`) and swapped into place using atomic `os.replace()`.

---

[//]: # (SECTION_ID: SIRA-DEV-01_32-SEC-4)
## 4. Why Order Matters in Cryptographic Cold Storage
[//]: # (SECTION_ID: SIRA-DOC-01_32-SEC-4)
1. **Verify Token Header Before Encrypting**: Checking for the `b'gAAAAA'` header before cipher execution guarantees archives are never double-encrypted.
2. **Write Temp File Before OS Replace**: Writing to a temporary file on the same filesystem ensures that if a disk failure occurs, the original unencrypted file remains unharmed.
3. **Derive KEK Before Reading Keychain**: The master key must be unlocked and PBKDF2-derived before parsing `keychain.json` to decrypt wrapped DEKs.

---

[//]: # (SECTION_ID: SIRA-DEV-01_32-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_32-SEC-5)
**Q: What is the difference between a KEK and a DEK?**  
A: A Data Encryption Key (DEK) encrypts actual files. A Key Encryption Key (KEK) is a master key that encrypts and protects the collection of DEKs.

**Q: Why use 100,000 iterations in PBKDF2?**  
A: A high iteration count slows down attackers trying to guess the master password using specialized GPU cracking rigs.

**Q: What is `os.replace()`?**  
A: A built-in Python function that atomically replaces a file. In the event of a system crash, the file is either completely updated or untouched—never corrupted.
