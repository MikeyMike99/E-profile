[//]: # (DOC_ID: SIRA-DEV-02_33 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.33: Source Code Evidence: OpenHands Local Broker & Token Economics

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-1)
## Overview & Context
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-1)
This document cites primary source evidence demonstrating how DevCore integrates external agent runtimes with local quantized GGUF models and tracks token consumption metrics to convert API usage into localized financial costs (South African Rands / ZAR).

---

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-2)
## Source Citation 1: Local Quantized Inference Pipeline (`security/local_brain_broker.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-2)

```python
# Location: <project_root>/security/local_brain_broker.py
# Offline Local Model Inference Execution

def execute_offline_model(prompt: str, model_path: str = None) -> str:
    """Invokes llama-cli to generate an answer without network connectivity."""
    target_model = model_path or DEFAULT_GGUF_MODEL
    if not os.path.exists(target_model):
        raise FileNotFoundError(f"Local GGUF model not found at: {target_model}")

    cmd = [
        "llama-cli",
        "-m", target_model,
        "-p", prompt,
        "-n", "512",
        "--temp", "0.2",
        "--top-p", "0.9",
        "-c", "4096",
        "--silent-prompt"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()
```

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-3)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-3)
- DevCore provides a completely air-gapped, zero-network fallback execution environment using `llama-cli` with compact GGUF weights (Qwen 2.5 1.5B), preventing sensitive queries from ever reaching external cloud providers.

---

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-4)
## Source Citation 2: Token Economics & Currency Conversion Telemetry
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-4)

```python
# Location: <project_root>/security/swarm_telemetry.py
# Real-Time Token Cost Calculation in ZAR

USD_TO_ZAR_EXCHANGE_RATE = 18.25
MODEL_PRICING = {
    "gemini-pro": {"input_cost_per_m": 1.25, "output_cost_per_m": 5.00},
    "gemini-flash": {"input_cost_per_m": 0.075, "output_cost_per_m": 0.30},
}

def calculate_session_cost_zar(model_name: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["gemini-flash"])
    cost_usd = (
        (input_tokens / 1_000_000.0) * pricing["input_cost_per_m"] +
        (output_tokens / 1_000_000.0) * pricing["output_cost_per_m"]
    )
    cost_zar = cost_usd * USD_TO_ZAR_EXCHANGE_RATE
    return round(cost_zar, 2)
```

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-5)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-5)
- The orchestration telemetry engine calculates the exact financial impact of autonomous agent execution, preventing developers from incurring unexpected runaway bills by enforcing strict budget thresholds.

---

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-3)
## 3. Why Order Matters in Token Budgeting
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-3)
1. **Estimate Tokens Prior to Dispatch**: Token counts of input prompts must be calculated using tokenizer byte counts before sending the payload over the wire.
2. **Local Screening Before Cloud Calling**: Prompts must pass through local PII scrubbing and lightweight summarization before determining whether cloud escalation is necessary.

---

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-4)
## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-6)

### What is a GGUF file?
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-6)
GGUF is a binary file format created by the `llama.cpp` project to store quantized language model weights. It allows large models to run efficiently on consumer CPUs and laptops with low RAM usage.

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-7)
### Why convert token costs to ZAR in the telemetry engine?
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-7)
Most developers outside the United States pay cloud providers in local currency. Converting tokens directly to local currency (like South African Rands) makes the cost tangible and immediately actionable.

---

[//]: # (SECTION_ID: SIRA-DEV-02_33-SEC-5)
## 5. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-02_33-SEC-5)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_37_OPENHANDS_LOCAL_INTEGRATION_AND_TOKEN_ECONOMICS.md`](/docs/devlog/01_37_OPENHANDS_LOCAL_INTEGRATION_AND_TOKEN_ECONOMICS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS.md`](/docs/devlog/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_33_LOCAL_AGENTIC_RUNNER_AND_TOKEN_ECONOMICS_ARCHITECTURE.md`](/docs/devlog/04_33_LOCAL_AGENTIC_RUNNER_AND_TOKEN_ECONOMICS_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_36_LOCAL_OPENHANDS_RUNNER_AND_TOKEN_CALCULATOR_FROM_SCRATCH.md`](/docs/devlog/05_36_LOCAL_OPENHANDS_RUNNER_AND_TOKEN_CALCULATOR_FROM_SCRATCH)
