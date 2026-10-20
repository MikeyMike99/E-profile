[//]: # (DOC_ID: SIRA-DEV-02_42 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.42: Source Code Evidence: Local Model Service & Token Telemetry Architecture

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-1)
## Overview & Context
This document provides forensic source code citations for the DevCore Local Model Token Optimization and Context Distillation architecture. It details dynamic GGUF model discovery, the offline Qwen inference engine, multi-turn session transcript persistence, PII sanitization pipelines, the real-time token telemetry engine, and Raugus VFS resolver integration.

---

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-2)
## 1. Dynamic Local Model Discovery (`core/local_model_service.py` & `core/server.py`)

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-3)
### Scanning Local GGUF Models (`discover_local_models`)
```python
def discover_local_models() -> list:
    """Dynamically discovers installed GGUF models in ~/.local/models/ for the UI model selector."""
    models_dir = os.path.expanduser("~/.local/models")
    if not os.path.isdir(models_dir):
        return [{"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"}]
    discovered = []
    try:
        for fname in sorted(os.listdir(models_dir)):
            if not fname.lower().endswith(".gguf"):
                continue
            low = fname.lower()
            if "qwen2.5" in low:
                label = "Local Qwen 2.5 (Offline)"
            else:
                stem = os.path.splitext(fname)[0]
                label = f"Local {stem} (Offline)"
            if not any(d["value"] == label for d in discovered):
                discovered.append({"value": label, "text": label})
    except Exception:
        pass
    return discovered or [{"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"}]
```
- **What This Proves**: Instead of hardcoding `<option>` elements inside `index.html`, the backend dynamically inspects `$HOME/.local/models/` for `.gguf` files and merges them into `fetch_dynamic_models()` in `core/server.py` so `GET /api/models` populates the Web Portal selector automatically.

---

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-4)
## 2. Semantic Compression & Multi-Turn Execution (`core/local_model_service.py`)

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-5)
### Semantic Context Compression Function (`compress_context`)
```python
def compress_context(raw_text: str, target_tokens: int = 400, context_label: str = "general") -> str:
    """Compresses large raw files or logs into a dense semantic summary using local Qwen."""
    if not raw_text or not raw_text.strip():
        return ""

    pre_scrubbed = offline_scrub_pii(raw_text[:20000], stage="compress_input")
    system_prompt = (
        "You are an ultra-concise technical distillation engine. Extract only core architecture, "
        "key logic, active errors, and critical data points. Omit fluff, greetings, and boilerplate."
    )
    user_prompt = (
        f"RAW CONTEXT:\n{pre_scrubbed}\n\n"
        f"Produce a high-density executive digest under {target_tokens} words. "
        "Highlight key functions, active states, and critical constraints."
    )
    digest = run_local_qwen(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=target_tokens + 100,
        target_label=f"compress:{context_label}",
    )
    return offline_scrub_pii(digest, stage="compress_output")
```
- **What This Proves**: Multi-thousand word inputs are pre-scrubbed for sensitive PII before ingestion, distilled on a local CPU model into an executive summary, and re-scrubbed on output with zero cloud token consumption.

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-6)
### Session Persistence & Local Agent Execution (`execute_local_agent_task`)
```python
async def execute_local_agent_task(
    agent_mgr,
    prompt: str,
    model: str,
    task_time: float,
    conversation_id: str,
    user: dict = None,
    is_admin: bool = False,
):
    """Executes a Web Portal prompt directly on the local model with full session persistence and UI synchronization."""
    await agent_mgr.broadcast({"type": "agent_start", "model": model})

    if not conversation_id or str(conversation_id).startswith("conv-"):
        conversation_id = str(uuid.uuid4())
    agent_mgr.current_conversation_id = conversation_id

    brain_dir = os.path.expanduser("~/.gemini/antigravity-cli/brain")
    transcript_path, next_step_idx, recent_context = _load_and_append_user_turn(
        brain_dir, conversation_id, clean_prompt
    )

    await agent_mgr.broadcast({
        "type": "init_conv_id",
        "conversation_id": conversation_id,
        "real_model": model,
    })

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None, query_local_model, clean_prompt, recent_context, 900, "portal_chat", "web_portal"
    )

    _append_planner_response(transcript_path, next_step_idx, response, usage_payload)
    await agent_mgr.broadcast({"type": "agent_chunk", "chunk": response})
    await agent_mgr.broadcast({
        "type": "token_telemetry",
        "usage": usage_payload,
        "conversation_id": conversation_id,
    })
```
- **What This Proves**: Web portal chats targeting a local offline model promote temporary `conv-...` IDs to canonical UUIDs, persist multi-turn history in `transcript.jsonl`, broadcast live `token_telemetry` badges, and report 5-tuple metrics to `SwarmFlowLogger`.

---

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-7)
## 3. Token Telemetry Engine & Raugus VFS (`core/token_telemetry.py`)

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-8)
### Live Step Recording & Session Rollup
```python
class TokenTelemetryEngine:
    def __init__(self, brain_dir=None):
        self._brain_dir = brain_dir or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        self._tz = datetime.timezone(datetime.timedelta(hours=2))
        self._file_cursors = {}
        self._steps = []
        self._sessions = {}
        self._last_refresh = 0.0

    def record_live_step(self, conv_id: str, step_data: dict):
        inp = int(step_data.get("input_tokens") or 0)
        cache = int(step_data.get("cache_read_tokens") or 0)
        out = int(step_data.get("output_tokens") or 0)
        if inp <= 0 and cache <= 0 and out <= 0:
            return

        total = inp + cache + out
        step = {
            "ts": dt.timestamp(), "dt": dt, "conv_id": conv_id,
            "inp": inp, "cache": cache, "out": out, "total": total,
        }
        self._steps.append(step)
```
- **What This Proves**: Token consumption (input, cache hits, output) is parsed incrementally using file seek cursors across all brain sessions, while the Raugus Resolver MCP Server (`raugus-resolver`) exposes all 11 symbols inside `devcore.core.local_model_service.py` under Tier 5 RBAC for zero-downtime hot-patching.

---

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-9)
## 4. Beginner Coder Q&A

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-10)
### What does `loop.run_in_executor(None, query_local_model, ...)` do?
Because Quart is an asynchronous framework, running a CPU-heavy subprocess like `llama-cli` on the main thread would block all other incoming HTTP requests and WebSocket connections. Running it in an executor thread offloads the calculation so the server remains completely responsive.

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-11)
### Why do we track `cache_read_tokens` separately from `input_tokens`?
Modern LLM providers offer prompt caching discounts. A token read from cache is billed at roughly 25% of standard input cost and processes significantly faster. Tracking cache hits separately allows the telemetry engine to report true monetary cost and cache efficiency.

---

[//]: # (SECTION_ID: SIRA-DEV-02_42-SEC-12)
## 5. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Scope / Chapter |
| :--- | :--- | :--- |
| **Problem Traps** | Memory exhaustion, static UI dropdown traps, and prompt leaks. | `01_46_LOCAL_MODEL_DISTILLATION_AND_TOKEN_BURNOUT_TRAPS.md` |
| **Diagnostic Test Logs** | Forensic execution verification and benchmark logs. | `03_39_LOCAL_MODEL_AND_TOKEN_TELEMETRY_AUDIT_LOGS.md` |
| **Architectural Blueprint** | End-to-end data flow and telemetry metrics layout. | `04_42_LOCAL_MODEL_TOKEN_OPTIMIZATION_AND_DISTILLATION_ARCHITECTURE.md` |
| **From-Scratch Guide** | Writing the telemetry engine and local service line-by-line. | `05_45_LOCAL_MODEL_SERVICE_AND_TELEMETRY_ENGINE_FROM_SCRATCH.md` |

</details>
