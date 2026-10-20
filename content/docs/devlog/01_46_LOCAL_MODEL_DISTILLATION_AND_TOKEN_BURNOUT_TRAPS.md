[//]: # (DOC_ID: SIRA-DEV-01_46 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 01.46: Problems Encountered: Local Model Distillation & Token Burnout Traps

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-1)
## Overview & Context
Modern agentic workflows depend heavily on frontier Large Language Models (LLMs) hosted in cloud environments. While cloud LLMs excel at complex reasoning, relying on them for routine repetitive tasks—such as summarizing multi-megabyte log files, distilling long session histories, answering simple user queries, or generating test quizzes—creates severe architectural vulnerabilities. These vulnerabilities include rapid API rate-limit exhaustion, skyrocketing token costs, privacy exposure of sensitive workstation code, and high network latency.

```text
Naive Cloud-Only Pipeline (Exhaustion & Leak Prone):
[Raw 20k Log / Context] ──► [Cloud LLM API] ──► [Token Quota Burn + Latency Spike + WAN Leak]

Hybrid Edge-Cloud Architecture (Resilient & Sovereign):
[Raw 20k Log / Context] ──► [Offline PII Scrubber] ──► [Local CPU Qwen2.5-1.5B (GGUF)]
                                                                    │
                                                [Dense Digest / Exam / Query Result]
                                                                    │ (0 Cloud Tokens Consumed)
                                                                    ▼
                                                    [Token Telemetry Engine & SIEM]
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-2)
## 1. The Token Burnout & Distillation Traps

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-3)
### The Megabyte Context Re-Reading Trap
- **What Happened**: In multi-step developer sessions, agents repeatedly read entire 500-line to 2,000-line source files into the conversational history to extract brief summaries. Within 10 to 15 turns, input tokens escalated beyond 100,000 per turn, burning through hourly rate limits and generating steep API costs.
- **Root Cause**: The absence of an offline, in-process context distillation filter forced the agent to shuttle raw source files across the WAN to the cloud LLM, duplicating identical code in prompt context.

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-4)
### The Static UI Dropdown & Hardcoded Model Trap
- **What Happened**: Early iterations attempted to expose offline models by hardcoding `<option value="Local Qwen 2.5 (Offline)">` directly inside `sandbox/templates/index.html`. However, upon page load, the frontend JavaScript (`fetchModels()`) queries `GET /api/models` and overwrites `modelSelect.innerHTML` with the backend's dynamic model list, erasing any hardcoded HTML options.
- **Root Cause**: The Web Portal relies on dynamic model discovery (`fetch_dynamic_models` in `core/server.py`) rather than static HTML markup. Local GGUF models must be discovered dynamically from `$HOME/.local/models/*.gguf` via `discover_local_models()` and merged directly into the `/api/models` payload.

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-5)
### The Stateless Ephemeral Chat & Missing Transcript Trap
- **What Happened**: When routing a web portal prompt directly to `llama-cli` on CPU instead of spawning the cloud `agy` CLI, initial implementations returned the response chunk over WebSocket but failed to promote temporary `conv-...` IDs to canonical UUIDs or append turns to `transcript.jsonl`. Subsequent follow-up questions had no memory of prior turns, and the live token meter badge remained unpopulated.
- **Root Cause**: Bypassing the external CLI also bypassed its automatic session transcript creation. The local runner (`execute_local_agent_task`) must explicitly manage `transcript.jsonl` (`_load_and_append_user_turn` and `_append_planner_response`), register session ownership, and broadcast `init_conv_id` and `token_telemetry` WebSocket events.

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-6)
### The Large Local Model Memory Collapse Trap
- **What Happened**: Early attempts to introduce local offline inference attempted to load unquantized 7B or 14B parameter models in standard developer environments without dedicated enterprise GPUs. The host machine suffered out-of-memory (OOM) kernel panics, frozen desktop windows, and 60-second execution timeouts.
- **Root Cause**: Developers often assume that local AI requires massive GPU hardware. For distillation and structured quiz generation, high-parameter models are overkill. The solution required a lightweight, CPU-optimized 1.5B 4-bit quantized model (`qwen2.5-1.5b-instruct-q4_k_m.gguf`) running via `llama-cli`.

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-7)
### The Unscrubbed Prompt Leak & Invisible Token Blindspot Traps
- **What Happened**: Passing raw developer project files to local or external models risked exposing personal API keys, passwords, email addresses, and private filesystem paths. Furthermore, administrators had zero real-time visibility into prompt cache hit rates or local token savings because metrics were buried inside raw JSONL transcripts.
- **Root Cause**: Offline pipelines require two-stage data loss prevention (`offline_scrub_pii`) on both input and output, paired with an incremental cursor-based telemetry engine (`TokenTelemetryEngine`) to surface live KPIs on `/telemetry`.

---

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-8)
## 2. Invariant Rules for Local Distillation & Token Economics
1. **Dynamic Model Discovery Only**: Never hardcode model `<option>` tags in `index.html`; always discover `.gguf` models dynamically in `discover_local_models()` and serve them through `GET /api/models`.
2. **Full Session Transcript Parity**: Local model executions must persist `USER_INPUT` and `PLANNER_RESPONSE` entries to `transcript.jsonl` and broadcast `init_conv_id` and `token_telemetry` events.
3. **Two-Stage PII Sanitization**: Every payload fed to or returned by the local model must pass through `offline_scrub_pii` before storage or broadcasting.
4. **Zero Host OOM Guarantee**: The local runtime must use 4-bit quantization with CPU thread constraints, consuming under 1.5 GB of RAM.

---

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-9)
## 3. Beginner Coder Q&A

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-10)
### Why did hardcoding an `<option>` tag in `index.html` disappear when the page loaded?
Modern web portals populate dropdowns dynamically from an API (`GET /api/models`) so that newly installed models appear automatically without editing HTML. When the JavaScript `fetchModels()` function runs on startup, it clears `modelSelect.innerHTML` and rebuilds the options from the server's JSON response.

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-11)
### Does running the model locally require an expensive Nvidia graphics card?
No. By utilizing `llama-cli` with 4-bit quantization (`q4_k_m`), the entire model occupies only ~1.06 GB of disk space and runs entirely on standard multi-core CPUs in 4 to 6 seconds per query, with zero GPU hardware requirements.

---

[//]: # (SECTION_ID: SIRA-DEV-01_46-SEC-12)
## 4. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Scope / Chapter |
| :--- | :--- | :--- |
| **Token Burst & Rollover** | Session history truncation vs. local distillation mitigation. | `01_43_TOKEN_BURST_PREMATURE_ROLLOVER_AND_MIDTASK_RESET_TRAPS.md` |
| **Source Code Evidence** | Exact implementations of `local_model_service.py`, `server.py`, and `token_telemetry.py`. | `02_42_LOCAL_MODEL_AND_TOKEN_TELEMETRY_EVIDENCE.md` |
| **Diagnostic Test Logs** | Live inference, compression, dynamic model discovery, and telemetry benchmark outputs. | `03_39_LOCAL_MODEL_AND_TOKEN_TELEMETRY_AUDIT_LOGS.md` |
| **Architectural Blueprint** | System architecture, dynamic `/api/models` flow, and component interactions. | `04_42_LOCAL_MODEL_TOKEN_OPTIMIZATION_AND_DISTILLATION_ARCHITECTURE.md` |
| **From-Scratch Guide** | Step-by-step DIY guide to writing the local service from a blank file. | `05_45_LOCAL_MODEL_SERVICE_AND_TELEMETRY_ENGINE_FROM_SCRATCH.md` |

</details>
