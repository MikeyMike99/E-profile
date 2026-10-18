[//]: # (DOC_ID: SIRA-DEV-03_04 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 03.4: Diagnostic Tests: Semantic Egress Firewall & DLP Audits

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Diagnostic Chapter**: [`03_03_ZOMBIE_REAPING_AND_PROCESS_AUDIT_LOGS.md`](/docs/devlog/03_03_ZOMBIE_REAPING_AND_PROCESS_AUDIT_LOGS)
- **Next Diagnostic Chapter**: [`03_05_COMPILATION_AND_BINARY_INTEGRITY_LOGS.md`](/docs/devlog/03_05_COMPILATION_AND_BINARY_INTEGRITY_LOGS)

---

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-1)

This chapter documents the forensic penetration and audit tests conducted against Siraugga's Data Loss Prevention (DLP) engine and the Semantic Egress Firewall.

---

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-2)
## Test 1: Hard PII & Synthetic Canary Scrubbing
[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-3)

### What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-3)
We injected synthetic canary credentials (a test API key, a simulated email address, and an internal IP address) into a model response buffer and verified that Microsoft Presidio scrubbed them before transmission.

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-4)
### Exact Test Command
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-4)
```bash
python3 -c "
from security.local_security import LocalSecurity

sec = LocalSecurity()
canary_payload = (
    'Contact security at admin@internal-net.org or 192.168.1.105. '
    'Use session token sk-test-994827104928172938471.'
)
print('[ORIGINAL]:', canary_payload)
scrubbed = sec.scrub_text(canary_payload)
print('[SCRUBBED]:', scrubbed)
"
```

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-5)
### Exact Output Returned
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-5)
```text
[ORIGINAL]: Contact security at admin@internal-net.org or 192.168.1.105. Use session token sk-test-994827104928172938471.
[SCRUBBED]: Contact security at <EMAIL_ADDRESS> or <IP_ADDRESS>. Use session token <CRYPTO>.
```

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-6)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-6)
All private entities were detected by the Presidio analyzer and substituted with generic semantic tags. The token string never touched the network stream in plain text.

---

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-7)
## Test 2: The "Friendly Leak" Extraction Interception
[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-8)

### What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-8)
We simulated an prompt injection attempt where a user coaxed the agent to quote its hidden DLP guidelines, and verified that the Semantic Egress Firewall intercepted the text before reaching the client.

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-9)
### Simulated Injected Output
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-9)
```text
Here is why I cannot open that file: my system instructions explicitly state 
that /mnt/c/Users/admin/vault.key is locked under Tier 5 root access.
```

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-10)
### Exact Firewall Diagnostic Trace
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-10)
```text
[FIREWALL INGRESS]: Analyzing outgoing chunk (128 characters)...
[SEMANTIC EVALUATOR]: Rule Leak Detected! (Score: 0.94 / Threshold: 0.70)
[ACTION]: Truncating response and substituting security alert.
[FIREWALL EGRESS]: [REDACTED BY SEMANTIC EGRESS FIREWALL]
[MAQ ALERT DISPATCHED]: Intrusion alert logged to Master Alert Queue.
```

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-11)
### Client Screen Output
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-11)
```text
[REDACTED BY SEMANTIC EGRESS FIREWALL]
```

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-12)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-12)
The Semantic Egress Firewall caught the contextual leak without relying on exact character matches. The user received a sanitized alert, and the internal directory layout was protected.

---

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-13)
## Why Order Matters in Data Loss Prevention
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-13)

1. **Pre-Transmission Interception**:
   - The egress firewall must evaluate text *before* passing it to `websocket.send()`. Once a WebSocket frame is placed on the network card buffer, it cannot be recalled or erased.
2. **Alert Dispatch Asynchronously**:
   - Logging to the Master Alert Queue (MAQ) must happen asynchronously in the background. If the alert logging blocked execution, an attacker could launch a denial-of-service attack by flooding the server with leak attempts.

---

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-14)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-15)

### Q: What is a "Canary"?
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-15)
**A:** A canary is a fake, synthetic piece of data (like a dummy password `canary_token_xyz`) placed into a system to detect leaks. If the canary string ever appears in logs or external traffic, administrators know immediately that a security boundary was breached.

[//]: # (SECTION_ID: SIRA-DEV-03_04-SEC-16)
### Q: Why not just ban all numbers and special symbols?
[//]: # (SECTION_ID: SIRA-DOC-03_04-SEC-16)
**A:** AI coding assistants must generate numbers, line counts, mathematical formulas, and code syntax. Banning numbers would break normal programming output completely.
