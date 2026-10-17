[//]: # (DOC_ID: SIRA-DOC-01_31 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# POPIA Data Privacy & Cloud Egress Traps

## 1. The Problem: The Cloud Scrubbing Paradox
[//]: # (SECTION_ID: SIRA-DOC-01_31-SEC-1)
When developers build AI applications handling user data, standard practice often delegates data privacy to cloud-hosted API models. However, under strict data protection laws such as South Africa's **POPIA** (Protection of Personal Information Act, Act 4 of 2013) and Europe's GDPR, transmitting raw personally identifiable information (PII) to foreign cloud servers without explicit user consent constitutes an immediate regulatory violation.

The trap: sending unscrubbed documents to a cloud LLM with the prompt *"Please remove all PII from this text"* is an illegal cross-border data transfer! The cloud provider's servers ingest the raw PII before the model can redact it.

```
+-------------------------------------------------------------+
|             Local User File (Contains SA ID, Medical Data)  |
+-------------------------------------------------------------+
                              |
                     ILLEGAL CROSS-BORDER EGRESS
                     Transmits Raw Data to Cloud API
                              |
                              v
+-------------------------------------------------------------+
|                     Cloud LLM Provider                      |
|            [POPIA VIOLATION: Section 72 Breach]             |
|   - Transmitted without user consent                        |
|   - Subject to statutory fines up to R10 million            |
+-------------------------------------------------------------+
```

---

## 2. Ineffectiveness of Generic Regex Scrubbing
[//]: # (SECTION_ID: SIRA-DOC-01_31-SEC-2)
Initial attempts to solve this locally used basic regex patterns for email addresses and phone numbers. However, real-world data contains complex regional identifiers:
- 13-digit South African National Identity Numbers (which encode date of birth, citizenship status, and checksum algorithms).
- Local cellphone and landline formats (`+27`, `082`, `011`).
- Physical residential addresses and medical aid numbers.
Generic regexes missed edge cases or aggressively mangled legitimate code variables.

---

## 3. The Solution: Local Presidio NLP & Offline Qwen Broker
[//]: # (SECTION_ID: SIRA-DOC-01_31-SEC-3)
Siraugga instituted the POPIA Offline Brain Broker (`security/local_brain_broker.py`):
1. **Zero Cloud Egress**: Document processing and scrubbing run 100% locally on the host machine.
2. **Hybrid Scrubbing Engine**: Combines deterministic regex with local Microsoft Presidio NLP to identify entities without network calls.
3. **Local GGUF Model Execution**: Uses `llama-cli` with quantized local models (`qwen2.5-1.5b-instruct-q4_k_m.gguf`), ensuring data never leaves local RAM.
4. **Verbatim Code Stripping**: Proprietary source code lines are converted into structural digests, preventing verbatim IP leaks.

---

## 4. Why Order Matters in Privacy Governance
[//]: # (SECTION_ID: SIRA-DOC-01_31-SEC-4)
1. **Scrub PII Before Any Network Transmission**: Redaction must occur in local process memory before any data packet touches an HTTP or WebSocket socket.
2. **Deterministic Regex Before NLP**: Running fast regex passes for known API keys and secrets throttles the volume of text that requires expensive NLP token parsing.
3. **Audit Log to Local SIEM**: Every redaction must be logged in `devcore_master.jsonl` to provide a legally verifiable compliance audit trail.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_31-SEC-5)
**Q: What is POPIA?**  
A: The Protection of Personal Information Act—South Africa's comprehensive data privacy law governing how organizations collect, process, and store personal data.

**Q: Why is local Presidio better than cloud APIs?**  
A: Presidio runs inside Python on your local computer. It does not send any text over the internet, keeping processing 100% compliant with cross-border transfer laws.

**Q: Can local AI models run without a dedicated GPU?**  
A: Yes! Modern 4-bit quantized GGUF models run efficiently on standard consumer CPUs with minimal RAM usage.
