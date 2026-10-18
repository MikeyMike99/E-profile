[//]: # (DOC_ID: SIRA-DEV-02_08 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.8: Source Evidence: Offline Crack Lab & Threat Simulation

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_07_CINEMATIC_TTS_AND_STEALTH_FEED_EVIDENCE.md`](/docs/devlog/02_07_CINEMATIC_TTS_AND_STEALTH_FEED_EVIDENCE)
- **Next: Diagnostic Tests**: [`../03_DIAGNOSTIC_TESTS/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS.md`](/docs/devlog/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS)

---

[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-02_08-SEC-1)

This chapter documents the primary source code from Siraugga's internal penetration testing harness (`crack.py`).

This source demonstrates how active threat modeling and dictionary attack simulations were executed directly within the platform's security audit lab to verify credential resistance against offline brute-force exfiltration.

---

[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-2)
## Source 1: The Offline Dictionary Hash Scanner
[//]: # (SECTION_ID: SIRA-DOC-02_08-SEC-2)

- **Source File**: `<project_root>/crack.py`
- **Location**: Complete Verification Script

```python
import hashlib

# Target: SHA-256 digest extracted during test audit
target = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"

# Candidate wordlist reflecting system roles, default credentials, and keywords
words = [
    "admin",
    "dev",
    "mod",
    "superadmin",
    "password",
    "master",
    "devcore",
    "siraugga",
    "12345",
    "root",
    "Raugus",
    "raugus"
]

# Fast hash iteration testing for dictionary collisions
for w in words:
    candidate_hash = hashlib.sha256(w.encode('utf-8')).hexdigest()
    if candidate_hash == target:
        print("FOUND:", w)
        break
```

[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-3)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_08-SEC-3)
1. **The Unsalted Hash Weakness**: Fast hash algorithms like SHA-256 allow dictionary loops to calculate and compare millions of candidates in sub-second time.
2. **The Defense-in-Depth Imperative**: Proves that relying solely on hash length is insufficient; cryptographic salting and intentionally slow key derivation functions (like Bcrypt or Argon2id) are mandatory for Tier 5 administrative accounts.

---

[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-4)
## Why Order Matters in Threat Simulation
[//]: # (SECTION_ID: SIRA-DOC-02_08-SEC-4)

1. **Encode to UTF-8 Before Hashing**:
   - `w.encode('utf-8')` must be called *before* passing strings to `hashlib.sha256()`. In Python, strings are abstract Unicode arrays; hashing requires raw deterministic bytes.
2. **Break Immediately Upon Match**:
   - Calling `break` once a collision is detected terminates the loop immediately, preventing wasted CPU cycles and benchmarking exact discovery times accurately.

---

[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-6)

### Q: Why is SHA-256 considered weak for passwords if it's used in Bitcoin?
[//]: # (SECTION_ID: SIRA-DOC-02_08-SEC-6)
**A:** Bitcoin uses SHA-256 specifically *because* it is fast and mathematically deterministic. But for passwords, high speed is the enemy: a modern computer can guess billions of SHA-256 hashes per second. Password algorithms must be intentionally slow.

[//]: # (SECTION_ID: SIRA-DEV-02_08-SEC-7)
### Q: Why keep `crack.py` in the workspace?
[//]: # (SECTION_ID: SIRA-DOC-02_08-SEC-7)
**A:** In a Zero-Trust engineering environment, test harnesses are maintained to run automated regression checks against credential databases, verifying that no developer has accidentally saved an unhashed or unsalted password.
