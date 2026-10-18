[//]: # (DOC_ID: SIRA-DEV-04_14 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 04_14: KMS Seed Phrase Disaster Recovery Architecture

A cryptographic architecture guide to Siraugga's **Key Management System (KMS) Disaster Recovery Engine**—providing deterministic 256-bit AES master key reconstruction from offline BIP-39 mnemonic seed phrases.

---

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-1)
## Architectural Overview & The SPOF Dilemma
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-1)

In zero-trust environments, session recordings, credentials, and forensic logs are encrypted at rest with AES-256-GCM. Storing the master key purely as a raw 32-byte file on disk creates a catastrophic **Single Point of Failure (SPOF)**:
- Container rebuilds or disk corruption permanently erase the key file.
- Unsalvageable master keys turn all historical forensic vaults into permanently locked ciphertext.

Siraugga solves this by pairing disk-based caching with an offline **BIP-39 Mnemonic Seed Phrase Escrow**:

```
┌─────────────────────────────────────────────────────────────┐
│                 OFFLINE HUMAN ESCROW LAYER                  │
│       12-Word Mnemonic Phrase (Recorded on Physical Paper)  │
│   e.g.: "apple river ocean copper tower shield dragon..."   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Emergency Disaster Recovery
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               CRYPTOGRAPHIC DERIVATION ENGINE               │
│                   (PBKDF2-HMAC-SHA512)                      │
│                                                             │
│   • Salt: "mnemonic" + optional passphrase                  │
│   • Iterations: 2048 rounds of HMAC-SHA512                  │
│   • Output: 512-bit binary seed                             │
└──────────────────────────────┬──────────────────────────────┘
                               │ First 256 bits (32 bytes)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 CANONICAL AES-256 MASTER KEY                │
│             (In-Memory Key Injection - Zero Disk)           │
│                                                             │
│   • Unlocks Forensic Audit Vaults                           │
│   • Decrypts Sensitive System Configurations                │
│   • 100% Deterministic Bit-for-Bit Reconstruction           │
└─────────────────────────────────────────────────────────────┘
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-2)
## Cryptographic Key Derivation Details
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-2)

1. **Entropy to Words (BIP-39 Standard)**:
   - 128 bits of cryptographic entropy are generated using `secrets.token_bytes(16)`.
   - A 4-bit checksum is calculated using SHA-256 and appended.
   - The resulting 132 bits are split into twelve 11-bit chunks, each indexing a standardized wordlist of 2048 words.
2. **Seed Derivation (PBKDF2-HMAC-SHA512)**:
   - The normalized word string is passed to `hashlib.pbkdf2_hmac("sha512", words.encode("utf-8"), salt, 2048)`.
   - The first 32 bytes of the derived seed become the canonical AES-256 master key.

---

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-3)

In cryptographic derivation, sequence controls reproducibility:
1. **Unicode Normalization (NFKD) Before Hashing**: Mnemonic words must be normalized to Unicode Compatibility Decomposition (NFKD) before PBKDF2 hashing. Failing to normalize produces completely different keys across operating systems!
2. **Canonical Path Resolution Before Disk Checks**: Always resolve the master key path against an absolute system directory (never relative `./`) to prevent sandboxed subagents from creating divergent keys.
3. **Verify Header Authentication Tag Before Vault Decryption**: Decrypting corrupted ciphertext can cause memory faults. Always verify the 16-byte AES-GCM tag first.

---

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-4)
## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-4)

To derive an AES-256 master key deterministically from a 12-word seed phrase in under 15 lines:

```python
import hashlib, unicodedata

def derive_master_key_from_mnemonic(mnemonic_phrase: str, passphrase: str = "") -> bytes:
    # Step 1: Normalize unicode characters (NFKD)
    clean_mnemonic = unicodedata.normalize("NFKD", mnemonic_phrase.strip())
    clean_passphrase = unicodedata.normalize("NFKD", passphrase)
    
    # Step 2: Construct standard BIP-39 salt
    salt = ("mnemonic" + clean_passphrase).encode("utf-8")
    
    # Step 3: Execute PBKDF2 key stretching
    seed = hashlib.pbkdf2_hmac("sha512", clean_mnemonic.encode("utf-8"), salt, iterations=2048)
    
    # Step 4: Return first 32 bytes as AES-256 master key
    return seed[:32]
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-6)

### What happens if I lose the master key file on disk?
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-6)
You run the recovery script, enter your 12-word seed phrase, and the script regenerates the exact same 32-byte AES key in memory, unlocking your encrypted files immediately.

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-7)
### Why is a seed phrase better than just writing down the hex key?
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-7)
A 256-bit key in hex looks like `4a7b9c1d2e...`—64 confusing characters where a single typo permanently destroys your data. A seed phrase uses simple English words that humans can easily check for spelling errors.

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-8)
### Can an attacker guess a 12-word seed phrase?
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-8)
No. There are $2048^{12} \approx 5.4 \times 10^{39}$ possible 12-word combinations. Even using all the supercomputers on Earth, it would take trillions of years to guess.

---

[//]: # (SECTION_ID: SIRA-DEV-04_14-SEC-9)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_14-SEC-9)
- To understand why relative paths broke KMS keys in sandboxes, read [`01_PROBLEMS_ENCOUNTERED/01_20_KMS_LOCKOUTS_AND_DISASTER_RECOVERY_TRAPS.md`](/docs/devlog/01_20_KMS_LOCKOUTS_AND_DISASTER_RECOVERY_TRAPS).
- To inspect the primary source implementation of KMS key loading, view [`02_SOURCE_EVIDENCE/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE.md`](/docs/devlog/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE).
- To build the complete offline seed phrase generator and recovery tool from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_16_KMS_MNEMONIC_SEED_PHRASE_RECOVERY_FROM_SCRATCH.md`](/docs/devlog/05_16_KMS_MNEMONIC_SEED_PHRASE_RECOVERY_FROM_SCRATCH).
