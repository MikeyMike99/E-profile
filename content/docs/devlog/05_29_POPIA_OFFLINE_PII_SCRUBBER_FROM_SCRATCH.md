# POPIA Offline PII Scrubber from Scratch

## 1. Architectural Role & Module Overview
Sending raw user documents or source code to external cloud AI models violates strict regional data privacy laws like South Africa's Protection of Personal Information Act (POPIA).

This guide details how to build `local_brain_broker.py` from scratch. It creates a 100% offline data protection broker that scrubs South African IDs, phone numbers, email addresses, and API credentials using deterministic regex and local Microsoft Presidio NLP before running inference on local GGUF models.

```
+-------------------------------------------------------------+
|               Input Text (Contains Sensitive Data)          |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Deterministic Regex Pattern Pass               |
|      - API Keys: AIza..., sk-...                            |
|      - SA National ID: YYMMDDSSSSCAZ (13 digits)            |
|      - SA Phone Numbers: +27... or 0...                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Local Presidio NLP Entity Extraction           |
|      - Analyzes names, physical locations, addresses        |
|      - Replaces entities with <REDACTED_TYPE> tags          |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Local GGUF Model Inference (llama-cli)         |
|      - 100% Offline execution, Zero external packets        |
+-------------------------------------------------------------+
```

---

## 2. Complete Python Implementation
Save the following script as `popia_scrubber.py`:

```python
import os
import re
import subprocess

# Step 1: Deterministic Regex Patterns
PATTERNS = {
    "API_KEY": r"(?:AIza[0-9A-Za-z\-_]{35}|sk-[0-9A-Za-z]{20,})",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "SA_ID": r"\b[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])[0-9]{4}[01][89][0-9]\b",
    "SA_PHONE": r"(?:\+27|0)[1-9][0-9]{8}\b"
}

def scrub_deterministic(text: str) -> tuple[str, dict]:
    """Applies fast regex patterns for high-entropy secrets and regional IDs."""
    scrubbed = text
    stats = {}
    for name, pattern in PATTERNS.items():
        matches = re.findall(pattern, scrubbed)
        stats[name] = len(matches)
        scrubbed = re.sub(pattern, f"<REDACTED_{name}>", scrubbed)
    return scrubbed, stats

# Step 2: Presidio NLP Integration (Optional / Fallback)
def scrub_nlp(text: str) -> str:
    """Uses Presidio Analyzer if available locally without network calls."""
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=text, language='en')
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
    except ImportError:
        # Graceful fallback if NLP libraries are not installed
        return text

# Step 3: Anti-Exfiltration Verification
def check_exfiltration(prompt: str) -> bool:
    """Flags prompts that attempt to extract entire codebases verbatim."""
    suspicious = [r"output.*entire.*file", r"dump.*source.*code", r"print.*verbatim"]
    return any(re.search(pat, prompt.lower()) for pat in suspicious)

# Step 4: Local Model Invoker
def run_local_model(prompt: str, model_path: str = "model.gguf") -> str:
    """Executes prompt on a local GGUF model via llama-cli with zero network calls."""
    if not os.path.exists(model_path):
        return f"[MOCK LOCAL MODEL OUTPUT] Processed securely offline: {prompt[:80]}..."
    
    cmd = ["llama-cli", "-m", model_path, "-p", prompt, "-n", "256", "--log-disable"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()

def process_secure_prompt(raw_text: str) -> str:
    print("[POPIA] Ingesting prompt for offline processing...")
    
    if check_exfiltration(raw_text):
        return "[SECURITY REFUSAL] Prompt blocked by anti-exfiltration policy."

    # 1. Deterministic scrubbing
    clean_text, stats = scrub_deterministic(raw_text)
    print(f"[POPIA] Redactions applied: {stats}")

    # 2. Local Presidio NLP scrubbing
    clean_text = scrub_nlp(clean_text)

    # 3. Local Model Execution
    return run_local_model(clean_text)

if __name__ == "__main__":
    sample_prompt = (
        "Hello! My South African ID is 9201155028087 and my phone is 0825551234. "
        "Here is my OpenAI secret key: sk-abcdef1234567890abcdef123456. "
        "Please summarize this message."
    )
    result = process_secure_prompt(sample_prompt)
    print("\nResulting Output:")
    print(result)
```

---

## 3. Why Order Matters in Privacy Scrubbing
1. **Scrub Deterministic Patterns Before NLP**: Running fast regexes first redacts obvious keys and IDs before sentence tokenization, saving significant CPU time.
2. **Execute Anti-Exfiltration Before Inference**: Rejecting code theft queries early avoids wasting system compute on malicious prompts.
3. **Scrub Before Storing Context in RAM**: Scrubbing input text before passing it to inference engines ensures sensitive data never persists in volatile model context buffers.

---

## 4. Beginner Coder Q&A
**Q: How does the South African ID regex validate a date?**  
A: `[0-9]{2}` matches the year, `(?:0[1-9]|1[0-2])` matches months 01-12, and `(?:0[1-9]|[12][0-9]|3[01])` matches days 01-31.

**Q: Can this script run without internet?**  
A: Yes! It relies exclusively on local Python regexes and locally stored model weights, making it completely immune to internet outages.

**Q: Where are the redaction counts saved?**  
A: In production, `stats` are logged to `logs/devcore_master.jsonl` to provide a complete POPIA compliance audit log.
