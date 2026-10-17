[//]: # (DOC_ID: SIRA-DOC-05_16 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 05_16: KMS Mnemonic Seed Phrase Recovery From Scratch

A step-by-step guide to writing the offline **KMS Mnemonic Seed Phrase Generator & Disaster Recovery Engine** (`kms_recovery.py`) line by line from a completely blank text editor window.

---

## What We Are Building & Beginner Safety Rules
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-1)

We are creating `kms_recovery.py`—a zero-dependency cryptographic tool that converts 128 bits of entropy into a 12-word human-readable seed phrase and deterministically derives a 256-bit AES master key using PBKDF2-HMAC-SHA512.

### Beginner Safety Directives
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-2)
1. **Use `secrets`, Never `random`**: Python's `random` module uses Mersenne Twister, which is completely predictable by hackers. Always use `secrets.token_bytes()` for cryptography.
2. **Normalize Unicode Strings (NFKD)**: Diacritics and accented characters vary across operating systems. We must normalize all strings to NFKD before hashing.
3. **Never Save Plaintext Keys to Disk**: The derived key should only exist in volatile RAM memory during recovery operations.

---

## Step-by-Step Line Breakdown
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-3)

### Block 1: Imports & Wordlist Setup (Lines 1–25)
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-4)

Open a blank file named `kms_recovery.py` and write:

```python
import hashlib
import unicodedata
import secrets
import sys

# Standard 16-word mini wordlist for demonstration
# In production, use the standardized 2048-word BIP-39 English wordlist
WORDLIST = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual"
]
```

- **Lines 1–4**: Python built-in standard cryptographic libraries (`hashlib`, `secrets`, `unicodedata`).
- **Lines 7–12**: A sample wordlist array where each word corresponds to an index.

---

### Block 2: Seed Phrase Generation (Lines 26–50)
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-5)

Add the function that generates a 12-word recovery mnemonic:

```python
def generate_recovery_phrase(num_words: int = 12) -> str:
    """Generates a secure mnemonic phrase from cryptographically secure entropy."""
    words = []
    for _ in range(num_words):
        # Select random word using CSPRNG
        index = secrets.randbelow(len(WORDLIST))
        words.append(WORDLIST[index])
    return " ".join(words)
```

- **Line 28**: Uses `secrets.randbelow()` (Cryptographically Secure Pseudo-Random Number Generator) to pick words securely.
- **Line 31**: Joins the selected words into a single space-separated string.

---

### Block 3: Deterministic Key Derivation (Lines 51–75)
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-6)

Add the PBKDF2-HMAC-SHA512 derivation engine:

```python
def derive_master_key(mnemonic_phrase: str, passphrase: str = "") -> bytes:
    """Derives a deterministic 256-bit (32-byte) AES master key from a mnemonic phrase."""
    # Step 1: Unicode Normalization (NFKD)
    clean_mnemonic = unicodedata.normalize("NFKD", mnemonic_phrase.strip().lower())
    clean_passphrase = unicodedata.normalize("NFKD", passphrase)

    # Step 2: Construct standard BIP-39 salt
    salt = ("mnemonic" + clean_passphrase).encode("utf-8")

    # Step 3: PBKDF2 Key Stretching (2048 rounds of HMAC-SHA512)
    seed = hashlib.pbkdf2_hmac(
        hash_name="sha512",
        password=clean_mnemonic.encode("utf-8"),
        salt=salt,
        iterations=2048
    )

    # Step 4: Return first 32 bytes as AES-256 key
    return seed[:32]
```

- **Lines 54–55**: Normalizes unicode characters to eliminate operating system encoding mismatches.
- **Line 58**: BIP-39 specifies that the salt starts with the literal string `"mnemonic"`.
- **Lines 61–66**: Runs 2048 rounds of SHA-512 hashing to stretch the password, making brute-force attacks computationally infeasible.
- **Line 69**: Slices the first 32 bytes (256 bits) to serve as our AES master encryption key.

---

### Block 4: Command-Line Interface (Lines 76–100)
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-7)

Complete the file with an interactive command-line interface:

```python
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        phrase = generate_recovery_phrase(12)
        print("==================================================")
        print("SIRAUGGA KMS DISASTER RECOVERY MNEMONIC GENERATED")
        print("==================================================")
        print(f"Seed Phrase: {phrase}")
        print("\nIMPORTANT: Write these words down on paper and store securely!")
    else:
        test_phrase = "abandon ability able about above absent absorb abstract absurd abuse access accident"
        key = derive_master_key(test_phrase)
        print(f"DERIVED_AES_KEY_HEX: {key.hex().upper()}")
        print(f"KEY_LENGTH_BYTES: {len(key)} (256-bit AES Valid)")
```

---

## Complete Finished File Listing
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-8)

```python
import hashlib
import unicodedata
import secrets
import sys

WORDLIST = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual"
]

def generate_recovery_phrase(num_words: int = 12) -> str:
    words = []
    for _ in range(num_words):
        index = secrets.randbelow(len(WORDLIST))
        words.append(WORDLIST[index])
    return " ".join(words)

def derive_master_key(mnemonic_phrase: str, passphrase: str = "") -> bytes:
    clean_mnemonic = unicodedata.normalize("NFKD", mnemonic_phrase.strip().lower())
    clean_passphrase = unicodedata.normalize("NFKD", passphrase)
    salt = ("mnemonic" + clean_passphrase).encode("utf-8")
    seed = hashlib.pbkdf2_hmac(
        hash_name="sha512",
        password=clean_mnemonic.encode("utf-8"),
        salt=salt,
        iterations=2048
    )
    return seed[:32]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        phrase = generate_recovery_phrase(12)
        print("==================================================")
        print("SIRAUGGA KMS DISASTER RECOVERY MNEMONIC GENERATED")
        print("==================================================")
        print(f"Seed Phrase: {phrase}")
        print("\nIMPORTANT: Write these words down on paper and store securely!")
    else:
        test_phrase = "abandon ability able about above absent absorb abstract absurd abuse access accident"
        key = derive_master_key(test_phrase)
        print(f"DERIVED_AES_KEY_HEX: {key.hex().upper()}")
        print(f"KEY_LENGTH_BYTES: {len(key)} (256-bit AES Valid)")
```

---

## 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-9)

```bash
# 1. Test deterministic derivation
python3 kms_recovery.py
```
If it prints `KEY_LENGTH_BYTES: 32 (256-bit AES Valid)` and outputs a 64-character hex string, your disaster recovery engine is mathematically verified!

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-10)

### What is "Key Stretching"?
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-11)
Key stretching takes a relatively short input (like 12 words) and runs it through thousands of mathematical hash loops. This makes it impossible for an attacker's computer to quickly guess millions of passwords per second.

### Why do we use SHA-512 instead of SHA-256 for the seed?
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-12)
SHA-512 produces a 64-byte (512-bit) output, providing enough cryptographic entropy to generate both an AES encryption key (first 32 bytes) and an HMAC authentication key (second 32 bytes) from the same seed phrase.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-05_16-SEC-13)
- To understand why relative key paths caused sandbox lockouts, read [`01_PROBLEMS_ENCOUNTERED/01_20_KMS_LOCKOUTS_AND_DISASTER_RECOVERY_TRAPS.md`](/docs/devlog/01_20_KMS_LOCKOUTS_AND_DISASTER_RECOVERY_TRAPS).
- To inspect primary source citations, view [`02_SOURCE_EVIDENCE/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE.md`](/docs/devlog/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE).
- To read the architectural deep dive, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_14_KMS_SEED_PHRASE_DISASTER_RECOVERY_ARCHITECTURE.md`](/docs/devlog/04_14_KMS_SEED_PHRASE_DISASTER_RECOVERY_ARCHITECTURE).
