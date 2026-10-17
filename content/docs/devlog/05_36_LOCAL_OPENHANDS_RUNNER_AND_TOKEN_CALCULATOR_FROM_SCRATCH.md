# Pillar 05.36: From-Scratch Creation Guide: Local GGUF Runner & Token Cost Calculator

## Overview & Beginner Context
This guide teaches you how to write a Python script from scratch that connects to a local GGUF model via `llama-cli` and calculates the financial cost of AI tokens in South African Rands (ZAR).

---

## 1. Line-by-Line Construction

### Block 1: Imports and Model Configuration (Lines 1–15)
```python
import subprocess
import os
import sys

DEFAULT_MODEL_PATH = os.path.expanduser("~/.models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
USD_TO_ZAR = 18.25

MODEL_RATES = {
    "gemini-flash": {"input_per_m": 0.075, "output_per_m": 0.30},
    "gemini-pro": {"input_per_m": 1.25, "output_per_m": 5.00}
}
```
- Defines the local file path to the quantized GGUF model and sets pricing tiers per million tokens.

### Block 2: The Local Offline Runner (Lines 16–35)
```python
def query_local_model(prompt: str, model_path: str = DEFAULT_MODEL_PATH) -> str:
    """Executes llama-cli with zero network egress."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Missing GGUF model at: {model_path}")
        
    cmd = [
        "llama-cli",
        "-m", model_path,
        "-p", prompt,
        "-n", "256",
        "--temp", "0.2",
        "-c", "2048",
        "--silent-prompt"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return proc.stdout.strip()
```
- Spawns `llama-cli` in a local subprocess with temperature set to 0.2 for deterministic extraction.

### Block 3: The Currency Translation Function (Lines 36–50)
```python
def calculate_cost_zar(model_key: str, in_tokens: int, out_tokens: int) -> float:
    rates = MODEL_RATES.get(model_key, MODEL_RATES["gemini-flash"])
    cost_usd = (in_tokens / 1e6 * rates["input_per_m"]) + (out_tokens / 1e6 * rates["output_per_m"])
    return round(cost_usd * USD_TO_ZAR, 2)
```
- Multiplies tokens by cloud rates and converts the result to ZAR.

---

## 2. Complete Finished File

```python
#!/usr/bin/env python3
import subprocess, os

USD_TO_ZAR = 18.25

def query_local_model(prompt: str) -> str:
    cmd = ["llama-cli", "-m", os.path.expanduser("~/.models/qwen2.5-1.5b-instruct-q4_k_m.gguf"), "-p", prompt, "-n", "256", "--silent-prompt"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()

def calculate_cost_zar(in_tokens: int, out_tokens: int) -> float:
    usd = (in_tokens / 1e6 * 0.075) + (out_tokens / 1e6 * 0.30)
    return round(usd * USD_TO_ZAR, 2)

if __name__ == "__main__":
    print("Testing Local Model & Token Cost Engine:")
    cost = calculate_cost_zar(500000, 100000)
    print(f"Cost of 600k tokens in ZAR: R{cost:.2f}")
```

---

## 3. 10-Second Verification Checklist
1. Run `python3 script.py` -> Outputs calculated ZAR cost.
2. Verify zero network sockets opened during local query.

---

## 4. Cross-Reference Navigation
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_37_OPENHANDS_LOCAL_INTEGRATION_AND_TOKEN_ECONOMICS.md`](/docs/devlog/01_37_OPENHANDS_LOCAL_INTEGRATION_AND_TOKEN_ECONOMICS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_33_OPENHANDS_LOCAL_BROKER_AND_TOKEN_COST_EVIDENCE.md`](/docs/devlog/02_33_OPENHANDS_LOCAL_BROKER_AND_TOKEN_COST_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS.md`](/docs/devlog/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_33_LOCAL_AGENTIC_RUNNER_AND_TOKEN_ECONOMICS_ARCHITECTURE.md`](/docs/devlog/04_33_LOCAL_AGENTIC_RUNNER_AND_TOKEN_ECONOMICS_ARCHITECTURE)
