[//]: # (DOC_ID: SIRA-DOC-05_41 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 05.41: From-Scratch Creation Guide: Thought Vector Obfuscator & Masking Pipeline

## Overview & Beginner Context
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-1)
This guide teaches you how to write an in-memory Thought Vector Obfuscation and Prompt Masking pipeline in Python from scratch. It scrubs API keys and developer secrets using regular expressions and verifies frame integrity using salted HMAC-SHA256 digests.

---

## 1. Line-by-Line Construction
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-1)

### Block 1: Imports and Scrubbing Regex (Lines 1–20)
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-2)
```python
import re
import os
import hmac
import hashlib

SECRET_PATTERNS = [
    (r"AIzaSy[A-Za-z0-9_-]{33}", "[MASKED_GEMINI_KEY]"),
    (r"sk-[A-Za-z0-9]{48}", "[MASKED_OPENAI_KEY]"),
    (r"ghp_[A-Za-z0-9]{36}", "[MASKED_GITHUB_TOKEN]"),
    (r"\b\d{13}\b", "[MASKED_NATIONAL_ID]")
]
```
- Defines regex tuples pairing sensitive secret patterns with clean structural replacements.

### Block 2: The Masking & Sanitization Function (Lines 21–40)
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-3)
```python
def mask_thought_vector(raw_text: str) -> str:
    """Replaces sensitive keys and PII with structural placeholders."""
    sanitized = raw_text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized
```
- Replaces matches in RAM before frames are broadcast over WebSockets or saved to logs.

### Block 3: The Salted HMAC Signer & Verifier (Lines 41–65)
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-4)
```python
def sign_thought_frame(text: str, secret_key: bytes) -> tuple[bytes, str]:
    """Generates a 16-byte random salt and calculates HMAC-SHA256."""
    salt = os.urandom(16)
    mac = hmac.new(secret_key, salt + text.encode('utf-8'), hashlib.sha256).hexdigest()
    return salt, mac

def verify_thought_frame(text: str, salt: bytes, expected_mac: str, secret_key: bytes) -> bool:
    """Verifies integrity using constant-time evaluation."""
    computed_mac = hmac.new(secret_key, salt + text.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_mac, expected_mac)
```
- Signs masked vectors with a CSPRNG salt and authenticates using constant-time comparison.

---

## 2. 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-2)
1. Feed string with API key `AIzaSy...` -> Replaced with `[MASKED_GEMINI_KEY]`.
2. Generate salt & MAC -> Verify with `verify_thought_frame` -> Returns `True`.

---

## 3. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-3)

### Why use `os.urandom(16)` for the salt?
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-5)
`os.urandom()` pulls random bytes directly from the Linux kernel or Windows cryptographic provider, guaranteeing that numbers cannot be predicted by external attackers.

---

## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-05_41-SEC-4)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_42_THOUGHT_VECTOR_EXPOSURE_AND_REASONING_LEAK_TRAPS.md`](/docs/devlog/01_42_THOUGHT_VECTOR_EXPOSURE_AND_REASONING_LEAK_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_38_THOUGHT_VECTOR_OBFUSCATION_EVIDENCE.md`](/docs/devlog/02_38_THOUGHT_VECTOR_OBFUSCATION_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_35_THOUGHT_VECTOR_HASHING_AND_MASKING_LOGS.md`](/docs/devlog/03_35_THOUGHT_VECTOR_HASHING_AND_MASKING_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_38_AGENTIC_CRYPTOGRAPHY_AND_VECTOR_MASKING_ARCHITECTURE.md`](/docs/devlog/04_38_AGENTIC_CRYPTOGRAPHY_AND_VECTOR_MASKING_ARCHITECTURE)
