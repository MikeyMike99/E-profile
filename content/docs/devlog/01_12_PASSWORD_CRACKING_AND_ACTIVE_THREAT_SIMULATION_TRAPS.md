[//]: # (DOC_ID: SIRA-DOC-01_12 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 01.12: Problems Encountered: Active Threat Simulation & Password Auditing

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_11_AI_INTERNAL_MONOLOGUE_AND_ROBOTIC_BOT_SPEAK.md`](/docs/devlog/01_11_AI_INTERNAL_MONOLOGUE_AND_ROBOTIC_BOT_SPEAK)
- **Next: Source Evidence**: [`../02_SOURCE_EVIDENCE/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE.md`](/docs/devlog/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-1)

In cybersecurity, defense cannot be assumed; it must be proven. As documented in DEVLOG Chapters 61 and 62, the Siraugga engineering team instituted an **Active Threat Simulation Strategy** to stress-test platform authentication and encrypted asset archives.

This chapter details the vulnerabilities uncovered during offline dictionary attacks (`crack.py`) and how contextual simulation bypassed false AI safety refusals.

---

## Issue 1: Unsalted Hashes & Dictionary Vulnerabilities
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-2)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-3)
During an internal audit of administrative credential storage, the team ran a lightweight dictionary attack script (`crack.py`):

```python
import hashlib
target = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"
words = ["admin", "dev", "mod", "superadmin", "password", "master", "devcore", "siraugga"]
for w in words:
    if hashlib.sha256(w.encode()).hexdigest() == target:
        print("FOUND:", w)
```

In less than 2 milliseconds, the script cracked the target hash and revealed the password.

### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-4)
1. **Unsalted Hashes**: Fast mathematical hash functions like raw SHA-256 produce the exact same hex digest for identical passwords. An attacker with precomputed rainbow tables can crack passwords instantaneously.
2. **Missing Key Derivation**: Fast hash functions are designed for high-throughput data integrity, not password hashing. Attackers can test billions of SHA-256 hashes per second using standard consumer graphics cards.

---

## Issue 2: AI Safety Guardrail Refusals During Security Auditing
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-5)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-6)
When the team prompted the AI agent to write auditing scripts to test online rate-limiting defenses against brute-force attacks, the AI abruptly refused:
> *"I cannot assist with writing password cracking or brute-force tools, as this violates safety guidelines regarding malicious hacking."*

The development workflow ground to an immediate halt. The AI could not distinguish between a malicious cyberattack and an authorized developer hardening their own local server.

### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-7)
Commercial LLM safety filters are triggered by naive keyword heuristics (like "brute force", "crack password", or "exploit"). Without proper architectural framing, the safety filters default to denial.

---

## The Architectural Solution
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-8)

To harden the platform and resolve testing roadblocks, Siraugga executed two strategic upgrades:

### 1. Cryptographic Salting & Slow Key Derivation
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-1)
Migrated all administrative authentication from plain SHA-256 to **Bcrypt / Argon2id**:
- Incorporates a unique, cryptographically random salt per user.
- Enforces an artificial computation cost (work factor) that slows down offline attacks from billions of hashes per second to less than 10 per second.

### 2. Contextual Threat Simulation Framing
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-2)
Security audit tasks are executed using the **Active Threat Simulation Pattern**:
- Audit scripts are framed strictly within an authorized penetration test sandbox (`Offline_Crack_Lab`).
- Tasks explicitly declare system ownership and defensive objectives, allowing the AI to analyze hash collisions and rate-limit thresholds safely.

---

## Why Order Matters in Password Security
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-9)

1. **Verify Rate-Limit Counter Before Hash Computation**:
   - The web server must check IP rate-limiting and account lockout thresholds *before* computing expensive Bcrypt hashes. If the server calculates the hash first, an attacker can crash the server CPU by flooding it with dummy login requests.
2. **Salt Generation Before Hash Execution**:
   - A unique salt must be generated via a secure random generator (`os.urandom`) *before* hashing. Reusing a static salt across multiple accounts enables rainbow table attacks.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-10)

### Q: What is a Salt in cryptography?
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-11)
**A:** A salt is random data added to a password before hashing. If two users choose the password `"secret"`, salting ensures their resulting hash strings look completely different, preventing attackers from cracking multiple accounts simultaneously.

### Q: What is a Rainbow Table?
[//]: # (SECTION_ID: SIRA-DOC-01_12-SEC-12)
**A:** A rainbow table is a massive precomputed database of passwords and their corresponding hash values. Instead of guessing passwords, an attacker simply searches the database to find the plaintext match. Salting completely destroys the effectiveness of rainbow tables.
