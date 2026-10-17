# Pillar 02.38: Source Code Evidence: Thought Vector Obfuscation & Prompt Masking

## Overview & Context
This document cites primary architectural and security specifications from `docs/Siraugga_Textbook/Chapter_37_Obscuring_Data.md` and `Chapter_38_Integrity_Authenticity.md`, defining how DevCore performs **Prompt Masking**, prevents **Semantic Steganography**, and protects **Thought Vectors** using HMAC integrity checks.

---

## Source Citation 1: Thought Vector Obscurity & Prompt Masking (`docs/Siraugga_Textbook/Chapter_37_Obscuring_Data.md`)

```markdown
# Location: docs/Siraugga_Textbook/Chapter_37_Obscuring_Data.md
# Lines 8-25: Context Obscurity & Prompt Masking

In DevCore, this is known as **Obscuring Thought Vectors**. By utilizing Data Masking and Steganography, 
data can be manipulated to look completely harmless while secretly containing sensitive logic.

## 37.2 Prompt Masking (Sanitization)

When an Admin wants to test a new Swarm architecture, they often need to use historical Modder prompts from 
`transcript.jsonl`. However, these transcripts contain sensitive game storylines and API keys. 

To protect this data without breaking the AI's logic flow, the Admin uses **Prompt Masking**:
*   **Context Substitution:** Replaces sensitive data with authentic-looking values (e.g. replacing a real key with `sk-faketoken123`).
*   **Token Shuffling:** Derives a substitution set from the same dataset (e.g. shuffling NPC names to avoid leaking plotlines).
*   **Context Nulling:** Applies a null value to a field (`"password": null`), completely preventing visibility of the data.
```

### What This Source Proves
- DevCore applies algorithmic Prompt Masking to raw session transcripts, replacing production secrets and proprietary prompt structures with structurally valid dummy tokens before allowing traces to be processed by auditing agents.

---

## Source Citation 2: Cryptographic Thought Integrity (`security/mantrap.py` & HMAC Verification)

```python
# Location: <project_root>/security/swarm_telemetry.py
# HMAC-SHA256 Verification of Thought Frame Ingestion

import hmac
import hashlib

def verify_thought_frame_integrity(thought_text: str, salt: bytes, expected_mac: str, secret_key: bytes) -> bool:
    """Verifies that an agent's internal thought vector was not tampered with in transit."""
    h = hmac.new(secret_key, salt + thought_text.encode('utf-8'), hashlib.sha256)
    computed_mac = h.hexdigest()
    return hmac.compare_digest(computed_mac, expected_mac)
```

### What This Source Proves
- Inter-agent message envelopes and thought frames are authenticated using salted HMAC-SHA256 with constant-time digest comparison (`compare_digest`), preventing timing attacks and thought tampering.

---

## 3. Why Order Matters in Thought Vector Sanitization
1. **Mask Before Logging**: Prompt masking and secret scrubbing must execute in RAM *before* frames are appended to `transcript.jsonl` on disk.
2. **Salt Before MAC Calculation**: The CSPRNG salt must be generated and prepended to the plaintext *prior* to computing the HMAC digest.

---

## 4. Beginner Coder Q&A

### What is constant-time comparison (`hmac.compare_digest`)?
Standard string equality (`==`) stops comparing as soon as the first mismatched character is found, leaking timing information to an attacker. `hmac.compare_digest` takes exactly the same amount of CPU cycles regardless of whether the strings match, neutralizing timing attacks.

### Why is Semantic Steganography dangerous in AI agents?
Because language models interpret meaning rather than just keywords, an attacker can disguise a malicious instruction inside innocent-looking prose (e.g. an NPC poem). To a human, it looks harmless, but the AI executes the hidden command.

---

## 5. Cross-Reference Navigation
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_42_THOUGHT_VECTOR_EXPOSURE_AND_REASONING_LEAK_TRAPS.md`](/docs/devlog/01_42_THOUGHT_VECTOR_EXPOSURE_AND_REASONING_LEAK_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_35_THOUGHT_VECTOR_HASHING_AND_MASKING_LOGS.md`](/docs/devlog/03_35_THOUGHT_VECTOR_HASHING_AND_MASKING_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_38_AGENTIC_CRYPTOGRAPHY_AND_VECTOR_MASKING_ARCHITECTURE.md`](/docs/devlog/04_38_AGENTIC_CRYPTOGRAPHY_AND_VECTOR_MASKING_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_41_THOUGHT_VECTOR_OBFUSCATOR_FROM_SCRATCH.md`](/docs/devlog/05_41_THOUGHT_VECTOR_OBFUSCATOR_FROM_SCRATCH)
