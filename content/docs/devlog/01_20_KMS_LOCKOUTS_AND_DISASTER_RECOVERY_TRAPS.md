# Chapter 01_20: KMS Lockouts & Disaster Recovery Traps

In zero-trust architectures, sensitive configurations and forensic audit vaults are protected by cryptographic encryption. This chapter details the catastrophic risk of **Key Management System (KMS) Lockouts** caused by sandbox path divergence, and how **BIP-39 Mnemonic Seed Phrase Disaster Recovery** ensures permanent data recoverability.

---

## What Happened

While securing forensic session vaults and sensitive credentials with AES-256-GCM encryption, the platform encountered critical data-loss events:
- **Sandbox Pathing Lockouts**: The KMS looked for the master key using a relative path (`./security/master.key`). When an autonomous agent switched its working directory to a sub-workspace (`/projects/game_demo/`), the KMS resolved the path to `/projects/game_demo/security/master.key`, failed to find it, generated a fresh key, and permanently orphaned all historical vault data!
- **Container Ephemerality Data Loss**: When running inside containerized Docker environments, non-persistent volumes wiped the physical key file on restart, turning all encrypted developer sessions into unrecoverable garbage.
- **The Lack of an Emergency Override**: Without an offline recovery mechanism, losing a single 32-byte key file resulted in total administrative lockout.

---

## Why It Happened

The root causes trace back to naive filesystem assumptions and missing cryptographic escrow:
- **Relative Path Vulnerability**: Relative file paths (`./...`) are dependent on the current process working directory (`os.getcwd()`). Because agent commands dynamically shift working directories, relative paths must never be used for security-critical assets.
- **Single Point of Failure (SPOF)**: Storing a master encryption key purely as raw bytes in a single file on disk creates an existential risk. If disk sectors corrupt or cleanup scripts purge temporary directories, the cryptographic trust root vanishes.
- **Human-Unfriendly Entropy**: A raw 256-bit AES key is an unmemorable sequence of random hex characters. Humans cannot write it down on paper without introducing transcription errors.

```
Relative Path Trap:
Agent cwd: /projects/demo/ ---> KMS checks ./master.key ---> Not Found! ---> Generates New Key ---> VAULT LOCKED!

Canonical Path + Seed Phrase Escrow:
KMS uses canonical /secure/vault/master.key + 12-Word Mnemonic Phrase ---> 100% Deterministic Recovery!
```

---

## The "Why Order Matters" Principle

In cryptographic bootstrapping and key derivation, the sequence of execution determines key validity:
1. **Resolve Canonical Master Path Before Access**: The KMS must resolve the absolute, canonical system path for the key file before checking process working directories.
2. **Derive Key Deterministically**: When recovering via a mnemonic seed phrase, the salt and PBKDF2 iteration count must match the exact initialization parameters. Deriving with wrong iteration counts produces an incorrect key with zero syntax warnings.
3. **Verify Integrity Tag Before Decryption**: Always verify the AES-GCM 16-byte authentication tag *before* writing decrypted plaintext to memory or disk. Decrypting corrupt ciphertext introduces remote code execution risks.

---

## Beginner Coder Q&A

### What is a BIP-39 Mnemonic Seed Phrase?
BIP-39 is a cryptographic standard that converts 128 or 256 bits of random entropy into an easy-to-read sequence of 12 or 24 English words (like `apple river ocean copper...`). It allows humans to record cryptographic keys securely on paper.

### Why is AES-GCM preferred over standard AES-CBC?
AES-CBC only encrypts data; it does not prove that the data wasn't tampered with. AES-GCM is an Authenticated Encryption mode that includes a cryptographic tag. If even one byte of ciphertext is modified, decryption immediately aborts with an authentication error.

### How does Siraugga recover if the master key file is deleted?
The developer enters the 12-word seed phrase into the offline recovery utility. The script executes PBKDF2-HMAC-SHA512 over the mnemonic, deterministically reconstructs the exact 256-bit AES key, and restores full vault access.

---

## Next Steps & Related Chapters
- To inspect the primary source implementation of KMS key loading and seed phrase derivation, read [`02_SOURCE_EVIDENCE/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE.md`](/docs/devlog/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE).
- To view the diagnostic test logs verifying deterministic key recovery, visit [`03_DIAGNOSTIC_TESTS/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS.md`](/docs/devlog/03_02_RBAC_SANDBOX_AND_HOT_PATCH_TEST_LOGS).
- To build the complete mnemonic disaster recovery script from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_16_KMS_MNEMONIC_SEED_PHRASE_RECOVERY_FROM_SCRATCH.md`](/docs/devlog/05_16_KMS_MNEMONIC_SEED_PHRASE_RECOVERY_FROM_SCRATCH).
