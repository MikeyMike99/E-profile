[//]: # (DOC_ID: SIRA-DOC-04_25 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Offline & Online Threat Modeling Architecture

## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_25-SEC-1)
Security in modern agentic systems cannot rely on theoretical assumptions or passive defense. Software must be continuously tested against simulated adversarial attacks.

The Threat Modeling Architecture splits system defense into two distinct, actively simulated fronts:
1. **The Offline Threat Front**: Defending stored data, encrypted archives, and database snapshots against stolen file attacks and offline dictionary cracking.
2. **The Online Threat Front**: Defending live HTTP routes, WebSockets, and authentication endpoints against automated brute-force attacks and credential stuffing.

```
+-------------------------------------------------------------+
|               Continuous Threat Modeling Engine             |
+-------------------------------------------------------------+
          |                                        |
          | Offline Attack Simulation              | Online Attack Simulation
          v                                        v
+-----------------------+              +----------------------+
| Offline Crack Lab     |              | Online Brute Lab     |
| - Dictionary sweeps   |              | - Rapid API probes   |
| - Known-plaintext test|              | - Rate-limit testing |
| - AES-256 vs ZipCrypto|              | - IP lockout triggers|
+-----------------------+              +----------------------+
          |                                        |
          \                                        /
           \                                      /
            v                                    v
+-------------------------------------------------------------+
|                 SIEM Telemetry & Policy Hardening           |
|         Enforces Zero Legacy Ciphers & Bounded Endpoints    |
+-------------------------------------------------------------+
```

---

## 2. Offline Defense: Eliminating Weak Ciphers
[//]: # (SECTION_ID: SIRA-DOC-04_25-SEC-2)
An attacker who gains access to an encrypted zip archive has unlimited offline compute time. To protect developer assets:
- **Zero ZipCrypto Clearance**: Legacy ZipCrypto is permanently blacklisted across all Siraugga backup routines.
- **Enforced AES-256 with PBKDF2**: Backups must be generated using `pyzipper` with WinZip-compatible AES-256 encryption. The high work factor throttles GPU password-cracking rigs from millions of hashes per second to a few hundred.

---

## 3. Online Defense: Throttling & Jailing
[//]: # (SECTION_ID: SIRA-DOC-04_25-SEC-3)
Against online endpoint attacks:
- **Strict Attempt Quotas**: Authentication endpoints allow a maximum of 5 failed attempts per IP address per minute.
- **Instant IP Jailing**: Exceeding the threshold triggers an automatic 300-second firewall ban and pushes a `CRITICAL` alert to the Master Alert Queue.
- **Timing Attack Mitigation**: Credential comparisons use constant-time string comparisons (`secrets.compare_digest`) to prevent side-channel timing analysis.

---

## 4. Why Order Matters in Threat Defense
[//]: # (SECTION_ID: SIRA-DOC-04_25-SEC-4)
1. **Hard-Code Cipher Validation Before Archiving**: Checking cipher algorithms before writing backup files ensures unencrypted or weakly encrypted files never touch the hard drive.
2. **Evaluate Rate Limiting Before Hashing**: Checking IP jail status before running expensive PBKDF2 or bcrypt verification protects the server from Denial-of-Service CPU exhaustion.
3. **Use Constant-Time Comparisons**: Using `secrets.compare_digest()` before returning auth status ensures string evaluation time reveals zero clues about character matching.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_25-SEC-5)
**Q: What is a dictionary attack?**  
A: An automated attack that tests thousands of common words and known leaked passwords against an encrypted file or login form.

**Q: What is a timing attack?**  
A: An attack where an adversary measures how many nanoseconds the server takes to respond. Standard string comparison (`==`) stops at the first mismatched character, leaking how many characters were correct.

**Q: Why run offline attack simulations inside the workspace?**  
A: By running `crack_master.py` in test folders, developers can directly observe how vulnerable legacy encryption is and verify that their production backups are safe.
