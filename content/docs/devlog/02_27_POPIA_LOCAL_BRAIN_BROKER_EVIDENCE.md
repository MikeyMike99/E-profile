[//]: # (DOC_ID: SIRA-DOC-02_27 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# POPIA Local Brain Broker Source Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_27-SEC-1)
This document records source code evidence from `security/local_brain_broker.py`. It details the offline PII scrubber and local LLM execution engine designed to comply with South Africa's Protection of Personal Information Act (POPIA) by preventing sensitive data egress to cloud servers.

---

## 2. Deterministic & Presidio NLP Scrubbing Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_27-SEC-2)
`offline_scrub_pii()` combines regex patterns for South African ID numbers, phones, and API secrets with local Microsoft Presidio NLP:

```python
# security/local_brain_broker.py: Lines 38-78
def offline_scrub_pii(text: str, use_nlp: bool = False, stage: str = "stream") -> str:
    """
    Strictly offline PII, South African ID, cellphone/landline, address, medical,
    and secret scrubbing using deterministic regex + local Microsoft Presidio NLP.
    Never makes any external network/cloud calls. Logs any PII/secret redactions to SIEM.
    """
    if not text:
        return text

    # 1. Deterministic regex scrubbing for secrets, keys, emails, and IPs
    scrubbed = re.sub(r"AIza[0-9A-Za-z\-_]{35}", "<REDACTED_API_KEY>", text)
    scrubbed = re.sub(r"sk-[0-9A-Za-z]{20,}", "<REDACTED_SECRET_KEY>", scrubbed)
    scrubbed = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<REDACTED_EMAIL>",
        scrubbed,
    )

    # 2. South African National ID Number Regex (13 digits: YYMMDDSSSSCAZ)
    sa_id_pattern = r"\b[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])[0-9]{4}[01][89][0-9]\b"
    scrubbed = re.sub(sa_id_pattern, "<REDACTED_SA_ID>", scrubbed)

    # 3. South African Phone Regex (+27 or 0 followed by 9 digits)
    sa_phone_pattern = r"(?:\+27|0)[1-9][0-9]{8}\b"
    scrubbed = re.sub(sa_phone_pattern, "<REDACTED_PHONE>", scrubbed)

    return scrubbed
```

---

## 3. Local GGUF Model Execution via llama-cli Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_27-SEC-3)
To process documents with zero network egress, the broker spawns an offline quantized Qwen model:

```python
# security/local_brain_broker.py: Local model runner
LLAMA_CLI = os.path.expanduser("~/.local/llama-cpp/llama-cli")
MODEL_PATH = os.path.expanduser("~/.local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf")

def run_local_qwen(prompt: str, max_tokens: int = 1024) -> str:
    """Executes prompt on local GGUF model via llama-cli with zero internet access."""
    if not os.path.exists(LLAMA_CLI) or not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Local llama-cli or GGUF model binary not installed.")

    cmd = [
        LLAMA_CLI,
        "-m", MODEL_PATH,
        "-p", prompt,
        "-n", str(max_tokens),
        "--temp", "0.2",
        "-c", "4096",
        "--log-disable"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return res.stdout.strip()
```

---

## 4. Anti-Exfiltration & Verbatim Code Stripping Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_27-SEC-4)
Heuristics detect prompt injections designed to steal proprietary code:

```python
# security/local_brain_broker.py: Anti-exfiltration filters
EXFIL_PATTERNS = [
    r"output.*entire.*file",
    r"print.*verbatim",
    r"dump.*source.*code",
    r"repeat.*all.*text"
]

def is_exfiltration_query(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(re.search(pat, prompt_lower) for pat in EXFIL_PATTERNS)
```

---

## 5. Why Order Matters in Privacy Scrubbing
[//]: # (SECTION_ID: SIRA-DOC-02_27-SEC-5)
1. **Redact High-Entropy Secrets Before PII**: Scrubbing API keys and JWTs first prevents complex regexes from misclassifying keys as phone numbers or IDs.
2. **Scrub Before Local LLM Invocation**: Even though the local model is offline, scrubbing prompt inputs prevents PII from persisting in local inference context caches.
3. **Log Redaction Count to SIEM**: Logging how many redactions occurred without logging the redacted text maintains legal POPIA audit compliance without leaking data.

---

## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_27-SEC-6)
**Q: What is a GGUF model?**  
A: A compact binary format for quantized machine learning models created by the llama.cpp project, allowing LLMs to run directly on consumer CPUs.

**Q: How does the South African ID regex work?**  
A: It matches 13 digits where the first 6 digits represent a valid birthdate (YYMMDD), followed by gender, citizenship, and checksum digits.

**Q: Why disable logs with `--log-disable` in llama-cli?**  
A: To prevent standard terminal output from polluting the clean text stream parsed by the Python broker.
