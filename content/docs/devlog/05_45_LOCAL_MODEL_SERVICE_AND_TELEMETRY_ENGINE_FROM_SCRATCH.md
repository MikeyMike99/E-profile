[//]: # (DOC_ID: SIRA-ARCH-05_45 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.45: "From Scratch" Step-by-Step Creation Guide: Local Model Service & Token Telemetry Engine

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-1)
## 1. Overview & Beginner Context
This guide provides a step-by-step tutorial for building a complete offline local model execution, dynamic GGUF discovery, and token telemetry pipeline from scratch. You will write two core modules: `local_model_service.py` to dynamically discover local GGUF models and offload inference and distillation tasks to a 4-bit CPU model with full `transcript.jsonl` session persistence, and `token_telemetry.py` to continuously track token burn rates, cache hit efficiency, and cost savings.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-2)
## 2. Environment Preparation & Prerequisites
Before writing code, ensure your environment meets these basic requirements:
1. **The Blank Editor**: Open a fresh, empty file in your code editor or text editor (such as VS Code or Notepad).
2. **Line Endings (LF vs. CRLF)**: Ensure your editor saves files using Unix Line Endings (`LF`). Windows line endings (`CRLF`) can cause string matching issues inside bash subshells.
3. **Execution Permissions**: Grant execution permissions to your python scripts and local binaries using `chmod +x core/local_model_service.py` or run directly with `python3` in Windows execution environments.
4. **Local Binaries**: Ensure `llama-cli` resides at `$HOME/.local/llama-cpp/llama-cli` with `chmod +x` permissions and your quantized model (`qwen2.5-1.5b-instruct-q4_k_m.gguf`) is placed in `$HOME/.local/models/`.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-3)
## 3. Step 1: Write `core/local_model_service.py` Line by Line
Create `core/local_model_service.py` and implement dynamic GGUF model discovery and offline context compression:

```python
import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

from security.central_logger import log_siem_event
from security.local_brain_broker import run_local_qwen, offline_scrub_pii, read_target_documents
from security.swarm_telemetry import SwarmFlowLogger

LLAMA_CLI = os.path.expanduser("~/.local/llama-cpp/llama-cli")
MODEL_PATH = os.path.expanduser("~/.local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf")

def discover_local_models() -> list:
    """Dynamically discovers installed GGUF models in ~/.local/models/ for the UI model selector."""
    models_dir = os.path.expanduser("~/.local/models")
    if not os.path.isdir(models_dir):
        return [{"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"}]
    discovered = []
    for fname in sorted(os.listdir(models_dir)):
        if fname.lower().endswith(".gguf"):
            label = "Local Qwen 2.5 (Offline)" if "qwen2.5" in fname.lower() else f"Local {os.path.splitext(fname)[0]} (Offline)"
            if not any(d["value"] == label for d in discovered):
                discovered.append({"value": label, "text": label})
    return discovered or [{"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"}]

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

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-4)
## 4. Step 2: Write `core/token_telemetry.py` Line by Line
Create `core/token_telemetry.py` to parse token logs incrementally:

```python
import os
import glob
import json
import time
import datetime

class TokenTelemetryEngine:
    def __init__(self, brain_dir=None):
        self._brain_dir = brain_dir or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        self._tz = datetime.timezone(datetime.timedelta(hours=2))
        self._file_cursors = {}
        self._steps = []
        self._sessions = {}
        self._last_refresh = 0.0

    def refresh(self, force=False):
        now = time.time()
        if not force and (now - self._last_refresh) < 1.0:
            return

        pattern = os.path.join(self._brain_dir, "*", ".system_generated", "logs", "transcript.jsonl")
        for fpath in glob.glob(pattern):
            try:
                st = os.stat(fpath)
                mtime, size = st.st_mtime, st.st_size
                prev = self._file_cursors.get(fpath)
                if prev and prev[0] == mtime and prev[1] == size:
                    continue

                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        if '"input_tokens"' in line or '"usage"' in line:
                            d = json.loads(line)
                            self.record_live_step(fpath.split("/")[-4], d.get("usage", d))
                self._file_cursors[fpath] = (mtime, size, size)
            except Exception:
                pass
        self._last_refresh = now
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-5)
## 5. The "Why Order Matters" Sequencing Rationale
1. **Dynamic Discovery Must Feed `/api/models`**: Because the frontend clears `modelSelect.innerHTML` upon fetching `/api/models`, local GGUF models must be merged in `fetch_dynamic_models()` on the backend rather than hardcoded in `index.html`.
2. **PII Scrubbing Must Precede Model Inference**: Passing unsanitized strings directly to any model risks credential leaks in downstream logging channels.
3. **Seek Offset Caching Must Follow Successful Parsing**: Setting byte cursors before completely reading a transcript line risks dropping token events permanently if an error occurs.
4. **Executor Wrapping Must Enclose CLI Calls**: Invoking synchronous CLI processes directly inside async handlers locks the Quart event loop and disrupts WebSocket heartbeats.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-6)
## 6. 10-Second Verification Checklist
- [ ] Run `python3 core/local_model_service.py --query "ping" --max-tokens 5` and verify output in < 6 seconds.
- [ ] Verify `python3 -c "from core.local_model_service import discover_local_models; print(discover_local_models())"` lists `Local Qwen 2.5 (Offline)`.
- [ ] Test context compression with `python3 core/local_model_service.py --mode compress --context "Text..."`.
- [ ] Verify `GET /api/telemetry/tokens` returns valid JSON KPIs.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-7)
## 7. Beginner Coder Q&A

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-8)
### Why do we check `mtime` and `size` before opening the transcript file?
If you have hundreds of sessions, opening and reading every file on disk repeatedly takes hundreds of milliseconds of disk I/O. By checking `st_mtime` and `st_size` first (which takes a microsecond `stat` call), we can skip untouched files completely.

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-9)
### Can I run this script without administrative permissions?
Yes. Both `local_model_service.py` and `token_telemetry.py` execute purely in user space and do not require root or administrator privileges.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_45-SEC-10)
## 8. Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Scope / Chapter |
| :--- | :--- | :--- |
| **Problem Traps** | Memory exhaustion, static UI dropdown traps, and prompt leaks. | `01_46_LOCAL_MODEL_DISTILLATION_AND_TOKEN_BURNOUT_TRAPS.md` |
| **Source Evidence** | Complete source code citations for the architecture. | `02_42_LOCAL_MODEL_AND_TOKEN_TELEMETRY_EVIDENCE.md` |
| **Diagnostic Tests** | Benchmark tests, CPU latency, and telemetry logs. | `03_39_LOCAL_MODEL_AND_TOKEN_TELEMETRY_AUDIT_LOGS.md` |
| **Architecture** | End-to-end architecture and component interactions. | `04_42_LOCAL_MODEL_TOKEN_OPTIMIZATION_AND_DISTILLATION_ARCHITECTURE.md` |

</details>
