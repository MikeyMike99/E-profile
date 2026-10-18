[//]: # (DOC_ID: SIRA-ARCH-05_09 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.9: From-Scratch Creation Guide: Offline Password Audit Lab

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_08_CINEMATIC_TTS_PROXY_FROM_SCRATCH.md`](/docs/devlog/05_08_CINEMATIC_TTS_PROXY_FROM_SCRATCH)
- **Next From-Scratch Guide**: [`05_10_WSL_WINDOWS_IO_BRIDGE_FROM_SCRATCH.md`](/docs/devlog/05_10_WSL_WINDOWS_IO_BRIDGE_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-1)

This guide walks you through building an **Offline Password Audit Test Harness** (`threat_audit_lab.py`) from a blank editor.

You will implement dictionary hash cracking tests to demonstrate the vulnerability of unsalted hashes and learn how to benchmark key derivation performance to protect administrative accounts.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-3)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-3)
```bash
nano threat_audit_lab.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-4)
### Step 2: Implement the Dictionary Hash Scanner (Lines 1–35)
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-4)
```python
import hashlib
import time

def audit_hash(target_hash: str, wordlist: list) -> tuple:
    """Attempts to find a dictionary collision for an unsalted SHA-256 hash."""
    start_time = time.perf_counter()
    attempts = 0

    for word in wordlist:
        attempts += 1
        # Compute SHA-256 digest of candidate word
        digest = hashlib.sha256(word.encode('utf-8')).hexdigest()
        if digest == target_hash:
            elapsed = time.perf_counter() - start_time
            return True, word, attempts, elapsed

    elapsed = time.perf_counter() - start_time
    return False, None, attempts, elapsed
```

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-5)
### Step 3: Implement Salted Hardening Verification (Lines 36–55)
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-5)
```python
def hash_with_salt(password: str, salt: bytes) -> str:
    """Demonstrates how cryptographic salting defeats dictionary collision."""
    salted_bytes = salt + password.encode('utf-8')
    return hashlib.sha256(salted_bytes).hexdigest()

if __name__ == '__main__':
    # Target: SHA-256 hash of "admin"
    TARGET = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
    WORDS = ["guest", "user", "developer", "password", "123456", "admin", "root"]

    found, match, count, sec = audit_hash(TARGET, WORDS)
    if found:
        print(f"[COLLISION DETECTED] Password '{match}' cracked in {sec*1000:.3f} ms after {count} attempts!")
    else:
        print("[AUDIT PASSED] No collision found in wordlist.")
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-6)
## Why Order Matters in Cryptographic Verification
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-6)

1. **UTF-8 Byte Encoding Before Hashing**:
   - Strings must be explicitly encoded to bytes (`.encode('utf-8')`) *before* being passed to `hashlib`. Relying on system default encodings causes hash mismatches across Windows and Linux.
2. **Measure Time Per Hash Incrementally**:
   - Track elapsed time using `time.perf_counter()`, which uses high-resolution CPU hardware clocks rather than `time.time()`, ensuring accurate sub-millisecond benchmarks.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-7)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-7)

Verify that your audit script detects the collision and reports metrics accurately:

```bash
python3 threat_audit_lab.py
```

**Expected Output**:
```text
[COLLISION DETECTED] Password 'admin' cracked in 0.038 ms after 6 attempts!
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-8)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-9)

### Q: Why is `time.perf_counter()` preferred over `time.time()`?
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-9)
**A:** `time.time()` measures wall-clock time and can jump backward if the operating system synchronizes with an NTP internet time server. `time.perf_counter()` is a monotonic clock that only moves forward, making it ideal for performance profiling.

[//]: # (SECTION_ID: SIRA-ARCH-05_09-SEC-10)
### Q: How does adding a salt stop this script?
[//]: # (SECTION_ID: SIRA-DOC-05_09-SEC-10)
**A:** If you add a random salt like `x9F2#kL` to the password before hashing, the attacker must guess the salt *and* the password simultaneously. This increases the possible combinations by billions, making dictionary attacks mathematically impossible.
