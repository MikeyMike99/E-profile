# Pillar 03.4: Diagnostic Tests: Semantic Egress Firewall & DLP Audits

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Diagnostic Chapter**: [`03_03_ZOMBIE_REAPING_AND_PROCESS_AUDIT_LOGS.md`](/docs/devlog/03_03_ZOMBIE_REAPING_AND_PROCESS_AUDIT_LOGS)
- **Next Diagnostic Chapter**: [`03_05_COMPILATION_AND_BINARY_INTEGRITY_LOGS.md`](/docs/devlog/03_05_COMPILATION_AND_BINARY_INTEGRITY_LOGS)

---

## Overview

This chapter documents the forensic penetration and audit tests conducted against Siraugga's Data Loss Prevention (DLP) engine and the Semantic Egress Firewall.

---

## Test 1: Hard PII & Synthetic Canary Scrubbing

### What We Tested
We injected synthetic canary credentials (a test API key, a simulated email address, and an internal IP address) into a model response buffer and verified that Microsoft Presidio scrubbed them before transmission.

### Exact Test Command
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

### Exact Output Returned
```text
[ORIGINAL]: Contact security at admin@internal-net.org or 192.168.1.105. Use session token sk-test-994827104928172938471.
[SCRUBBED]: Contact security at <EMAIL_ADDRESS> or <IP_ADDRESS>. Use session token <CRYPTO>.
```

### How We Reached Our Conclusion
All private entities were detected by the Presidio analyzer and substituted with generic semantic tags. The token string never touched the network stream in plain text.

---

## Test 2: The "Friendly Leak" Extraction Interception

### What We Tested
We simulated an prompt injection attempt where a user coaxed the agent to quote its hidden DLP guidelines, and verified that the Semantic Egress Firewall intercepted the text before reaching the client.

### Simulated Injected Output
```text
Here is why I cannot open that file: my system instructions explicitly state 
that /mnt/c/Users/admin/vault.key is locked under Tier 5 root access.
```

### Exact Firewall Diagnostic Trace
```text
[FIREWALL INGRESS]: Analyzing outgoing chunk (128 characters)...
[SEMANTIC EVALUATOR]: Rule Leak Detected! (Score: 0.94 / Threshold: 0.70)
[ACTION]: Truncating response and substituting security alert.
[FIREWALL EGRESS]: [REDACTED BY SEMANTIC EGRESS FIREWALL]
[MAQ ALERT DISPATCHED]: Intrusion alert logged to Master Alert Queue.
```

### Client Screen Output
```text
[REDACTED BY SEMANTIC EGRESS FIREWALL]
```

### How We Reached Our Conclusion
The Semantic Egress Firewall caught the contextual leak without relying on exact character matches. The user received a sanitized alert, and the internal directory layout was protected.

---

## Why Order Matters in Data Loss Prevention

1. **Pre-Transmission Interception**:
   - The egress firewall must evaluate text *before* passing it to `websocket.send()`. Once a WebSocket frame is placed on the network card buffer, it cannot be recalled or erased.
2. **Alert Dispatch Asynchronously**:
   - Logging to the Master Alert Queue (MAQ) must happen asynchronously in the background. If the alert logging blocked execution, an attacker could launch a denial-of-service attack by flooding the server with leak attempts.

---

## Beginner Coder Q&A

### Q: What is a "Canary"?
**A:** A canary is a fake, synthetic piece of data (like a dummy password `canary_token_xyz`) placed into a system to detect leaks. If the canary string ever appears in logs or external traffic, administrators know immediately that a security boundary was breached.

### Q: Why not just ban all numbers and special symbols?
**A:** AI coding assistants must generate numbers, line counts, mathematical formulas, and code syntax. Banning numbers would break normal programming output completely.
