[//]: # (DOC_ID: SIRA-DEV-04_33 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 04.33: Architectural Blueprint: Local Agentic Runner & Token Economics

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-1)
## Executive Summary
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-1)
This blueprint establishes the architectural model for integrating local, sovereign agentic runtimes (such as OpenHands or specialized subagents) with compact, quantized language models (`llama-cli` with Qwen 2.5 GGUF) and a real-time token tracking telemetry engine that translates API consumption directly into South African Rands (ZAR).

---

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-1)
## 1. Hybrid Orchestration Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-1)

```
User Task Submission:
          │
          ▼
Central Orchestrator
          │
          ├── Task is High-Level Planning? ──► Cloud API (Gemini Pro/Flash)
          │                                           │
          │                                           ▼
          │                                  Telemetry Cost Ledger (ZAR)
          │
          └── Task is PII Scrubbing / AST? ──► Local Llama-CLI (Zero Network)
                                                      │
                                                      ▼
                                             Zero Cloud API Cost
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-2)
## 2. Core Functional Modules
[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-1)

### 1. The Local Brain Broker (`security/local_brain_broker.py`)
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-1)
- Executes entirely offline using `llama-cli` and 4-bit quantized GGUF weights.
- Processes high-frequency, low-complexity structural operations: PII redaction, JSON formatting, AST symbol extraction, and regex classification.
- Guarantees zero cloud egress for sensitive student content and local passwords, complying with South African POPIA Section 72 cross-border data transfer regulations.

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-2)
### 2. The Multi-Tier Token Telemetry Engine (`security/swarm_telemetry.py`)
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-2)
- Captures input and output token counts across every HTTP and WebSocket agent invocation.
- Maintains rolling 24-hour and 7-day sliding window ledgers.
- Computes exact financial expenditures using dynamically configurable foreign exchange rates (USD to ZAR), automatically throttling or alerting when predefined daily spending caps are reached.

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-3)
### 3. The Isolated Agent Execution Boundary
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-3)
- Restricts external agent runtimes (like OpenHands) to assigned project directories (`playground/<project_name>`).
- Intercepts raw shell execution through the PreToolUse security hook, blocking destructive root commands and preventing Docker socket mounting exploits.

---

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-3)
## 3. Why Order Matters in Hybrid Routing
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-3)
1. **Sanitize via Local Model Before Cloud Transmission**: Sensitive data must be stripped in local RAM *before* sending payloads across external network connections.
2. **Compute Token Budget Before Spawning Swarms**: The orchestrator must verify that available budget headroom exists in the 24-hour sliding ledger before launching multi-agent parallel workflows.

---

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-4)
## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-2)

### How does the system determine whether to use the local model or the cloud?
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-2)
The orchestrator checks task type and classification tier. High-risk, sensitive content (such as private exam vaults or student records) is hardcoded to Tier 5 Local Processing, while generic game script generation can be routed to cloud models.

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-3)
### Can I adjust the USD-to-ZAR exchange rate?
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-3)
Yes. The exchange rate is defined as a parameter in `security/swarm_telemetry.py` or can be fetched periodically from a local currency cache.

---

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-5)
## 5. Reusable Quick-Start Recipe (2-Minute Deployment)
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-5)
1. Ensure `llama-cli` and `qwen2.5-1.5b-instruct-q4_k_m.gguf` are located in your models directory.
2. Initialize broker: `from security.local_brain_broker import execute_offline_model`.
3. Track telemetry: `cost = calculate_session_cost_zar('gemini-flash', prompt_tokens, completion_tokens)`.

---

[//]: # (SECTION_ID: SIRA-DEV-04_33-SEC-6)
## 6. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-04_33-SEC-6)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_37_OPENHANDS_LOCAL_INTEGRATION_AND_TOKEN_ECONOMICS.md`](/docs/devlog/01_37_OPENHANDS_LOCAL_INTEGRATION_AND_TOKEN_ECONOMICS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_33_OPENHANDS_LOCAL_BROKER_AND_TOKEN_COST_EVIDENCE.md`](/docs/devlog/02_33_OPENHANDS_LOCAL_BROKER_AND_TOKEN_COST_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS.md`](/docs/devlog/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_36_LOCAL_OPENHANDS_RUNNER_AND_TOKEN_CALCULATOR_FROM_SCRATCH.md`](/docs/devlog/05_36_LOCAL_OPENHANDS_RUNNER_AND_TOKEN_CALCULATOR_FROM_SCRATCH)
