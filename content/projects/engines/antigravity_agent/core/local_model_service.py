import argparse
import ast
import asyncio
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

from security.central_logger import log_siem_event
from security.local_brain_broker import offline_scrub_pii, read_target_documents
import security.local_brain_broker as _lbb_module
from security.swarm_telemetry import SwarmFlowLogger

LLAMA_CLI = os.path.expanduser("~/.local/llama-cpp/llama-cli")
MODEL_PATH = os.path.expanduser("~/.local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf")


def resolve_gguf_model_path(model_label: str = "") -> str:
    """Finds the best matching GGUF model path in ~/.local/models/ for the selected label."""
    models_dir = os.path.expanduser("~/.local/models")
    if not os.path.isdir(models_dir):
        return MODEL_PATH
    try:
        fnames = [f for f in os.listdir(models_dir) if f.lower().endswith(".gguf")]
        if not fnames:
            return MODEL_PATH
        m_low = (model_label or "").lower()
        if "llama" in m_low:
            for f in fnames:
                if "llama" in f.lower():
                    return os.path.join(models_dir, f)
        elif "qwen" in m_low:
            for f in fnames:
                if "qwen" in f.lower():
                    return os.path.join(models_dir, f)
        for f in fnames:
            stem = os.path.splitext(f)[0].lower()
            if stem and stem in m_low:
                return os.path.join(models_dir, f)
        if os.path.exists(MODEL_PATH):
            return MODEL_PATH
        return os.path.join(models_dir, fnames[0])
    except Exception:
        return MODEL_PATH


def is_cloud_hosted_environment() -> bool:
    """Detects whether Siraugga is running in a cloud-hosted WSGI environment such as PythonAnywhere."""
    if os.environ.get("SIRAUGGA_CLOUD_ONLY", "").lower() in ("1", "true", "yes"):
        return True
    return (
        "PYTHONANYWHERE_DOMAIN" in os.environ
        or "PYTHONANYWHERE_SITE" in os.environ
        or os.path.exists("/var/www")
    )


def discover_local_models() -> list:
    """Discovers local Ollama models and ~/.local/models/*.gguf weights when running locally; returns [] on PythonAnywhere."""
    if is_cloud_hosted_environment():
        return []

    discovered = []
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            for m in payload.get("models", []):
                m_name = (m.get("name") or "").strip()
                if m_name:
                    val = f"Ollama: {m_name}"
                    if not any(d["value"] == val for d in discovered):
                        discovered.append({"value": val, "text": f"Ollama: {m_name} (Local)"})
    except Exception:
        try:
            import shutil as _shutil
            ollama_bin = _shutil.which("ollama")
            if ollama_bin:
                res = subprocess.run(
                    [ollama_bin, "list"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                if res.returncode == 0 and res.stdout:
                    for idx, line in enumerate(res.stdout.strip().splitlines()):
                        if idx == 0 and "NAME" in line.upper():
                            continue
                        parts = line.split()
                        if parts:
                            m_name = parts[0].strip()
                            val = f"Ollama: {m_name}"
                            if not any(d["value"] == val for d in discovered):
                                discovered.append({"value": val, "text": f"Ollama: {m_name} (Local)"})
        except Exception:
            pass

    models_dir = os.path.expanduser("~/.local/models")
    if os.path.isdir(models_dir):
        try:
            for fname in sorted(os.listdir(models_dir)):
                if not fname.lower().endswith(".gguf"):
                    continue
                low = fname.lower()
                if "qwen2.5" in low:
                    label = "Local Qwen 2.5 (Offline)"
                elif "llama" in low:
                    label = "Local LLaMA (Offline)"
                else:
                    stem = os.path.splitext(fname)[0]
                    label = f"Local {stem} (Offline)"
                if not any(d["value"] == label for d in discovered):
                    discovered.append({"value": label, "text": label})
        except Exception:
            pass

    if os.path.isdir(models_dir) or os.path.exists(MODEL_PATH):
        defaults = [
            {"value": "Local Qwen 2.5 (Offline)", "text": "Local Qwen 2.5 (Offline)"},
            {"value": "Local LLaMA (Offline)", "text": "Local LLaMA (Offline)"},
        ]
        for d in defaults:
            if not any(item["value"] == d["value"] for item in discovered):
                discovered.append(d)

    return discovered


def run_local_ollama_model(
    system_prompt: str,
    user_prompt: str,
    model_label: str = "",
    max_tokens: int = 1400,
    target_label: str = "portal_chat",
) -> str:
    """Executes local inference against the local Ollama daemon."""
    if is_cloud_hosted_environment():
        return "[LOCAL_BRAIN_UNAVAILABLE] Local Ollama models are disabled in cloud-hosted environments."

    raw_name = (model_label or "").strip()
    if raw_name.lower().startswith("ollama:"):
        raw_name = raw_name.split(":", 1)[1].strip()
    if raw_name.endswith("(Local)"):
        raw_name = raw_name[:-len("(Local)")].strip()
    ollama_model = raw_name or "qwen2.5:1.5b"

    try:
        import urllib.request
        body = json.dumps({
            "model": ollama_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.2,
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            out = (data.get("response") or "").strip()
            if out:
                est_tokens = max(1, (len(user_prompt) + len(out)) // 4)
                SwarmFlowLogger.log_tuple(
                    modder_id="LocalPrivacyBroker",
                    agent_id=f"Ollama-{ollama_model}",
                    target_namespace=target_label,
                    model_tier=f"Ollama: {ollama_model}",
                    token_volume=est_tokens,
                )
                return out
    except Exception as e:
        return f"[LOCAL_BRAIN_ERROR] Ollama inference failed for '{ollama_model}': {e}"

    return f"[LOCAL_BRAIN_UNAVAILABLE] Ollama returned an empty response for '{ollama_model}'."


def get_system_resource_profile() -> dict:
    """
    Measures available host memory and logical CPU cores up to 70% capacity.
    Estimates maximum safe single-pass context window and thread bounds.
    """
    mem_total = 8 * 1024**3
    mem_available = 7 * 1024**3
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "MemTotal:":
                    mem_total = int(parts[1]) * 1024
                elif parts[0] == "MemAvailable:":
                    mem_available = int(parts[1]) * 1024
    except Exception:
        pass

    cpu_count = os.cpu_count() or 4
    mem_budget_70 = mem_available * 0.70
    threads_70 = max(1, int(cpu_count * 0.70))

    base_model_ram = 1.15 * (1024**3)
    available_kv_ram = max(0.0, mem_budget_70 - base_model_ram)
    max_tokens_from_ram = max(4096, int(available_kv_ram / 16384))
    dynamic_ctx_ceiling = min(32768, max_tokens_from_ram)

    return {
        "mem_total_bytes": mem_total,
        "mem_available_bytes": mem_available,
        "mem_budget_70_bytes": mem_budget_70,
        "cpu_count": cpu_count,
        "max_threads_70": threads_70,
        "dynamic_ctx_ceiling": dynamic_ctx_ceiling,
    }


def calculate_dynamic_execution_params(prompt_tokens: int, max_output_tokens: int = 900) -> dict:
    """
    Computes dynamic context size (-c), thread throttling, and pacing
    based on proximity to the 70% available resource capacity ceiling.
    """
    profile = get_system_resource_profile()
    ceiling = profile["dynamic_ctx_ceiling"]
    max_threads = profile["max_threads_70"]

    needed = prompt_tokens + max_output_tokens + 256
    buckets = [4096, 6144, 8192, 12288, 16384, 24576, 32768]
    chosen_ctx = 4096
    for b in buckets:
        if b >= needed:
            chosen_ctx = min(b, ceiling)
            break
    else:
        chosen_ctx = ceiling

    ratio = min(1.0, needed / float(max(4096, ceiling)))

    if ratio < 0.35:
        threads = max_threads
        throttle_delay = 0.0
    elif ratio < 0.65:
        threads = max(1, int(max_threads * 0.75))
        throttle_delay = 0.15
    else:
        threads = max(1, int(max_threads * 0.50))
        throttle_delay = 0.35

    should_chunk = (needed > 14000) or (ratio >= 0.85)

    return {
        "ctx_size": chosen_ctx,
        "threads": threads,
        "throttle_delay": throttle_delay,
        "should_chunk": should_chunk,
        "ratio": ratio,
        "profile": profile,
    }


def split_text_into_chunks(text: str, max_chunk_chars: int = 10000, overlap_chars: int = 800) -> list:
    """
    Splits long context text into overlapping semantic blocks along paragraph or sentence boundaries.
    """
    if not text or len(text) <= max_chunk_chars:
        return [text] if text else []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chunk_chars, text_len)
        if end < text_len:
            break_pt = text.rfind("\n\n", start, end)
            if break_pt == -1 or break_pt <= start:
                break_pt = text.rfind("\n", start, end)
            if break_pt == -1 or break_pt <= start:
                break_pt = text.rfind(". ", start, end)
            if break_pt > start:
                end = break_pt + (2 if text[break_pt:break_pt + 2] == "\n\n" else 1)

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(start + 1, end - overlap_chars)

    return chunks


def extract_instruction_and_context(prompt: str, context: str = "") -> tuple:
    """Separates user prompt instructions from attached text or large inline documents."""
    if context and context.strip():
        return prompt.strip(), context.strip()

    if not prompt or len(prompt) < 4000:
        return prompt, ""

    colon_idx = prompt.find(":")
    if 10 < colon_idx < 400 and (len(prompt) - colon_idx) > 2000:
        return prompt[:colon_idx + 1].strip(), prompt[colon_idx + 1:].strip()

    newline_idx = prompt.find("\n\n")
    if 10 < newline_idx < 400 and (len(prompt) - newline_idx) > 2000:
        return prompt[:newline_idx].strip(), prompt[newline_idx + 2:].strip()

    return "Analyze, synthesize, and answer based on this content:", prompt


def run_dynamic_local_qwen(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 900,
    target_label: str = "sensitive_vault",
    retry_depth: int = 0,
    model_path: str = None,
) -> str:
    """
    Invokes local GGUF model via llama-cli on CPU with dynamic 70% resource adaptation.
    Dynamically scales context window size, throttles CPU threads, and auto-recovers from overflow.
    """
    active_model = model_path or resolve_gguf_model_path()
    if not os.path.exists(LLAMA_CLI) or not os.path.exists(active_model):
        log_siem_event(
            level="ERROR",
            message="[FAULT] Local Brain binary or GGUF model missing during dynamic local invocation.",
            module_name="local_model_service",
            logger_name="agent.local_model_service",
        )
        return (
            "[LOCAL_BRAIN_UNAVAILABLE] The local model or llama-cli binary "
            "is missing at ~/.local/llama-cpp/ or ~/.local/models/."
        )

    est_prompt_tokens = max(1, int((len(system_prompt) + len(user_prompt)) / 3.5))
    params = calculate_dynamic_execution_params(est_prompt_tokens, max_output_tokens=max_tokens)
    ctx_size = params["ctx_size"]
    threads = params["threads"]
    throttle_delay = params["throttle_delay"]

    if throttle_delay > 0:
        time.sleep(throttle_delay)

    cmd = [
        LLAMA_CLI,
        "-m",
        active_model,
        "-sys",
        system_prompt,
        "-p",
        user_prompt,
        "-n",
        str(max_tokens),
        "-t",
        str(threads),
        "-tb",
        str(threads),
        "-c",
        str(ctx_size),
        "--temp",
        "0.2",
        "--no-display-prompt",
        "-st",
        "--log-disable",
    ]

    timeout_seconds = max(90, int(ctx_size / 60))

    try:
        res = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=timeout_seconds,
        )
        out = res.stdout or ""
        err = res.stderr or ""
        combined_output = out + "\n" + err

        # Self-healing fallback: catch context size overflow and auto-scale or auto-chunk
        if "exceeds the available context size" in combined_output and retry_depth < 2:
            match = re.search(r"request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)", combined_output)
            req_tok = int(match.group(1)) if match else est_prompt_tokens
            ceiling = params["profile"]["dynamic_ctx_ceiling"]

            if req_tok + max_tokens <= ceiling:
                retry_ctx = min(ceiling, max(ctx_size * 2, req_tok + max_tokens + 512))
                log_siem_event(
                    level="INFO",
                    message=f"[DYNAMIC_RESCALING] Scaling context window from {ctx_size} to {retry_ctx} tokens for '{target_label}'.",
                    module_name="local_model_service",
                    logger_name="agent.local_model_service",
                )
                cmd_retry = list(cmd)
                c_idx = cmd_retry.index("-c")
                cmd_retry[c_idx + 1] = str(retry_ctx)
                res_retry = subprocess.run(
                    cmd_retry,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    start_new_session=True,
                    timeout=max(120, int(retry_ctx / 50)),
                )
                out = res_retry.stdout or ""
            elif len(user_prompt) > 3000:
                log_siem_event(
                    level="INFO",
                    message=f"[DYNAMIC_CHUNKING] Context ({req_tok} tokens) exceeds single pass. Routing to progressive chunking for '{target_label}'.",
                    module_name="local_model_service",
                    logger_name="agent.local_model_service",
                )
                inst, body = extract_instruction_and_context(user_prompt)
                return process_large_context_progressive(
                    instruction=inst,
                    context_text=body,
                    max_output_tokens=max_tokens,
                    context_label=target_label,
                )

        if "... (truncated)\n" in out:
            out = out.split("... (truncated)\n", 1)[-1]
        else:
            prompt_lines = [line for line in user_prompt.strip().splitlines() if line.strip()]
            if prompt_lines and prompt_lines[-1] in out:
                out = out.split(prompt_lines[-1], 1)[-1]
            elif "\n> " in out:
                out = out.split("\n> ", 1)[-1]
                if "\n" in out:
                    out = out.split("\n", 1)[-1]

        if "[ Prompt:" in out:
            out = out.split("[ Prompt:", 1)[0]
        elif "Exiting..." in out:
            out = out.split("Exiting...", 1)[0]

        out = out.strip()
        for marker in ("<|im_end|>", "<|endoftext|>", "[end of text]"):
            if out.endswith(marker):
                out = out[:-len(marker)].strip()

        est_tokens = max(1, (len(user_prompt) + len(out)) // 4)
        SwarmFlowLogger.log_tuple(
            modder_id="LocalPrivacyBroker",
            agent_id="Qwen2.5-1.5B-CPU",
            target_namespace=target_label,
            model_tier="qwen2.5-1.5b-instruct-q4_k_m (Local Dynamic CPU)",
            token_volume=est_tokens,
        )
        log_siem_event(
            level="INFO",
            message=f"[AGENTIC] Local Brain completed dynamic inference on '{target_label}' (~{est_tokens} tokens, ctx={ctx_size}, threads={threads}).",
            module_name="local_model_service",
            logger_name="agent.local_model_service",
        )
        return out
    except subprocess.TimeoutExpired:
        log_siem_event(
            level="ERROR",
            message=f"[FAULT] Local Brain timed out after {timeout_seconds}s while processing '{target_label}'.",
            module_name="local_model_service",
            logger_name="agent.local_model_service",
        )
        return "[LOCAL_BRAIN_TIMEOUT] Local model timed out while processing the prompt."
    except Exception as e:
        log_siem_event(
            level="ERROR",
            message=f"[FAULT] Local Brain execution error on '{target_label}': {str(e)}",
            module_name="local_model_service",
            logger_name="agent.local_model_service",
        )
        return f"[LOCAL_BRAIN_ERROR] {str(e)}"


def process_large_context_progressive(
    instruction: str,
    context_text: str,
    max_output_tokens: int = 900,
    context_label: str = "chunked_query",
) -> str:
    """
    Progressively processes large contexts across smaller chunks and synthesizes findings.
    Slows down between chunks to protect local resources from spike saturation.
    """
    chunks = split_text_into_chunks(context_text, max_chunk_chars=10000, overlap_chars=800)
    if not chunks:
        return ""

    if len(chunks) == 1:
        clean_chunk = offline_scrub_pii(chunks[0], stage="single_chunk")
        user_prompt = f"CONTEXT:\n{clean_chunk}\n\nINSTRUCTION:\n{instruction}"
        system_prompt = (
            "You are the DevCore Local AI Assistant running offline on the user's machine (Qwen2.5-1.5B). "
            "Provide direct, technically accurate, concise answers without filler or pleasantries."
        )
        return run_dynamic_local_qwen(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_output_tokens,
            target_label=context_label,
        )

    chunk_distillations = []
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks):
        clean_chunk = offline_scrub_pii(chunk, stage=f"chunk_{idx}")
        sys_p = (
            "You are an analytical distillation sub-engine running locally. "
            "Extract all facts, key points, data structures, and rules from this document section "
            "that are relevant to fulfilling the user's instruction. Be factual, dense, and concise."
        )
        u_p = (
            f"DOCUMENT SECTION {idx + 1} OF {total_chunks}:\n{clean_chunk}\n\n"
            f"USER INSTRUCTION: {instruction}\n\n"
            "Key points and data from this section relevant to the instruction:"
        )

        distilled = run_dynamic_local_qwen(
            system_prompt=sys_p,
            user_prompt=u_p,
            max_tokens=450,
            target_label=f"{context_label}:chunk_{idx + 1}_of_{total_chunks}",
        )
        if distilled and not distilled.startswith("[LOCAL_BRAIN_"):
            chunk_distillations.append(f"--- Section {idx + 1} Findings ---\n{distilled}")

        time.sleep(0.2)

    combined_findings = "\n\n".join(chunk_distillations) if chunk_distillations else context_text[:8000]

    final_sys_p = (
        "You are the DevCore Local AI Assistant running offline on the user's machine (Qwen2.5-1.5B). "
        "Synthesize all analyzed findings from the document sections to provide a complete, well-structured, "
        "and accurate response to the user's instruction."
    )
    final_u_p = (
        f"ANALYZED FINDINGS ACROSS ALL SECTIONS:\n{combined_findings}\n\n"
        f"USER INSTRUCTION:\n{instruction}\n\n"
        "Provide your thorough, synthesized response:"
    )

    return run_dynamic_local_qwen(
        system_prompt=final_sys_p,
        user_prompt=final_u_p,
        max_tokens=max_output_tokens,
        target_label=f"{context_label}:synthesis",
    )


def compress_context(raw_text: str, target_tokens: int = 400, context_label: str = "general") -> str:
    """Compresses raw files or logs into a dense semantic summary with progressive chunking support."""
    if not raw_text or not raw_text.strip():
        return ""

    if len(raw_text) > 14000:
        chunks = split_text_into_chunks(raw_text, max_chunk_chars=10000, overlap_chars=600)
        chunk_digests = []
        for idx, chunk in enumerate(chunks):
            pre_scrubbed = offline_scrub_pii(chunk, stage=f"compress_chunk_{idx}")
            sys_p = "You are an ultra-concise technical distillation engine. Extract core architecture and critical data."
            u_p = f"RAW CONTEXT SECTION {idx + 1} OF {len(chunks)}:\n{pre_scrubbed}\n\nProduce an executive summary under {max(60, target_tokens // len(chunks) + 40)} words."
            digest = run_dynamic_local_qwen(
                system_prompt=sys_p,
                user_prompt=u_p,
                max_tokens=max(80, target_tokens // len(chunks) + 60),
                target_label=f"compress:{context_label}_part_{idx + 1}",
            )
            if digest and not digest.startswith("[LOCAL_BRAIN_"):
                chunk_digests.append(digest)
            time.sleep(0.15)
        combined_text = "\n\n".join(chunk_digests)
        final_u_p = f"CONSOLIDATED CHUNK DIGESTS:\n{combined_text}\n\nSynthesize into a unified final executive digest under {target_tokens} words."
        final_digest = run_dynamic_local_qwen(
            system_prompt="You are an ultra-concise technical distillation engine. Produce the final unified summary.",
            user_prompt=final_u_p,
            max_tokens=target_tokens + 100,
            target_label=f"compress:{context_label}_final",
        )
        return offline_scrub_pii(final_digest, stage="compress_output")

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
    digest = run_dynamic_local_qwen(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=target_tokens + 100,
        target_label=f"compress:{context_label}",
    )
    return offline_scrub_pii(digest, stage="compress_output")


def query_local_model(
    prompt: str,
    context: str = "",
    max_tokens: int = 800,
    mode: str = "query",
    context_label: str = "direct_query",
) -> str:
    """Executes a local inference task with zero cloud token consumption and dynamic chunking."""
    if not prompt and not context:
        return ""

    if mode == "compress":
        text_to_compress = context or prompt
        return compress_context(text_to_compress, target_tokens=max_tokens, context_label=context_label)

    inst, body = extract_instruction_and_context(prompt, context)
    if body and (len(body) > 12000 or (len(body) + len(inst)) > 15000):
        return process_large_context_progressive(
            instruction=inst,
            context_text=body,
            max_output_tokens=max_tokens,
            context_label=f"{mode}:{context_label}",
        )

    if context:
        clean_context = offline_scrub_pii(context, stage="query_context")
        user_prompt = f"CONTEXT:\n{clean_context}\n\nINSTRUCTION:\n{prompt}"
    else:
        user_prompt = prompt

    system_prompt = (
        "You are the DevCore Local AI Assistant running offline on the user's machine (Qwen2.5-1.5B). "
        "Provide direct, technically accurate, concise answers without filler or pleasantries."
    )
    response = run_dynamic_local_qwen(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        target_label=f"{mode}:{context_label}",
    )
    return offline_scrub_pii(response, stage="query_output")


def generate_local_exam(target_path_or_content: str, count: int = 5, query: str = None) -> dict:
    """Generates schema-compliant exam questions using the local CPU model with multi-chunk support."""
    if os.path.exists(target_path_or_content):
        files, raw_text = read_target_documents(target_path_or_content)
        content_label = os.path.basename(target_path_or_content)
    else:
        files = ["inline_content"]
        raw_text = target_path_or_content
        content_label = "inline"

    if not raw_text.strip():
        return {
            "status": "EMPTY",
            "error": "No content available to generate exam questions.",
            "questions": [],
        }

    if len(raw_text) > 16000:
        chunks = split_text_into_chunks(raw_text, max_chunk_chars=12000, overlap_chars=600)
        all_questions = []
        base_per_chunk = max(1, count // len(chunks))
        remainder = count % len(chunks)

        for idx, chunk in enumerate(chunks):
            chunk_q_count = base_per_chunk + (1 if idx < remainder else 0)
            if chunk_q_count <= 0:
                continue
            pre_scrubbed = offline_scrub_pii(chunk, stage=f"exam_chunk_{idx}")
            sys_p = (
                "You are the DevCore Local Exam Broker AI. Read the source material and generate "
                "educational exam questions in strict JSON format. Output ONLY valid JSON."
            )
            extra_instructions = f"\nAdditional instructions: {query}\n" if query else ""
            u_p = (
                f"SOURCE MATERIAL (PART {idx + 1} OF {len(chunks)}):\n{pre_scrubbed}\n"
                f"{extra_instructions}\n"
                f"Generate exactly {chunk_q_count} exam questions based on this part. "
                "Output ONLY a valid JSON object matching this schema:\n"
                "{\n"
                '  "questions": [\n'
                "    {\n"
                '      "type": "multiple_choice",\n'
                '      "text": "Question text here?",\n'
                '      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
                '      "correct_index": 0,\n'
                '      "explanation": "Clear explanation."\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "- Return ONLY the raw JSON object without markdown code fences."
            )
            reply = run_dynamic_local_qwen(
                system_prompt=sys_p,
                user_prompt=u_p,
                max_tokens=1000,
                target_label=f"exam:{content_label}_chunk_{idx + 1}",
            )
            safe_reply = offline_scrub_pii(reply, stage=f"exam_output_{idx}")
            json_match = re.search(r"\{[\s\S]*\}", safe_reply)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    qs = parsed.get("questions", [])
                    if isinstance(qs, list):
                        all_questions.extend(qs)
                except Exception:
                    pass
            time.sleep(0.15)

        if all_questions:
            return {
                "status": "OK",
                "target": content_label,
                "files": files,
                "model": "qwen2.5-1.5b-instruct-q4_k_m (Local CPU)",
                "payload": {"questions": all_questions[:count]},
            }

    pre_scrubbed = offline_scrub_pii(raw_text, stage="exam_input")
    system_prompt = (
        "You are the DevCore Local Exam Broker AI. Read the source material and generate "
        "educational exam questions in strict JSON format. Never include raw secrets or personal PII. "
        "Output ONLY valid JSON."
    )
    extra_instructions = f"\nAdditional instructions: {query}\n" if query else ""
    user_prompt = (
        f"SOURCE MATERIAL:\n{pre_scrubbed}\n"
        f"{extra_instructions}\n"
        f"Generate exactly {count} exam questions based on the concepts in the source material. "
        "Output ONLY a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "type": "multiple_choice",\n'
        '      "text": "Question text here?",\n'
        '      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
        '      "correct_index": 0,\n'
        '      "explanation": "Clear explanation of why Option A is correct."\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        '- Use "text" (NEVER "question").\n'
        '- For "multiple_choice", use integer "correct_index" (0-based).\n'
        "- Return ONLY the raw JSON object without markdown code fences."
    )

    reply = run_dynamic_local_qwen(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1400,
        target_label=f"exam:{content_label}",
    )
    safe_reply = offline_scrub_pii(reply, stage="exam_output")

    json_match = re.search(r"\{[\s\S]*\}", safe_reply)
    parsed_questions = None
    if json_match:
        try:
            parsed_questions = json.loads(json_match.group(0))
        except Exception:
            parsed_questions = None

    return {
        "status": "OK",
        "target": content_label,
        "files": files,
        "model": "qwen2.5-1.5b-instruct-q4_k_m (Local CPU)",
        "payload": parsed_questions if parsed_questions else safe_reply,
    }


def local_read_file(workspace_dir: str, rel_path: str, user: dict = None, sec_mgr = None) -> tuple:
    """Reads a workspace file safely, returning (success: bool, content: str)."""
    if not rel_path or not rel_path.strip():
        return False, "File path cannot be empty."
    clean_path = rel_path.strip().strip("'\"`").lstrip("/\\")
    if clean_path.startswith("..") or "/../" in clean_path or "\\..\\" in clean_path:
        return False, f"Access Denied: Path traversal forbidden ({clean_path})"

    if sec_mgr and hasattr(sec_mgr, "read_file_content"):
        try:
            res = sec_mgr.read_file_content(workspace_dir, clean_path, user=user)
            if isinstance(res, dict) and "content" in res:
                return True, res["content"]
        except Exception:
            pass

    is_admin = False
    if sec_mgr and hasattr(sec_mgr, "is_admin_user"):
        is_admin = sec_mgr.is_admin_user(user)
    elif user and user.get("role") == "admin":
        is_admin = True

    full_path = os.path.realpath(os.path.join(workspace_dir, clean_path))
    real_base = os.path.realpath(workspace_dir)
    if not os.path.exists(full_path) and is_admin:
        alt_path = os.path.realpath(os.path.join(DEVCORE_ROOT, clean_path))
        if os.path.exists(alt_path):
            full_path = alt_path

    if not full_path.startswith(real_base):
        if is_admin and (full_path == os.path.realpath(DEVCORE_ROOT) or full_path.startswith(os.path.realpath(DEVCORE_ROOT) + os.sep)):
            pass
        else:
            return False, f"Access Denied: Path escapes workspace boundary ({clean_path})"

    if not os.path.isfile(full_path):
        return False, f"File not found: {clean_path}"

    try:
        if os.path.getsize(full_path) > 1024 * 1024:
            return False, f"File exceeds maximum viewable size (1 MB): {clean_path}"
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return True, content
    except Exception as e:
        return False, f"Error reading file {clean_path}: {str(e)}"

def local_read_symbol(workspace_dir: str, target: str, symbol: str = None, user: dict = None, sec_mgr = None) -> tuple:
    """
    Surgically reads a specific AST symbol (function, method, class) or Markdown section,
    returning (success: bool, snippet: str, metadata: dict).
    Conserves tokens and avoids loading massive files into the small local model context.
    """
    if not target or not target.strip():
        return False, "Target file or symbol key cannot be empty.", {}

    raw_target = target.strip().strip("'\"`")
    if "::" in raw_target:
        parts = raw_target.split("::", 1)
        raw_target = parts[0]
        if not symbol:
            symbol = parts[1]

    full_path = None
    phonebook_entry = None
    try:
        from security.raugus_resolver import RaugusResolver
        resolver = RaugusResolver()
        tier = 5 if (user and user.get("role") == "admin") else (3 if (user and user.get("role") == "gamedev") else 1)
        
        lookup_key = f"{raw_target}::{symbol}" if symbol else raw_target
        if lookup_key in resolver.phonebook:
            phonebook_entry = resolver.phonebook[lookup_key]
            full_path = phonebook_entry.get("real_path")
        elif raw_target in resolver.phonebook:
            phonebook_entry = resolver.phonebook[raw_target]
            full_path = phonebook_entry.get("real_path")
            
        if not full_path and symbol:
            block = resolver.get_block_by_tag(symbol, user_tier=tier)
            if block and block.get("real_path"):
                phonebook_entry = block
                full_path = block["real_path"]
    except Exception:
        pass

    if not full_path:
        clean_path = raw_target.lstrip("/\\")
        if clean_path.startswith("..") or "/../" in clean_path or "\\..\\" in clean_path:
            return False, f"Access Denied: Path traversal forbidden ({clean_path})", {}
        full_path = os.path.realpath(os.path.join(workspace_dir, clean_path))
        real_base = os.path.realpath(workspace_dir)
        if not full_path.startswith(real_base) and not full_path.startswith(os.path.abspath(DEVCORE_ROOT)):
            return False, f"Access Denied: Path escapes boundary ({clean_path})", {}

    if not os.path.isfile(full_path):
        return False, f"File not found: {raw_target}", {}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return False, f"Error reading file {raw_target}: {str(e)}", {}

    if not symbol:
        content = "".join(lines)
        if len(content) > 1024 * 1024:
            return False, f"File exceeds maximum viewable size: {raw_target}", {}
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        return True, content, {"line_count": len(lines), "content_hash": file_hash}

    s_line = None
    e_line = None
    kind = "symbol"
    content_hash = ""

    if phonebook_entry and phonebook_entry.get("start_line") and phonebook_entry.get("end_line"):
        s_line = int(phonebook_entry["start_line"])
        e_line = int(phonebook_entry["end_line"])
        kind = phonebook_entry.get("type", "symbol")
        content_hash = phonebook_entry.get("content_hash", "")

    if not s_line or not e_line:
        if full_path.endswith(".py"):
            try:
                tree = ast.parse("".join(lines))
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name == symbol:
                            s_line = node.lineno
                            e_line = getattr(node, "end_lineno", node.lineno)
                            kind = "function" if isinstance(node, ast.FunctionDef) else ("async_function" if isinstance(node, ast.AsyncFunctionDef) else "class")
                            break
                        if isinstance(node, ast.ClassDef):
                            for child in node.body:
                                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == symbol:
                                    s_line = child.lineno
                                    e_line = getattr(child, "end_lineno", child.lineno)
                                    kind = "method"
                                    break
                    elif isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name) and t.id == symbol:
                                s_line = node.lineno
                                e_line = getattr(node, "end_lineno", node.lineno)
                                kind = "variable"
                                break
            except Exception:
                pass
        elif full_path.endswith((".md", ".plan")):
            try:
                from security.raugus_sync import extract_markdown_sections
                sec_dict = extract_markdown_sections(full_path)
                for sec_key, sec_info in sec_dict.items():
                    if sec_key == symbol or sec_info.get("symbol_name") == symbol:
                        s_line = sec_info["start_line"]
                        e_line = sec_info["end_line"]
                        kind = "section"
                        content_hash = sec_info.get("content_hash", "")
                        break
            except Exception:
                pass

    if not s_line or not e_line:
        return False, f"Symbol or section '{symbol}' was not found in '{os.path.basename(full_path)}'.", {}

    snippet_lines = lines[max(0, s_line - 1): e_line]
    snippet = "".join(snippet_lines)
    if not content_hash:
        content_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:12]

    meta = {
        "symbol": symbol,
        "kind": kind,
        "start_line": s_line,
        "end_line": e_line,
        "line_count": max(1, e_line - s_line + 1),
        "content_hash": content_hash,
        "file": os.path.basename(full_path),
    }
    return True, snippet, meta


def local_write_symbol(workspace_dir: str, target: str, symbol: str, new_code: str, user: dict = None, sec_mgr = None) -> tuple:
    """
    Surgically replaces a specific AST symbol (function, method) in a target file,
    validates syntax, stages engine patches, and updates Raugus hashes.
    """
    if not target or not target.strip():
        return False, "Target file cannot be empty."
    if not symbol or not symbol.strip():
        return False, "Target symbol cannot be empty."

    raw_target = target.strip().strip("'\"`")
    if "::" in raw_target:
        parts = raw_target.split("::", 1)
        raw_target = parts[0]
        if not symbol:
            symbol = parts[1]

    full_path = None
    try:
        from security.raugus_resolver import RaugusResolver
        resolver = RaugusResolver()
        if raw_target in resolver.phonebook:
            full_path = resolver.phonebook[raw_target].get("real_path")
    except Exception:
        pass

    if not full_path:
        clean_path = raw_target.lstrip("/\\")
        if clean_path.startswith("..") or "/../" in clean_path or "\\..\\" in clean_path:
            return False, f"Access Denied: Path traversal forbidden ({clean_path})"
        full_path = os.path.realpath(os.path.join(workspace_dir, clean_path))

    if not os.path.isfile(full_path):
        return False, f"Target file not found: {raw_target}"

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            orig_lines = f.readlines()
        orig_source = "".join(orig_lines)
    except Exception as e:
        return False, f"Error reading file {raw_target}: {e}"

    s_line, e_line = None, None
    if full_path.endswith(".py"):
        try:
            tree = ast.parse(orig_source)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == symbol:
                        s_line = node.lineno
                        e_line = getattr(node, "end_lineno", node.lineno)
                        break
                    if isinstance(node, ast.ClassDef):
                        for child in node.body:
                            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == symbol:
                                s_line = child.lineno
                                e_line = getattr(child, "end_lineno", child.lineno)
                                break
        except SyntaxError as se:
            return False, f"Target file has syntax errors: {se}"

    clean_replacement = new_code if new_code.endswith("\n") else (new_code + "\n")
    if s_line and e_line:
        new_lines = orig_lines[: s_line - 1] + [clean_replacement] + orig_lines[e_line:]
    else:
        new_lines = orig_lines + ["\n" + clean_replacement]

    new_source = "".join(new_lines)
    if full_path.endswith(".py"):
        try:
            ast.parse(new_source)
        except SyntaxError as se:
            return False, f"Syntax validation failed for modified symbol '{symbol}' (line {se.lineno}): {se.msg}"

    is_engine = "/DevCore/core/" in full_path or "/DevCore/agents/" in full_path or "/DevCore/security/" in full_path
    if is_engine and "/core/patches/" not in full_path:
        basename = os.path.basename(full_path)
        patch_dir = os.path.join(DEVCORE_ROOT, "core", "patches")
        os.makedirs(patch_dir, exist_ok=True)
        staged_file = os.path.join(patch_dir, basename)
        with open(staged_file, "w", encoding="utf-8") as pf:
            pf.write(new_source)
        try:
            from core.bootstrap_gateway import run_preflight_checks
            report = run_preflight_checks(base_dir=DEVCORE_ROOT, spawn_agent=False, quiet=True)
            if not report.get("success") or basename not in report.get("promoted_patches", []):
                return False, f"Hot-patch verification failed for staged update to '{basename}'."
        except Exception as e:
            return False, f"Hot-patch execution error: {e}"
    else:
        try:
            with open(full_path, "w", encoding="utf-8") as wf:
                wf.write(new_source)
        except Exception as e:
            return False, f"Error saving file {raw_target}: {e}"

    try:
        from security.raugus_sync import sync_path
        sync_path(full_path)
    except Exception:
        pass

    return True, f"Successfully updated symbol '{symbol}' in '{os.path.basename(full_path)}'."
def local_write_file(workspace_dir: str, rel_path: str, content: str, user: dict = None, sec_mgr = None) -> tuple:
    """Writes content to a workspace file safely, returning (success: bool, message: str)."""
    if not rel_path or not rel_path.strip():
        return False, "File path cannot be empty."
    clean_path = rel_path.strip().strip("'\"`").lstrip("/\\")
    if clean_path.startswith("..") or "/../" in clean_path or "\\..\\" in clean_path:
        return False, f"Access Denied: Path traversal forbidden ({clean_path})"

    if sec_mgr and hasattr(sec_mgr, "write_file_content"):
        try:
            res = sec_mgr.write_file_content(workspace_dir, clean_path, content, user=user)
            if isinstance(res, dict) and res.get("success"):
                return True, f"Successfully wrote {len(content)} bytes to {clean_path}."
        except Exception:
            pass

    is_admin = False
    if sec_mgr and hasattr(sec_mgr, "is_admin_user"):
        is_admin = sec_mgr.is_admin_user(user)
    elif user and user.get("role") == "admin":
        is_admin = True

    full_path = os.path.realpath(os.path.join(workspace_dir, clean_path))
    real_base = os.path.realpath(workspace_dir)
    if not os.path.exists(full_path) and is_admin:
        alt_path = os.path.realpath(os.path.join(DEVCORE_ROOT, clean_path))
        if os.path.exists(alt_path):
            full_path = alt_path

    if not full_path.startswith(real_base):
        if is_admin and (full_path == os.path.realpath(DEVCORE_ROOT) or full_path.startswith(os.path.realpath(DEVCORE_ROOT) + os.sep)):
            pass
        else:
            return False, f"Access Denied: Path escapes workspace boundary ({clean_path})"

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"Successfully wrote {len(content)} bytes to {clean_path}."
    except Exception as e:
        return False, f"Error writing file {clean_path}: {str(e)}"


def local_search_files(workspace_dir: str, query: str = "", user: dict = None, sec_mgr = None, max_results: int = 50) -> tuple:
    """Safely searches workspace files recursively matching a filename pattern or query substring. Returns (success: bool, results_str: str)."""
    if not workspace_dir or not os.path.isdir(workspace_dir):
        return False, "Workspace directory does not exist."

    clean_query = (query or "").strip().strip("'\"`")
    if not clean_query:
        clean_query = "*"

    query_map = {
        "python": "*.py",
        "python files": "*.py",
        "python scripts": "*.py",
        "all python files": "*.py",
        "json": "*.json",
        "json files": "*.json",
        "all json files": "*.json",
        "markdown": "*.md",
        "markdown files": "*.md",
        "md files": "*.md",
        "javascript": "*.js",
        "js files": "*.js",
        "html": "*.html",
        "html files": "*.html",
        "css": "*.css",
        "css files": "*.css",
    }
    pattern = query_map.get(clean_query.lower(), clean_query)

    is_admin = False
    if sec_mgr and hasattr(sec_mgr, "is_admin_user"):
        is_admin = sec_mgr.is_admin_user(user)
    elif user and user.get("role") == "admin":
        is_admin = True

    real_base = os.path.realpath(workspace_dir)

    forbidden_names = {
        ".git", "venv", ".venv", "node_modules", "__pycache__",
        ".gemini", ".pytest_cache", ".coverage", ".mypy_cache",
        ".DS_Store", "desktop.ini", ".849c9593-d756-4e56-8d6e-42412f2a707b",
    }
    if sec_mgr and hasattr(sec_mgr, "FORBIDDEN_NAMES"):
        forbidden_names.update(sec_mgr.FORBIDDEN_NAMES)

    matched_files = []
    is_glob = any(char in pattern for char in ("*", "?", "["))
    low_pat = pattern.lower()

    for root, dirs, files in os.walk(real_base):
        dirs[:] = [
            d for d in dirs
            if d not in forbidden_names
            and not d.startswith(".")
        ]

        for fname in sorted(files):
            if fname.startswith(".") or fname in forbidden_names:
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, real_base).replace("\\", "/")

            if sec_mgr and hasattr(sec_mgr, "classify_file"):
                try:
                    tier = sec_mgr.classify_file(rel_path)
                    if tier == sec_mgr.TIER_FORBIDDEN:
                        continue
                    if not is_admin and tier in (sec_mgr.TIER_CORE_ENGINE, sec_mgr.TIER_ADMIN_LOG):
                        continue
                except Exception:
                    pass

            matched = False
            if is_glob:
                if fnmatch.fnmatch(fname.lower(), low_pat) or fnmatch.fnmatch(rel_path.lower(), low_pat):
                    matched = True
            else:
                if low_pat in fname.lower() or low_pat in rel_path.lower():
                    matched = True

            if matched:
                try:
                    sz = os.path.getsize(full_path)
                    if sz < 1024:
                        sz_str = f"{sz} B"
                    elif sz < 1024 * 1024:
                        sz_str = f"{sz / 1024:.1f} KB"
                    else:
                        sz_str = f"{sz / (1024 * 1024):.1f} MB"
                    matched_files.append((rel_path, sz_str))
                except Exception:
                    matched_files.append((rel_path, "unknown size"))

            if len(matched_files) >= max_results:
                break
        if len(matched_files) >= max_results:
            break

    if not matched_files:
        return True, f"No files found matching '{clean_query}' in workspace."

    lines = [f"Found {len(matched_files)} file(s) matching '{clean_query}':"]
    for rpath, sz_str in matched_files:
        lines.append(f"- {rpath} ({sz_str})")

    if len(matched_files) >= max_results:
        lines.append(f"... [Truncated at {max_results} results]")

    return True, "\n".join(lines)


def local_list_directory(workspace_dir: str, rel_path: str = "", user: dict = None, sec_mgr = None, max_items: int = 50) -> tuple:
    """Lists workspace directory contents safely, returning (success: bool, listing_str: str)."""
    clean_path = (rel_path or "").strip().strip("'\"`").lstrip("/\\")
    if clean_path in (".", "./", ".\\"):
        clean_path = ""

    if clean_path.startswith("..") or "/../" in clean_path or "\\..\\" in clean_path:
        return False, f"Access Denied: Path traversal forbidden ({clean_path})"

    is_admin = False
    if sec_mgr and hasattr(sec_mgr, "is_admin_user"):
        is_admin = sec_mgr.is_admin_user(user)
    elif user and user.get("role") == "admin":
        is_admin = True

    real_base = os.path.realpath(workspace_dir)
    target_dir = os.path.realpath(os.path.join(workspace_dir, clean_path)) if clean_path else real_base
    if not os.path.exists(target_dir) and is_admin and clean_path:
        alt_dir = os.path.realpath(os.path.join(DEVCORE_ROOT, clean_path))
        if os.path.exists(alt_dir):
            target_dir = alt_dir
            real_base = os.path.realpath(DEVCORE_ROOT)

    if not (target_dir == real_base or target_dir.startswith(real_base + os.sep)):
        if is_admin and (target_dir == os.path.realpath(DEVCORE_ROOT) or target_dir.startswith(os.path.realpath(DEVCORE_ROOT) + os.sep)):
            pass
        else:
            return False, f"Access Denied: Path escapes workspace boundary ({clean_path})"

    if not os.path.exists(target_dir):
        return False, f"Directory not found: {clean_path or '.'}"
    if not os.path.isdir(target_dir):
        return False, f"Path is not a directory: {clean_path or '.'}"

    forbidden_names = {
        ".git", "venv", ".venv", "node_modules", "__pycache__",
        ".gemini", ".pytest_cache", ".coverage", ".mypy_cache",
        ".DS_Store", "desktop.ini", ".849c9593-d756-4e56-8d6e-42412f2a707b",
    }
    if sec_mgr and hasattr(sec_mgr, "FORBIDDEN_NAMES"):
        forbidden_names.update(sec_mgr.FORBIDDEN_NAMES)

    is_admin = False
    if sec_mgr and hasattr(sec_mgr, "is_admin_user"):
        is_admin = sec_mgr.is_admin_user(user)
    elif user and user.get("role") == "admin":
        is_admin = True

    try:
        raw_entries = sorted(os.listdir(target_dir))
    except Exception as e:
        return False, f"Error reading directory {clean_path or '.'}: {str(e)}"

    dir_entries = []
    file_entries = []

    for name in raw_entries:
        if name in forbidden_names or name.startswith("."):
            continue

        item_full = os.path.join(target_dir, name)
        item_rel = os.path.relpath(item_full, real_base).replace("\\", "/")

        if sec_mgr and hasattr(sec_mgr, "classify_file"):
            try:
                tier = sec_mgr.classify_file(item_rel)
                if tier == sec_mgr.TIER_FORBIDDEN:
                    continue
                if not is_admin and tier in (sec_mgr.TIER_CORE_ENGINE, sec_mgr.TIER_ADMIN_LOG):
                    continue
            except Exception:
                pass

        try:
            if os.path.isdir(item_full):
                dir_entries.append(f"📁 {name}/")
            else:
                sz = os.path.getsize(item_full)
                if sz < 1024:
                    sz_str = f"{sz} B"
                elif sz < 1024 * 1024:
                    sz_str = f"{sz / 1024:.1f} KB"
                else:
                    sz_str = f"{sz / (1024 * 1024):.1f} MB"
                file_entries.append(f"📄 {name} ({sz_str})")
        except Exception:
            continue

    total_count = len(dir_entries) + len(file_entries)
    combined = dir_entries + file_entries
    truncated_msg = ""
    if len(combined) > max_items:
        combined = combined[:max_items]
        truncated_msg = f"\n... [{total_count - max_items} additional items truncated]"

    display_path = clean_path if clean_path else "."
    result = f"Directory: {display_path} ({total_count} items)\n"
    if combined:
        result += "\n".join(combined) + truncated_msg
    else:
        result += "(empty directory)"

    return True, result

def _get_transcript_path(brain_dir: str, conv_id: str) -> str:
    p1 = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(brain_dir, conv_id, "transcript.jsonl")
    if os.path.exists(p2):
        return p2
    os.makedirs(os.path.dirname(p1), exist_ok=True)
    return p1


def _clean_transcript_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<SYSTEM_MESSAGE>[\s\S]*?</SYSTEM_MESSAGE>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<SESSION_CONTINUATION_CONTEXT>[\s\S]*?</SESSION_CONTINUATION_CONTEXT>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<USER_SETTINGS_CHANGE>[\s\S]*?</USER_SETTINGS_CHANGE>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<MID_TASK_STEERING_UPDATE>[\s\S]*?</MID_TASK_STEERING_UPDATE>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<CONTEXT_SUMMARY>[\s\S]*?</CONTEXT_SUMMARY>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?USER_REQUEST>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[(?:STEER_NOW|QUEUE_NEXT)\]', '', text, flags=re.IGNORECASE)
    return text.strip()


def _load_prior_conversation_turns(brain_dir: str, conv_id: str, max_turns: int = 12) -> tuple:
    transcript_path = _get_transcript_path(brain_dir, conv_id)
    step_idx = 0
    turns = []
    if os.path.exists(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    step_idx += 1
                    try:
                        d = json.loads(line)
                        dtype = d.get("type")
                        content = d.get("content") or ""
                        if dtype == "USER_INPUT":
                            cleaned = _clean_transcript_text(content)
                            if cleaned:
                                turns.append({"role": "user", "content": cleaned[:1200]})
                        elif dtype == "PLANNER_RESPONSE":
                            cleaned = (content or "").strip()
                            if cleaned:
                                turns.append({"role": "assistant", "content": cleaned[:1500]})
                    except Exception:
                        pass
        except Exception:
            pass
    return step_idx, turns[-max_turns:]


def _load_and_append_user_turn(brain_dir: str, conv_id: str, clean_prompt: str) -> tuple:
    """Loads recent conversation context and appends the new USER_INPUT step in standard AGY format."""
    transcript_path = _get_transcript_path(brain_dir, conv_id)
    step_idx, prior_turns = _load_prior_conversation_turns(brain_dir, conv_id, max_turns=12)

    user_entry = {
        "step_index": step_idx,
        "source": "USER_EXPLICIT",
        "type": "USER_INPUT",
        "status": "DONE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "content": f"<USER_REQUEST>\n{clean_prompt}\n</USER_REQUEST>",
    }
    try:
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(user_entry) + "\n")
    except Exception:
        pass

    return transcript_path, step_idx + 1, prior_turns


def _append_planner_response(transcript_path: str, step_idx: int, response: str, usage: dict):
    """Appends the local model PLANNER_RESPONSE entry to transcript.jsonl for persistent session history."""
    resp_entry = {
        "step_index": step_idx,
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "status": "DONE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": 0,
        "content": response,
        "usage": usage,
    }
    try:
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(resp_entry) + "\n")
    except Exception:
        pass



LOCAL_AGENT_SYSTEM_PROMPT = (
    "You are the DevCore Local AI Assistant running offline on the user's machine with direct filesystem tools.\n"
    "CRITICAL RULES:\n"
    "1. You HAVE direct access to search files, browse directories, read files, and write files in the active workspace.\n"
    "2. NEVER apologize, refuse, or claim that you lack filesystem access.\n"
    "3. When the user asks to inspect, search, list, read, or write files or directories, immediately emit a tool call.\n"
    "4. For targeted code inspection, prefer read_symbol over read_file to keep context small and fast.\n"
    "AVAILABLE TOOLS:\n"
    "- Search files: `<tool_call>{\"action\": \"search_files\", \"query\": \"*.py\"}</tool_call>` (or `[SEARCH_FILES: pattern]`)\n"
    "- Browse directory: `<tool_call>{\"action\": \"list_dir\", \"path\": \".\"}</tool_call>` (or `[LIST_DIR: path]`)\n"
    "- Read file: `<tool_call>{\"action\": \"read_file\", \"path\": \"filename.ext\"}</tool_call>` (or `[READ_FILE: path]`)\n"
    "- Read symbol/block: `<tool_call>{\"action\": \"read_symbol\", \"path\": \"file.py\", \"symbol\": \"func_name\"}</tool_call>` (or `[READ_SYMBOL: file.py::func_name]`)\n"
    "- Search symbols: `<tool_call>{\"action\": \"search_symbols\", \"query\": \"func_name\"}</tool_call>` (or `[SEARCH_SYMBOLS: query]`)\n"
    "- Write file: `<tool_call>{\"action\": \"write_file\", \"path\": \"filename.ext\", \"content\": \"...\"}</tool_call>` "
    "(or `[WRITE_FILE: path]content[/WRITE_FILE]`)\n\n"
    "EXAMPLES:\n"
    "User: search for all python files\n"
    "Assistant: <tool_call>{\"action\": \"search_files\", \"query\": \"*.py\"}</tool_call>\n\n"
    "User: what is in my directory?\n"
    "Assistant: <tool_call>{\"action\": \"list_dir\", \"path\": \".\"}</tool_call>\n\n"
    "User: read function reload_system in system.py\n"
    "Assistant: <tool_call>{\"action\": \"read_symbol\", \"path\": \"system.py\", \"symbol\": \"reload_system\"}</tool_call>\n\n"
    "User: read the file lab.py\n"
    "Assistant: <tool_call>{\"action\": \"read_file\", \"path\": \"lab.py\"}</tool_call>\n\n"
    "User: create notes.txt with 'Hello from DevCore'\n"
    "Assistant: <tool_call>{\"action\": \"write_file\", \"path\": \"notes.txt\", \"content\": \"Hello from DevCore\"}</tool_call>\n"
)

LOCAL_AGENT_SYNTHESIS_SYSTEM = (
    "You are the DevCore Local AI Assistant running offline on the user's machine. "
    "Provide a helpful, clear, and friendly conversational response summarizing the tool results to answer the user's request. "
    "Do not emit any tool calls in this response."
)


def parse_search_intent(prompt: str) -> tuple:
    """Detects user intent to search workspace files by filename, extension glob, or pattern. Returns (has_intent: bool, search_query: str | None)."""
    clean = (prompt or "").strip()
    low = clean.lower()

    if any(k in low for k in ["search for all python files", "find all python files", "search python files", "find python files", "search for python files", "list all python files", "show all python files"]):
        return True, "*.py"

    if any(k in low for k in ["search for all json files", "find all json files", "search json files", "find json files", "search for json files", "list all json files"]):
        return True, "*.json"

    # Targeted pattern search: "search for files matching *.py", "find files named test"
    m_search = re.search(
        r"(?:search|find|locate)\s+(?:for\s+)?(?:all\s+)?(?:the\s+)?(?:files?\s+|scripts?\s+)?"
        r"(?:matching|named|with\s+name|with\s+pattern|called)\s+"
        r"['\"`]?([a-zA-Z0-9_\-\.\*\?]+)['\"`]?",
        clean,
        re.IGNORECASE
    )
    if m_search:
        target = m_search.group(1).strip()
        if target.lower() not in ("all", "the", "files", "file", "scripts", "workspace", "directory", "dir", "here", "in", "for"):
            return True, target

    m_ext = re.search(r"(?:search|find|locate)\s+(?:for\s+)?(?:all\s+)?(?:the\s+)?([a-zA-Z0-9_\-]+)\s+(?:files?|scripts?)", clean, re.IGNORECASE)
    if m_ext:
        ext = m_ext.group(1).lower().strip()
        if ext not in ("all", "the", "my", "our", "this", "these", "some", "any", "for", "in", "workspace"):
            if ext in ("python", "py"):
                return True, "*.py"
            elif ext in ("json",):
                return True, "*.json"
            elif ext in ("markdown", "md"):
                return True, "*.md"
            elif ext in ("javascript", "js"):
                return True, "*.js"
            elif ext in ("html",):
                return True, "*.html"
            elif ext in ("css",):
                return True, "*.css"
            else:
                return True, f"*.{ext}"

    m_direct = re.match(r"^(?:search|find|locate)\s+['\"`]?([a-zA-Z0-9_\-\.\*\?]+)['\"`]?$", clean, re.IGNORECASE)
    if m_direct:
        q = m_direct.group(1).strip()
        if q.lower() not in ("files", "directory", "dir", "workspace", "folder"):
            return True, q

    m_where = re.search(r"where\s+is\s+(?:the\s+file\s+|file\s+)?['\"`]?([a-zA-Z0-9_\-\.\*\?]+)['\"`]?", clean, re.IGNORECASE)
    if m_where:
        q = m_where.group(1).strip()
        if q.lower() not in ("the", "file", "it", "this"):
            return True, q

    m_in_ws = re.search(
        r"(?:search|find|locate)\s+['\"`]?([a-zA-Z0-9_\-\.\*\?]+)['\"`]?\s+(?:in|across|under)\s+(?:the\s+)?(?:workspace|directory|folder|repo|project)",
        clean,
        re.IGNORECASE
    )
    if m_in_ws:
        target = m_in_ws.group(1).strip()
        if target.lower() not in ("all", "files", "the", "everything"):
            return True, target

    return False, None


def parse_directory_intent(prompt: str) -> tuple:
    clean = (prompt or "").strip()
    low = clean.lower()

    if low in ("ls", "dir", "tree", "browse root", "browse workspace", "list files", "show files", "my directory", "workspace"):
        return True, ""

    m = re.match(r"^(?:ls|dir|tree)\s+['\"`]?([a-zA-Z0-9_\-\./\\]+)['\"`]?$", clean, re.IGNORECASE)
    if m:
        target = m.group(1).strip()
        if target in (".", "./", ".\\"):
            target = ""
        return True, target

    m = re.search(
        r"(?:list|browse|show|view|explore|see|find|get|check)\s+(?:the\s+|my\s+|this\s+)?(?:directory|dir|folder|workspace)\s+['\"`]?([a-zA-Z0-9_\-\./\\]+)['\"`]?",
        clean,
        re.IGNORECASE,
    )
    if m:
        target = m.group(1).strip()
        if target.lower() in ("the", "workspace", "directory", "dir", "folder", "root", ".", "./", "all", "here", "my", "this"):
            target = ""
        return True, target

    m = re.search(
        r"(?:list|browse|show|view|explore|see|find|get|check)\s+(?:me\s+)?(?:the\s+|all\s+|my\s+|our\s+|this\s+)?(?:files|contents|folders|directories|directory|dirs?|tree|workspace)(?:\s+(?:in|of|under|for|inside)\s+['\"`]?([a-zA-Z0-9_\-\./\\]*)['\"`]?)?",
        clean,
        re.IGNORECASE,
    )
    if m:
        raw = m.group(1) or ""
        target = raw.strip()
        if target.lower() in ("the", "workspace", "directory", "dir", "folder", "root", ".", "./", "all", "here", "my", "this", "our", ""):
            target = ""
        return True, target

    if any(k in low for k in ["what is in", "what's in", "what files", "what folders", "what items"]) and any(w in low for w in ["directory", "workspace", "folder", "here"]):
        target = ""
        m_target = re.search(r"(?:in|inside|under|of)\s+(?:the\s+folder\s+|the\s+directory\s+|folder\s+|directory\s+)?['\"`]?([a-zA-Z0-9_\-\./\\]+)['\"`]?", clean, re.IGNORECASE)
        if m_target:
            t = m_target.group(1).strip()
            if t.lower() not in ("the", "workspace", "directory", "dir", "folder", "root", ".", "./", "all", "here", "my", "this", "our"):
                target = t
        return True, target

    return False, None


def parse_symbol_intent(prompt: str) -> tuple:
    """
    Detects user intent to read a discrete symbol (function/class/method) or Markdown section.
    Returns (has_intent: bool, target_file: str | None, symbol_name: str | None).
    """
    clean = (prompt or "").strip()

    # 1. Targeted symbol/block regex: "read function reload_system in system.py" / "what does reload_system in system.py do"
    m_sym = re.search(
        r"(?:read|view|show(?:\s+me)?|display|examine|inspect|what\s+does|check)\s+(?:the\s+)?"
        r"(?:function|method|class|section|symbol|block)?\s*['\"`]?([a-zA-Z0-9_]+)['\"`]?\s+"
        r"(?:in|from|inside|of|under)\s+(?:the\s+file\s+|file\s+)?['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)['\"`]?",
        clean,
        re.IGNORECASE,
    )
    if m_sym:
        symbol = m_sym.group(1).strip()
        path = m_sym.group(2).strip()
        if symbol.lower() not in ("the", "a", "an", "file", "it", "code", "content", "contents", "all"):
            return True, path, symbol

    # 2. Key with double-colon: "read system.py::reload_system"
    m_colon = re.search(
        r"(?:read|view|show(?:\s+me)?|display|examine|inspect)\s+['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)['\"`]?",
        clean,
        re.IGNORECASE,
    )
    if m_colon:
        return True, m_colon.group(1).strip(), m_colon.group(2).strip()

    return False, None, None


def parse_read_intent(prompt: str, with_symbol: bool = False) -> tuple:
    """
    Detects user intent to read a file or symbol.
    When with_symbol=False (default): returns (has_intent: bool, target_file: str | None).
    When with_symbol=True: returns (has_intent: bool, target_file: str | None, symbol_name: str | None).
    """
    clean = (prompt or "").strip()
    if with_symbol:
        has_sym, path, sym = parse_symbol_intent(clean)
        if has_sym:
            return True, path, sym

    m = re.search(r"(?:read|view|show(?:\s+me)?|display|examine|cat|check|open|inspect)\s+(?:the\s+)?(?:file\s+|document\s+)?(?:contents?\s+of\s+|inside\s+)?['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)['\"`]?", clean, re.IGNORECASE)
    if m:
        return (True, m.group(1).strip(), None) if with_symbol else (True, m.group(1).strip())
    m2 = re.search(r"what(?:'s|\s+is)\s+(?:in|inside)\s+(?:the\s+file\s+|file\s+)?['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)['\"`]?", clean, re.IGNORECASE)
    if m2:
        return (True, m2.group(1).strip(), None) if with_symbol else (True, m2.group(1).strip())
    return (False, None, None) if with_symbol else (False, None)


def parse_write_intent(prompt: str) -> tuple:
    clean = (prompt or "").strip()

    # Pattern 1: Explicit content clause (with / containing / holding / content:)
    m_with = re.search(
        r"(?:create|write|save|update|add|generate|make)\s+(?:a\s+)?(?:new\s+)?(?:python\s+|lua\s+|shell\s+|bash\s+|js\s+|text\s+)?(?:file|script|document)?\s*(?:named|called)?\s*['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)['\"`]?\s+(?:with|containing|holding|content:?)\s+['\"`]?([\s\S]+?)['\"`]?$",
        clean,
        re.IGNORECASE
    )
    if m_with:
        path = m_with.group(1).strip()
        content = m_with.group(2).strip()
        return True, path, content

    # Pattern 2: "write 'content' to file.ext"
    m_to = re.search(
        r"(?:write|save)\s+['\"`]?([\s\S]+?)['\"`]?\s+to\s+(?:the\s+file\s+|file\s+)?['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)['\"`]?",
        clean,
        re.IGNORECASE
    )
    if m_to:
        content = m_to.group(1).strip()
        path = m_to.group(2).strip()
        if len(content) > 0 and path:
            return True, path, content

    # Pattern 3: Generative file creation request without inline content
    m_gen = re.search(
        r"(?:create|write|save|update|add|generate|make)\s+(?:a\s+)?(?:new\s+)?(?:python\s+|lua\s+|shell\s+|bash\s+|js\s+|text\s+)?(?:file|script|document)?\s*(?:named|called)?\s*['\"`]?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)['\"`]?",
        clean,
        re.IGNORECASE
    )
    if m_gen:
        path = m_gen.group(1).strip()
        if "." in path and not path.endswith("."):
            return True, path, ""

    return False, None, None


def extract_local_tool_calls(response: str) -> list:
    calls = []
    seen = set()

    tc_pattern = re.compile(r"<tool_call>\s*(\{[\s\S]*?)(?:</tool_call>|$)", re.IGNORECASE)
    for m in tc_pattern.finditer(response):
        raw_fragment = m.group(1).strip()
        brace_count = 0
        json_str = ""
        in_string = False
        escape = False
        for char in raw_fragment:
            if escape:
                json_str += char
                escape = False
                continue
            if char == "\\":
                json_str += char
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                json_str += char
                continue
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    json_str += char
                    if brace_count == 0:
                        break
                    continue
            json_str += char
        
        if json_str:
            try:
                data = json.loads(json_str)
                action = data.get("action") or data.get("tool")
                path = data.get("path") or data.get("file")
                sym = data.get("symbol") or data.get("name")
                query = data.get("query")
                sig = f"{action}:{path}:{sym}:{query}:{data.get('content', '')}"
                if action and sig not in seen:
                    seen.add(sig)
                    calls.append(data)
            except Exception:
                pass

    for p, c in re.findall(r"\[WRITE_FILE:\s*([^\n\]]+)\]([\s\S]*?)\[/WRITE_FILE\]", response, re.IGNORECASE):
        clean_p = p.strip()
        sig = f"write_file:{clean_p}:{c.strip()}"
        if clean_p and sig not in seen:
            seen.add(sig)
            calls.append({"action": "write_file", "path": clean_p, "content": c.strip()})

    for p in re.findall(r"\[READ_FILE:\s*([^\]]+)\]", response, re.IGNORECASE):
        clean_p = p.strip()
        sig = f"read_file:{clean_p}:"
        if clean_p and sig not in seen:
            seen.add(sig)
            calls.append({"action": "read_file", "path": clean_p})

    for p, sym in re.findall(r"\[READ_SYMBOL:\s*([^\n\]:]+)::([^\]]+)\]", response, re.IGNORECASE):
        clean_p = p.strip()
        clean_sym = sym.strip()
        sig = f"read_symbol:{clean_p}:{clean_sym}"
        if clean_p and clean_sym and sig not in seen:
            seen.add(sig)
            calls.append({"action": "read_symbol", "path": clean_p, "symbol": clean_sym})

    for q in re.findall(r"\[SEARCH_SYMBOLS:\s*([^\]]+)\]", response, re.IGNORECASE):
        clean_q = q.strip()
        sig = f"search_symbols:{clean_q}:"
        if clean_q and sig not in seen:
            seen.add(sig)
            calls.append({"action": "search_symbols", "query": clean_q})

    for q in re.findall(r"\[SEARCH_FILES:\s*([^\]]+)\]", response, re.IGNORECASE):
        clean_q = q.strip()
        sig = f"search_files:{clean_q}:"
        if clean_q and sig not in seen:
            seen.add(sig)
            calls.append({"action": "search_files", "query": clean_q})

    for p in re.findall(r"\[LIST_DIR:\s*([^\]]*)\]", response, re.IGNORECASE):
        clean_p = p.strip() or "."
        sig = f"list_dir:{clean_p}:"
        if sig not in seen:
            seen.add(sig)
            calls.append({"action": "list_dir", "path": clean_p})

    return calls


def clean_local_model_display_text(response: str) -> str:
    cleaned = response
    cleaned = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", cleaned, flags=re.IGNORECASE)

    while True:
        m = re.search(r"<tool_call>\s*\{", cleaned, flags=re.IGNORECASE)
        if not m:
            break
        start_idx = m.start()
        brace_count = 0
        in_string = False
        escape = False
        end_idx = -1
        for i in range(m.end() - 1, len(cleaned)):
            char = cleaned[i]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
        if end_idx != -1:
            cleaned = cleaned[:start_idx] + cleaned[end_idx:]
        else:
            cleaned = cleaned[:start_idx]
            break

    cleaned = re.sub(r"\[WRITE_FILE:\s*[^\n\]]+\][\s\S]*?(?:\[/WRITE_FILE\]|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[READ_FILE:\s*[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[READ_SYMBOL:\s*[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[SEARCH_SYMBOLS:\s*[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[SEARCH_FILES:\s*[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[LIST_DIR:\s*[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?tool_call>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[/?(?:WRITE_FILE|READ_FILE|READ_SYMBOL|SEARCH_SYMBOLS|SEARCH_FILES|LIST_DIR)[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


async def execute_local_agent_task(
    agent_mgr,
    prompt: str,
    model: str,
    task_time: float,
    conversation_id: str,
    user: dict = None,
    is_admin: bool = False,
):
    """Executes a Web Portal prompt directly on the local model with autonomous file I/O tools and continuous conversation."""
    await agent_mgr.broadcast({"type": "agent_start", "model": model})

    if is_cloud_hosted_environment():
        err_msg = "⚠️ **Local & Ollama Models Unavailable on Cloud Host**: Please select a cloud model (such as Gemini 3.8 Flash or Gemini 4 Argon) when running on PythonAnywhere."
        agent_mgr.output_buffer.append(err_msg)
        await agent_mgr.broadcast({"type": "agent_chunk", "chunk": err_msg})
        await agent_mgr.broadcast({
            "type": "agent_done",
            "exit_code": 1,
            "elapsed": round(time.time() - task_time, 1),
            "status": "ERROR",
            "cancelled": False,
        })
        return

    if not conversation_id or str(conversation_id).startswith("conv-"):
        conversation_id = str(uuid.uuid4())
    agent_mgr.current_conversation_id = conversation_id

    workspace_dir = None
    if getattr(agent_mgr, "project_manager", None):
        workspace_dir = agent_mgr.project_manager.get_active_workspace_path()
    if not workspace_dir:
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    sec_mgr = None
    if hasattr(agent_mgr, "_get_security"):
        try:
            sec_mgr = agent_mgr._get_security()
        except Exception:
            pass

    clean_prompt = prompt
    try:
        sm_inst = agent_mgr._get_session_mgr()
        cleaned = sm_inst._clean_prompt_text(prompt)
        if cleaned:
            clean_prompt = cleaned
    except Exception:
        if clean_prompt.startswith("<SYSTEM_MESSAGE>"):
            parts = clean_prompt.split("</SYSTEM_MESSAGE>\n\n", 1)
            if len(parts) == 2:
                clean_prompt = parts[1]

    brain_dir = os.path.expanduser("~/.gemini/antigravity-cli/brain")
    transcript_path, next_step_idx, prior_turns = _load_and_append_user_turn(
        brain_dir, conversation_id, clean_prompt
    )

    try:
        sm_inst = agent_mgr._get_session_mgr()
        proj_name = agent_mgr.project_manager.active_project if getattr(agent_mgr, "project_manager", None) else None
        username = user.get("username") if user else "admin"
        sm_inst.register_session_owner(conversation_id, username, proj_name)
        sm_inst._conv_meta_cache.pop(conversation_id, None)
    except Exception:
        pass

    await agent_mgr.broadcast({
        "type": "init_conv_id",
        "conversation_id": conversation_id,
        "real_model": model,
    })

    file_context_blocks = []
    executed_actions_log = []

    has_search_query, search_target = parse_search_intent(clean_prompt)
    if has_search_query:
        s_ok, s_text = local_search_files(workspace_dir, search_target or "*", user=user, sec_mgr=sec_mgr)
        act_id = str(uuid.uuid4())[:8]
        display_query = search_target if search_target else "*"
        await agent_mgr.broadcast({
            "type": "action_start",
            "action": {
                "id": act_id,
                "tool": "search_files",
                "params": {"query": display_query},
                "status": "running",
                "friendly_name": "Search Files",
                "thought": f"Searching workspace for files matching '{display_query}'",
                "announcement": f"Searching files for {display_query}..."
            }
        })
        await asyncio.sleep(0.05)
        await agent_mgr.broadcast({
            "type": "action_done",
            "action": {
                "id": act_id,
                "tool": "search_files",
                "params": {"query": display_query},
                "output": s_text[:2000] + ("\n... [truncated]" if len(s_text) > 2000 else ""),
                "duration": 0.05,
                "status": "done" if s_ok else "error",
                "friendly_name": "Search Files",
                "announcement": f"Completed file search for {display_query}."
            }
        })
        file_context_blocks.append(f"--- File Search Results: {display_query} ---\n{s_text}")
        executed_actions_log.append(f"> 🔍 **Files Searched:** `{display_query}`")

    if not has_search_query:
        has_dir_query, dir_target = parse_directory_intent(clean_prompt)
        if has_dir_query:
            d_ok, d_text = local_list_directory(workspace_dir, dir_target or "", user=user, sec_mgr=sec_mgr)
            if d_ok:
                act_id = str(uuid.uuid4())[:8]
                display_target = dir_target if dir_target else "workspace root"
                await agent_mgr.broadcast({
                    "type": "action_start",
                    "action": {
                        "id": act_id,
                        "tool": "list_directory",
                        "params": {"path": dir_target or "."},
                        "status": "running",
                        "friendly_name": "Browse Directory",
                        "thought": f"Listing directory contents of '{display_target}' for local analysis",
                        "announcement": f"Browsing directory {display_target}..."
                    }
                })
                await asyncio.sleep(0.05)
                await agent_mgr.broadcast({
                    "type": "action_done",
                    "action": {
                        "id": act_id,
                        "tool": "list_directory",
                        "params": {"path": dir_target or "."},
                        "output": d_text[:2000] + ("\n... [truncated]" if len(d_text) > 2000 else ""),
                        "duration": 0.05,
                        "status": "done",
                        "friendly_name": "Browse Directory",
                        "announcement": f"Completed browsing {display_target}."
                    }
                })
                file_context_blocks.append(f"--- Directory Listing: {dir_target or '.'} ---\n{d_text}")
                executed_actions_log.append(f"> 📁 **Directory Browsed:** `{display_target}`")

    has_read_query, req_read_file, req_read_symbol = parse_read_intent(clean_prompt, with_symbol=True)
    if has_read_query:
        if req_read_symbol:
            f_ok, f_text, f_meta = local_read_symbol(workspace_dir, req_read_file, req_read_symbol, user=user, sec_mgr=sec_mgr)
            if f_ok:
                act_id = str(uuid.uuid4())[:8]
                await agent_mgr.broadcast({
                    "type": "action_start",
                    "action": {
                        "id": act_id,
                        "tool": "read_symbol",
                        "params": {"path": req_read_file, "symbol": req_read_symbol},
                        "status": "running",
                        "friendly_name": "Read Symbol",
                        "thought": f"Reading {f_meta.get('kind', 'symbol')} '{req_read_symbol}' in '{req_read_file}' ({f_meta.get('line_count')} lines)",
                        "announcement": f"Reading symbol {req_read_symbol} in {req_read_file}..."
                    }
                })
                await asyncio.sleep(0.05)
                await agent_mgr.broadcast({
                    "type": "action_done",
                    "action": {
                        "id": act_id,
                        "tool": "read_symbol",
                        "params": {"path": req_read_file, "symbol": req_read_symbol},
                        "output": f_text[:2000] + ("\n... [truncated]" if len(f_text) > 2000 else ""),
                        "duration": 0.05,
                        "status": "done",
                        "friendly_name": "Read Symbol",
                        "announcement": f"Completed reading symbol {req_read_symbol}."
                    }
                })
                file_context_blocks.append(f"--- Symbol/Section: {req_read_file}::{req_read_symbol} ({f_meta.get('line_count', 0)} lines, hash {f_meta.get('content_hash', '')}) ---\n{f_text}")
                executed_actions_log.append(f"> 🧩 **Symbol Read:** `{req_read_file}::{req_read_symbol}` ({len(f_text)} bytes, {f_meta.get('line_count', 0)} lines)")
        else:
            f_ok, f_text = local_read_file(workspace_dir, req_read_file, user=user, sec_mgr=sec_mgr)
            if f_ok:
                act_id = str(uuid.uuid4())[:8]
                await agent_mgr.broadcast({
                    "type": "action_start",
                    "action": {
                        "id": act_id,
                        "tool": "read_file",
                        "params": {"path": req_read_file},
                        "status": "running",
                        "friendly_name": "Read File",
                        "thought": f"Reading '{req_read_file}' for local analysis",
                        "announcement": f"Reading file {req_read_file}..."
                    }
                })
                await asyncio.sleep(0.05)
                await agent_mgr.broadcast({
                    "type": "action_done",
                    "action": {
                        "id": act_id,
                        "tool": "read_file",
                        "params": {"path": req_read_file},
                        "output": f_text[:2000] + ("\n... [truncated]" if len(f_text) > 2000 else ""),
                        "duration": 0.05,
                        "status": "done",
                        "friendly_name": "Read File",
                        "announcement": f"Completed reading {req_read_file}."
                    }
                })
                file_context_blocks.append(f"--- File: {req_read_file} ---\n{f_text}")
                executed_actions_log.append(f"> 📄 **File Read:** `{req_read_file}` ({len(f_text)} bytes)")
    has_write_query, prompt_target_file, prompt_target_content = parse_write_intent(clean_prompt)
    if has_write_query and prompt_target_content:
        w_ok, w_msg = local_write_file(workspace_dir, prompt_target_file, prompt_target_content, user=user, sec_mgr=sec_mgr)
        act_id = str(uuid.uuid4())[:8]
        await agent_mgr.broadcast({
            "type": "action_start",
            "action": {
                "id": act_id,
                "tool": "write_file",
                "params": {"path": prompt_target_file, "size": len(prompt_target_content)},
                "status": "running",
                "friendly_name": "Write File",
                "thought": f"Writing {len(prompt_target_content)} bytes to '{prompt_target_file}'",
                "announcement": f"Writing file {prompt_target_file}..."
            }
        })
        await asyncio.sleep(0.05)
        await agent_mgr.broadcast({
            "type": "action_done",
            "action": {
                "id": act_id,
                "tool": "write_file",
                "params": {"path": prompt_target_file, "size": len(prompt_target_content)},
                "output": w_msg,
                "duration": 0.05,
                "status": "done" if w_ok else "error",
                "friendly_name": "Write File",
                "announcement": f"Completed writing {prompt_target_file}."
            }
        })
        executed_actions_log.append(f"> ✅ **File Written:** `{prompt_target_file}` ({len(prompt_target_content)} bytes)")
        file_context_blocks.append(f"--- Action Executed: Successfully created/wrote file '{prompt_target_file}' ({len(prompt_target_content)} bytes) ---")

    dialogue_lines = []
    if prior_turns:
        for t in prior_turns:
            role = "User" if t["role"] == "user" else "Assistant"
            dialogue_lines.append(f"{role}: {t['content']}")

    history_str = "\n".join(dialogue_lines) if dialogue_lines else ""
    file_context_str = "\n\n".join(file_context_blocks) if file_context_blocks else ""

    write_hint = ""
    if has_write_query and not prompt_target_content and prompt_target_file:
        write_hint = f"\n\n[INSTRUCTION: Please generate the full code for '{prompt_target_file}' in a markdown code block (```python ... ```) or emit a write_file tool call.]"

    if file_context_str:
        system_prompt = LOCAL_AGENT_SYNTHESIS_SYSTEM
        query_payload = f"WORKSPACE FILE CONTENT:\n{file_context_str}\n\nUSER REQUEST:\n{clean_prompt}{write_hint}"
    else:
        system_prompt = LOCAL_AGENT_SYSTEM_PROMPT
        query_payload = f"{clean_prompt}{write_hint}"

    if history_str:
        query_payload = f"PREVIOUS CONVERSATION HISTORY:\n{history_str}\n\nCURRENT REQUEST:\n{query_payload}"

    loop = asyncio.get_running_loop()
    is_ollama = isinstance(model, str) and (model.lower().startswith("ollama:") or "ollama" in model.lower())
    active_gguf = resolve_gguf_model_path(model)

    if is_ollama:
        response = await loop.run_in_executor(
            None,
            run_local_ollama_model,
            system_prompt,
            query_payload,
            model,
            1400,
            "portal_chat",
        )
    else:
        response = await loop.run_in_executor(
            None,
            run_dynamic_local_qwen,
            system_prompt,
            query_payload,
            1400,
            "portal_chat",
            0,
            active_gguf,
        )

    newly_discovered_contexts = []
    extracted_calls = extract_local_tool_calls(response)
    for tc_data in extracted_calls:
        action = tc_data.get("action")
        path = tc_data.get("path")
        content = tc_data.get("content", "")
        if action == "write_file" and path and content:
            already_done = any(f"`{path}`" in act and "Written" in act for act in executed_actions_log)
            if already_done:
                continue
            w_ok, w_msg = local_write_file(workspace_dir, path, content, user=user, sec_mgr=sec_mgr)
            act_id = str(uuid.uuid4())[:8]
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "write_file",
                    "params": {"path": path, "size": len(content)},
                    "status": "running",
                    "friendly_name": "Write File",
                    "thought": f"Writing {len(content)} bytes to '{path}'",
                    "announcement": f"Writing file {path}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "write_file",
                    "params": {"path": path, "size": len(content)},
                    "output": w_msg,
                    "duration": 0.05,
                    "status": "done" if w_ok else "error",
                    "friendly_name": "Write File",
                    "announcement": f"Completed writing {path}."
                }
            })
            executed_actions_log.append(f"> ✅ **File Written:** `{path}` ({len(content)} bytes)")
        elif action == "read_file" and path:
            r_ok, r_content = local_read_file(workspace_dir, path, user=user, sec_mgr=sec_mgr)
            act_id = str(uuid.uuid4())[:8]
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "read_file",
                    "params": {"path": path},
                    "status": "running",
                    "friendly_name": "Read File",
                    "thought": f"Reading '{path}'",
                    "announcement": f"Reading file {path}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "read_file",
                    "params": {"path": path},
                    "output": r_content[:2000] + ("\n... [truncated]" if len(r_content) > 2000 else ""),
                    "duration": 0.05,
                    "status": "done" if r_ok else "error",
                    "friendly_name": "Read File",
                    "announcement": f"Completed reading {path}."
                }
            })
            executed_actions_log.append(f"> 📄 **File Read:** `{path}` ({len(r_content)} bytes)")
            if r_ok:
                newly_discovered_contexts.append(f"--- File: {path} ---\n{r_content}")
        elif action in ("read_symbol", "read_block") and path:
            sym_name = tc_data.get("symbol") or ""
            r_ok, r_content, r_meta = local_read_symbol(workspace_dir, path, sym_name, user=user, sec_mgr=sec_mgr)
            act_id = str(uuid.uuid4())[:8]
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "read_symbol",
                    "params": {"path": path, "symbol": sym_name},
                    "status": "running",
                    "friendly_name": "Read Symbol",
                    "thought": f"Reading symbol '{sym_name}' in '{path}'",
                    "announcement": f"Reading symbol {sym_name}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "read_symbol",
                    "params": {"path": path, "symbol": sym_name},
                    "output": r_content[:2000] + ("\n... [truncated]" if len(r_content) > 2000 else ""),
                    "duration": 0.05,
                    "status": "done" if r_ok else "error",
                    "friendly_name": "Read Symbol",
                    "announcement": f"Completed reading symbol {sym_name}."
                }
            })
            executed_actions_log.append(f"> 🧩 **Symbol Read:** `{path}::{sym_name}` ({len(r_content)} bytes)")
            if r_ok:
                newly_discovered_contexts.append(f"--- Symbol/Section: {path}::{sym_name} ({r_meta.get('line_count', 0)} lines, hash {r_meta.get('content_hash', '')}) ---\n{r_content}")
        elif action in ("write_symbol", "update_symbol") and path and content:
            sym_name = tc_data.get("symbol") or ""
            w_ok, w_msg = local_write_symbol(workspace_dir, path, sym_name, content, user=user, sec_mgr=sec_mgr)
            act_id = str(uuid.uuid4())[:8]
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "write_symbol",
                    "params": {"path": path, "symbol": sym_name, "size": len(content)},
                    "status": "running",
                    "friendly_name": "Write Symbol",
                    "thought": f"Updating symbol '{sym_name}' in '{path}'",
                    "announcement": f"Writing symbol {sym_name}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "write_symbol",
                    "params": {"path": path, "symbol": sym_name, "size": len(content)},
                    "output": w_msg,
                    "duration": 0.05,
                    "status": "done" if w_ok else "error",
                    "friendly_name": "Write Symbol",
                    "announcement": f"Completed writing symbol {sym_name}."
                }
            })
            executed_actions_log.append(f"> 🧩 **Symbol Written:** `{path}::{sym_name}` ({len(content)} bytes)")
        elif action in ("search_symbols", "find_symbols"):
            q = tc_data.get("query") or tc_data.get("symbol") or ""
            matches = []
            try:
                from security.raugus_resolver import RaugusResolver
                resolver = RaugusResolver()
                for k, v in resolver.phonebook.items():
                    if v.get("type") in ("function", "async_function", "class", "method", "section"):
                        s_name = v.get("symbol_name", "")
                        if q.lower() in k.lower() or q.lower() in s_name.lower():
                            matches.append(f"- {k} ({v.get('type')}, lines {v.get('start_line')}-{v.get('end_line')})")
                            if len(matches) >= 20:
                                break
            except Exception:
                pass
            res_str = "\n".join(matches) if matches else f"No symbols found matching '{q}'."
            act_id = str(uuid.uuid4())[:8]
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "search_symbols",
                    "params": {"query": q},
                    "status": "running",
                    "friendly_name": "Search Symbols",
                    "thought": f"Searching for symbols matching '{q}'",
                    "announcement": f"Searching symbols for {q}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "search_symbols",
                    "params": {"query": q},
                    "output": res_str,
                    "duration": 0.05,
                    "status": "done",
                    "friendly_name": "Search Symbols",
                    "announcement": f"Completed search for {q}."
                }
            })
            executed_actions_log.append(f"> 🔍 **Symbols Searched:** `{q}` ({len(matches)} matches)")
            newly_discovered_contexts.append(f"--- Symbol Search Results for '{q}' ---\n{res_str}")
        elif action in ("search_files", "find_files", "locate_files"):
            q = tc_data.get("query") or tc_data.get("pattern") or tc_data.get("path") or "*"
            s_ok, s_text = local_search_files(workspace_dir, q, user=user, sec_mgr=sec_mgr)
            act_id = str(uuid.uuid4())[:8]
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "search_files",
                    "params": {"query": q},
                    "status": "running",
                    "friendly_name": "Search Files",
                    "thought": f"Searching workspace for files matching '{q}'",
                    "announcement": f"Searching files for {q}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "search_files",
                    "params": {"query": q},
                    "output": s_text[:2000] + ("\n... [truncated]" if len(s_text) > 2000 else ""),
                    "duration": 0.05,
                    "status": "done" if s_ok else "error",
                    "friendly_name": "Search Files",
                    "announcement": f"Completed search for {q}."
                }
            })
            executed_actions_log.append(f"> 🔍 **Files Searched:** `{q}`")
            if s_ok:
                newly_discovered_contexts.append(f"--- File Search Results for '{q}' ---\n{s_text}")
        elif action in ("list_dir", "browse_directory", "list_directory", "list_files", "ls", "dir"):
            dir_path = (path or "").strip()
            l_ok, l_text = local_list_directory(workspace_dir, dir_path, user=user, sec_mgr=sec_mgr)
            act_id = str(uuid.uuid4())[:8]
            display_target = dir_path if dir_path else "workspace root"
            await agent_mgr.broadcast({
                "type": "action_start",
                "action": {
                    "id": act_id,
                    "tool": "list_directory",
                    "params": {"path": dir_path or "."},
                    "status": "running",
                    "friendly_name": "Browse Directory",
                    "thought": f"Listing directory '{display_target}'",
                    "announcement": f"Browsing directory {display_target}..."
                }
            })
            await asyncio.sleep(0.05)
            await agent_mgr.broadcast({
                "type": "action_done",
                "action": {
                    "id": act_id,
                    "tool": "list_directory",
                    "params": {"path": dir_path or "."},
                    "output": l_text[:2000] + ("\n... [truncated]" if len(l_text) > 2000 else ""),
                    "duration": 0.05,
                    "status": "done" if l_ok else "error",
                    "friendly_name": "Browse Directory",
                    "announcement": f"Completed browsing {display_target}."
                }
            })
            executed_actions_log.append(f"> 📁 **Directory Browsed:** `{display_target}`")
            if l_ok:
                newly_discovered_contexts.append(f"--- Directory Listing: {dir_path or '.'} ---\n{l_text}")

    already_written = any(
        f"`{prompt_target_file}`" in act and ("Written" in act or "Created" in act or "Updated" in act)
        for act in executed_actions_log
    )
    if prompt_target_file and not already_written:
        code_block_match = re.search(r"```(?:[a-zA-Z0-9_\-]+)?\n([\s\S]*?)```", response)
        if code_block_match:
            extracted_code = code_block_match.group(1).rstrip()
            if len(extracted_code) > 5:
                w_ok, w_msg = local_write_file(workspace_dir, prompt_target_file, extracted_code, user=user, sec_mgr=sec_mgr)
                act_id = str(uuid.uuid4())[:8]
                await agent_mgr.broadcast({
                    "type": "action_start",
                    "action": {
                        "id": act_id,
                        "tool": "write_file",
                        "params": {"path": prompt_target_file, "size": len(extracted_code)},
                        "status": "running",
                        "friendly_name": "Write File",
                        "thought": f"Saving code to '{prompt_target_file}'",
                        "announcement": f"Writing file {prompt_target_file}..."
                    }
                })
                await asyncio.sleep(0.05)
                await agent_mgr.broadcast({
                    "type": "action_done",
                    "action": {
                        "id": act_id,
                        "tool": "write_file",
                        "params": {"path": prompt_target_file, "size": len(extracted_code)},
                        "output": w_msg,
                        "duration": 0.05,
                        "status": "done" if w_ok else "error",
                        "friendly_name": "Write File",
                        "announcement": f"Completed writing {prompt_target_file}."
                    }
                })
                executed_actions_log.append(f"> ✅ **File Created/Updated:** `{prompt_target_file}` ({len(extracted_code)} bytes)")

    clean_display_response = clean_local_model_display_text(response)

    if newly_discovered_contexts:
        added_ctx = "\n\n".join(newly_discovered_contexts)
        synthesis_prompt = (
            f"TOOL DISCOVERY RESULTS:\n{added_ctx}\n\n"
            f"USER REQUEST:\n{clean_prompt}\n\n"
            "Based on the tool results above, provide a clear, helpful response answering the user's request."
        )
        if is_ollama:
            second_response = await loop.run_in_executor(
                None,
                run_local_ollama_model,
                LOCAL_AGENT_SYNTHESIS_SYSTEM,
                synthesis_prompt,
                model,
                800,
                "portal_chat_synthesis",
            )
        else:
            second_response = await loop.run_in_executor(
                None,
                run_dynamic_local_qwen,
                LOCAL_AGENT_SYNTHESIS_SYSTEM,
                synthesis_prompt,
                800,
                "portal_chat_synthesis",
                0,
                active_gguf,
            )
        cleaned_2nd = clean_local_model_display_text(second_response)
        if cleaned_2nd:
            clean_display_response = cleaned_2nd

    if executed_actions_log:
        actions_summary = "\n".join(executed_actions_log)
        clean_display_response = f"{actions_summary}\n\n{clean_display_response}".strip()

    if not clean_display_response:
        clean_display_response = response

    if not is_admin and sec_mgr:
        clean_display_response = sec_mgr.scrub_text(clean_display_response)

    in_tok = max(1, (len(clean_prompt) + len(history_str) + len(file_context_str)) // 4)
    out_tok = max(1, len(clean_display_response) // 4)
    est_tokens = in_tok + out_tok
    usage_payload = {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": est_tokens,
        "cache_read_tokens": 0,
        "is_local": True,
        "local_tokens_offloaded": est_tokens,
        "model": model,
    }

    _append_planner_response(transcript_path, next_step_idx, clean_display_response, usage_payload)
    try:
        sm_inst = agent_mgr._get_session_mgr()
        proj_name = agent_mgr.project_manager.active_project if getattr(agent_mgr, "project_manager", None) else None
        username = user.get("username") if user else "admin"
        sm_inst.register_session_owner(conversation_id, username, proj_name)
        sm_inst._conv_meta_cache.pop(conversation_id, None)
    except Exception:
        pass

    agent_mgr.output_buffer.append(clean_display_response)
    await agent_mgr.broadcast({"type": "agent_chunk", "chunk": clean_display_response})

    elapsed = round(time.time() - task_time, 1)

    modder_id = user.get("username", "LocalUser") if user else "LocalUser"
    SwarmFlowLogger.log_tuple(
        modder_id=modder_id,
        agent_id=conversation_id,
        target_namespace="web_portal_chat",
        model_tier=model,
        token_volume=est_tokens,
    )

    await agent_mgr.broadcast({
        "type": "token_telemetry",
        "usage": usage_payload,
        "conversation_id": conversation_id,
    })

    agent_mgr.last_completed_task = {
        "prompt": prompt,
        "model": model,
        "actions": getattr(agent_mgr, "actions", []),
        "output": clean_display_response,
        "elapsed": elapsed,
        "status": "SUCCESS",
        "timestamp": time.time(),
    }

    await agent_mgr.broadcast({
        "type": "agent_done",
        "exit_code": 0,
        "elapsed": elapsed,
        "status": "SUCCESS",
        "cancelled": False,
    })


run_local_qwen = run_dynamic_local_qwen

try:
    _lbb_module.run_local_qwen = run_dynamic_local_qwen
    _lbb_module.local_list_directory = local_list_directory
    _lbb_module.local_search_files = local_search_files
except Exception:
    pass


def main():
    parser = argparse.ArgumentParser(description="DevCore Local Model Token Optimization Service")
    parser.add_argument("--query", default=None, help="Query or prompt to execute on local Qwen")
    parser.add_argument("--context", default=None, help="Context file path or inline text")
    parser.add_argument(
        "--mode",
        choices=["query", "compress", "exam", "draft"],
        default="query",
        help="Execution mode",
    )
    parser.add_argument("--target", default=None, help="Target document path for compression or exam")
    parser.add_argument("--count", type=int, default=5, help="Question count for exam mode")
    parser.add_argument("--max-tokens", type=int, default=800, help="Max generated tokens")
    args = parser.parse_args()

    target_content = ""
    if args.target and os.path.exists(args.target):
        if os.path.isdir(args.target):
            _, target_content = local_list_directory(args.target, ".")
        else:
            _, target_content = read_target_documents(args.target)
    elif args.context:
        if os.path.exists(args.context):
            if os.path.isdir(args.context):
                _, target_content = local_list_directory(args.context, ".")
            else:
                _, target_content = read_target_documents(args.context)
        else:
            target_content = args.context
    if args.mode == "exam":
        target = args.target or target_content
        result = generate_local_exam(target, count=args.count, query=args.query)
        print(json.dumps(result, indent=2))
    elif args.mode == "compress":
        text_to_compress = target_content or args.query or ""
        label = os.path.basename(args.target) if args.target else "cli"
        summary = compress_context(text_to_compress, target_tokens=args.max_tokens, context_label=label)
        print(summary)
    else:
        out = query_local_model(
            prompt=args.query or "Summarize the context.",
            context=target_content,
            max_tokens=args.max_tokens,
            mode=args.mode,
            context_label=os.path.basename(args.target) if args.target else "cli",
        )
        print(out)


if __name__ == "__main__":
    main()
