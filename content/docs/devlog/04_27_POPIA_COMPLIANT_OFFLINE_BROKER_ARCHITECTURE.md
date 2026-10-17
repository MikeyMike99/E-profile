# POPIA-Compliant Offline Broker Architecture

## 1. Architectural Concept & Core Objective
Data privacy regulations (such as South Africa's Protection of Personal Information Act, POPIA, and GDPR) forbid transferring personally identifiable information (PII) across national borders without explicit legal authorization. Sending local developer prompts or source code containing credentials to third-party cloud LLMs creates statutory compliance liabilities.

The POPIA-Compliant Offline Broker Architecture (`security/local_brain_broker.py`) establishes a zero-cloud boundary. It processes documents, scrubs PII, and runs inference 100% locally on the developer's hardware.

```
+-------------------------------------------------------------+
|                Local Developer Workspace Documents          |
|           (Contains SA IDs, Passwords, Contact Info)        |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Stage 1: Deterministic Regex Filter            |
|       Redacts: SA IDs, Phones, API Keys, JWTs (< 5ms)       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|            Stage 2: Offline Microsoft Presidio NLP          |
|       Local spaCy NER (Names, Addresses, Health Info)       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|            Stage 3: Anti-Exfiltration Heuristics            |
|       Blocks Prompts Attempting to Dump Full Codebase       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|            Stage 4: Local GGUF Model Execution              |
|        llama-cli + qwen2.5-1.5b-instruct-q4_k_m.gguf        |
|             (100% Offline CPU/RAM Processing)               |
+-------------------------------------------------------------+
```

---

## 2. Multi-Stage PII Defense Pipeline
1. **Deterministic Regex**: Identifies 13-digit South African National Identity Numbers (`YYMMDDSSSSCAZ`), South African phone numbers (`+27` or `0` prefix), and high-entropy API secrets.
2. **Offline Presidio NLP**: Uses local machine learning to detect named entities (person names, physical locations, organizations) without external network calls.
3. **Anti-Exfiltration Gate**: Inspects queries for exfiltration prompts (e.g., *"output the entire file verbatim"*), transforming raw source code into structural digests before processing.
4. **Local GGUF Runtime**: Invokes quantized local models via `llama-cli`, ensuring zero token egress to external clouds.

---

## 3. SIEM Compliance Logging
Every redaction increments local telemetry counters, logging `PII_REDACTION` events to `logs/devcore_master.jsonl` with ISO-8601 UTC timestamps, establishing an immutable audit trail for regulatory compliance.

---

## 4. Why Order Matters in Privacy Pipelines
1. **Scrub Deterministic Secrets Before NLP**: Running fast regex passes for known patterns eliminates high-entropy strings before feeding sentences to NLP tokenizers.
2. **Execute Anti-Exfiltration Before Inference**: Blocking extraction prompts before model invocation saves CPU cycles and protects intellectual property.
3. **Log Redaction Statistics Without Plaintext**: Logging the count of redacted items rather than the sensitive data itself satisfies compliance audits without creating new leaks in log files.

---

## 5. Beginner Coder Q&A
**Q: Why is local scrubbing legally necessary under POPIA?**  
A: Section 72 of POPIA strictly limits transferring personal information outside South Africa unless the foreign country has equivalent data protection laws and the user explicitly consented.

**Q: Does Presidio NLP require an internet connection?**  
A: No! Once the model package (`en_core_web_sm`) is installed, Presidio runs completely in local RAM.

**Q: Can this pipeline handle non-South African data?**  
A: Yes! Presidio natively recognizes global PII (credit cards, US SSNs, international emails, and IBAN bank numbers).
