# Pillar 01.37: Problems Encountered: OpenHands Integration & Token Economics Traps

## Overview & Context
As autonomous agentic workflows scale, developers experiment with external orchestration runtimes like OpenHands to delegate multi-step code modification and terminal execution. However, blindly connecting external agent frameworks to cloud LLM APIs leads to severe financial exposure, quota exhaustion, and unmonitored token burn.

```
Unmonitored Cloud API Agent Loop:
Agent ──(High-effort queries)──► Cloud API ──(Exhausts Rate Limits)──► HTTP 429
                                   │
                                   ▼
                Severe Billing Shock ($$$ in USD / ZAR)
```

---

## 1. The Token Economics Traps

### The Uncontrolled Cloud Token Burn
- **What Happened**: Running an agentic loop on high-reasoning cloud models during autonomous debugging burned millions of tokens within hours. In South Africa and other non-USD regions, exchange rate multipliers convert minor cloud bills into thousands of South African Rands (ZAR).
- **Root Cause**: Autonomous coding agents submit entire conversation histories and multi-file contexts on every turn. Without local token tracking and strict budget cutoffs, loops execute unchecked.

### The External Agent Sandbox Escape
- **What Happened**: Integrating OpenHands inside the project workspace presented security challenges because external agent runtimes often expect unrestricted Docker socket access (`/var/run/docker.sock`) or raw bash execution, bypassing DevCore's Zero-Trust RBAC tiers.
- **Root Cause**: Third-party agent frameworks are built with the assumption that the agent is either running in a dedicated throwaway VM or has full root privileges, conflicting with Siraugga's in-game developer sandbox.

### Local Quantized Model Context Limitations
- **What Happened**: When routing OpenHands to local quantized models (e.g. Qwen 2.5 1.5B via `llama-cli`), the model struggled with complex multi-file refactors and hallucinated CLI arguments due to restricted context window sizes (2048–4096 tokens).
- **Root Cause**: Compact 1.5B GGUF models are optimized for single-turn extraction, classification, and PII scrubbing, not 50-step autonomous agentic planning.

---

## 2. Why Order Matters in Local Agent Orchestration
1. **Local Pre-Flight Token Budgeting**: You must calculate and inspect token usage across 24-hour and 7-day windows before spawning autonomous agents.
2. **Tiered Model Routing**: Low-complexity tasks (formatting, regex generation, PII masking) must route to local GGUF models first, reserving cloud API credits exclusively for high-level architectural planning.
3. **Execution Guardrails Before Runtime Boot**: Tool-use interception hooks must be active before launching an external agent engine to prevent destructive commands (`rm -rf`, raw privilege escalation).

---

## 3. Beginner Coder Q&A

### How do I calculate how much an AI agent is actually costing me?
Multiply input tokens by the model's prompt price per million tokens, add output tokens multiplied by completion price per million tokens, and apply your local currency exchange rate (e.g., USD to ZAR). DevCore automates this in its telemetry pipeline.

### Why use OpenHands when DevCore already has its own agent manager?
OpenHands serves as a benchmark and pluggable testing ground. Testing multiple agent runtimes against identical tasks reveals edge cases in sandbox security, tool interception, and cross-platform I/O.

---

## 4. Cross-Reference Navigation
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_33_OPENHANDS_LOCAL_BROKER_AND_TOKEN_COST_EVIDENCE.md`](/docs/devlog/02_33_OPENHANDS_LOCAL_BROKER_AND_TOKEN_COST_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS.md`](/docs/devlog/03_30_OPENHANDS_LOCAL_INFERENCE_AND_TOKEN_COST_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_33_LOCAL_AGENTIC_RUNNER_AND_TOKEN_ECONOMICS_ARCHITECTURE.md`](/docs/devlog/04_33_LOCAL_AGENTIC_RUNNER_AND_TOKEN_ECONOMICS_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_36_LOCAL_OPENHANDS_RUNNER_AND_TOKEN_CALCULATOR_FROM_SCRATCH.md`](/docs/devlog/05_36_LOCAL_OPENHANDS_RUNNER_AND_TOKEN_CALCULATOR_FROM_SCRATCH)
