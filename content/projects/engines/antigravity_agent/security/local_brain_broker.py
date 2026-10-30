import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid

LLAMA_CLI = os.path.expanduser("~/.local/llama-cpp/llama-cli")
MODEL_PATH = os.path.expanduser("~/.local/models/qwen2.5-1.5b-instruct-q4_k_m.gguf")

_DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, _DEVCORE_ROOT)

from security.central_logger import log_siem_event
from security.raugus_resolver import normalize_cross_platform_path, resolver
from security.swarm_telemetry import SwarmFlowLogger

_PRESIDIO_ANALYZER = None
_PRESIDIO_ANONYMIZER = None

_TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".yaml", ".yml",
    ".ini", ".cfg", ".rst", ".py", ".js", ".html", ".xml", ".log",
}
_SKIP_FILENAMES = {
    "desktop.ini",
    ".ds_store",
    ".849c9593-d756-4e56-8d6e-42412f2a707b",
}


def offline_scrub_pii(text: str, use_nlp: bool = False, stage: str = "stream") -> str:
    """
    Strictly offline PII, South African ID, cellphone/landline, address, medical,
    and secret scrubbing using deterministic regex + local Microsoft Presidio NLP.
    Never makes any external network/cloud calls. Logs any PII/secret redactions to SIEM.
    """
    if not text:
        return text

    scrubbed = re.sub(r"AIza[0-9A-Za-z\-_]{35}", "<REDACTED_API_KEY>", text)
    scrubbed = re.sub(r"sk-[0-9A-Za-z]{20,}", "<REDACTED_SECRET_KEY>", scrubbed)
    scrubbed = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<REDACTED_EMAIL>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "<REDACTED_IP>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)(password|passwd|secret|api_key|token)\s*[:=]\s*['\"]?[^\s,'\"\n]+['\"]?",
        r"\1: <REDACTED_SECRET>",
        scrubbed,
    )

    scrubbed = re.sub(
        r"\b\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[\s\-]?\d{4}[\s\-]?[01]\d[\s\-]?\d\b",
        "<REDACTED_SA_ID>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)\b(id\s*(?:no|number|#)|passport\s*(?:no|number|#)?|student\s*(?:no|number|#)|learner\s*(?:no|number|#)|tax\s*(?:no|number|#)|sars\s*(?:no|number|#)|registration\s*(?:no|number|#))\s*[:=\-]?\s*[A-Z0-9/\-\s]{5,22}\b",
        r"\1: <REDACTED_ID_NUMBER>",
        scrubbed,
    )

    scrubbed = re.sub(
        r"(?:\+27|0027)[\s\-\.]?(?:\(0\))?[\s\-\.]?[1-8]\d[\s\-\.]?\d{3}[\s\-\.]?\d{4}\b",
        "<REDACTED_PHONE>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"\b(?:\(0[1-8]\d\)|0[1-8]\d)[\s\-\.]?\d{3}[\s\-\.]?\d{4}\b",
        "<REDACTED_PHONE>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"\+\d{1,3}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4}\b",
        "<REDACTED_PHONE>",
        scrubbed,
    )

    scrubbed = re.sub(
        r"\b(?:\d{4}[\s\-]){3}\d{1,4}\b",
        "<REDACTED_FINANCIAL_ID>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)\b(account\s*(?:no|number|#)|acc\s*(?:no|number|#)|iban)\s*[:=\-]?\s*\d[\d\s\-]{5,18}\d\b",
        r"\1: <REDACTED_BANK_ACCOUNT>",
        scrubbed,
    )

    scrubbed = re.sub(
        r"\b\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3}\s+(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|Boulevard|Blvd|Close|Crescent|Cres|Way|Court|Ct|Place|Pl)\b",
        "<REDACTED_ADDRESS>",
        scrubbed,
    )
    scrubbed = re.sub(
        r"(?i)\b(medical\s*aid\s*(?:no|number)?|diagnosis|disability\s*status|visual\s*acuity|chronic\s*medication|icd[\-\s]?10)\s*[:=\-]\s*[^\n,;]+",
        r"\1: <REDACTED_MEDICAL_INFO>",
        scrubbed,
    )

    if use_nlp:
        global _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER
        try:
            if _PRESIDIO_ANALYZER is None:
                import logging
                logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
                from presidio_analyzer import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine

                _PRESIDIO_ANALYZER = AnalyzerEngine()
                _PRESIDIO_ANONYMIZER = AnonymizerEngine()
            results = _PRESIDIO_ANALYZER.analyze(
                text=scrubbed,
                language="en",
                entities=[
                    "PERSON",
                    "PHONE_NUMBER",
                    "EMAIL_ADDRESS",
                    "CREDIT_CARD",
                    "IBAN_CODE",
                    "IP_ADDRESS",
                    "MEDICAL_LICENSE",
                ],
            )
            scrubbed = _PRESIDIO_ANONYMIZER.anonymize(text=scrubbed, analyzer_results=results).text
        except Exception:
            pass

    redaction_tags = (
        "<REDACTED_API_KEY>",
        "<REDACTED_SECRET_KEY>",
        "<REDACTED_EMAIL>",
        "<REDACTED_IP>",
        "<REDACTED_SECRET>",
        "<REDACTED_SA_ID>",
        "<REDACTED_ID_NUMBER>",
        "<REDACTED_PHONE>",
        "<REDACTED_FINANCIAL_ID>",
        "<REDACTED_BANK_ACCOUNT>",
        "<REDACTED_ADDRESS>",
        "<REDACTED_MEDICAL_INFO>",
        "<PERSON>",
        "<PHONE_NUMBER>",
        "<EMAIL_ADDRESS>",
        "<CREDIT_CARD>",
        "<IBAN_CODE>",
    )
    redaction_count = sum(scrubbed.count(tag) for tag in redaction_tags)
    if redaction_count > 0:
        log_siem_event(
            level="WARNING",
            message=f"[SECURITY_AUDIT] [LOCAL_BROKER_PII] Offline DLP scrubbed {redaction_count} sensitive PII/secret item(s) during '{stage}' stage.",
            module_name="local_brain_broker",
            logger_name="security.local_brain_broker",
        )

    return scrubbed


def _extract_file_text(filepath: str, limit: int) -> str:
    if limit <= 0:
        return ""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".docx":
        try:
            import xml.etree.ElementTree as ET
            import zipfile

            with zipfile.ZipFile(filepath) as z:
                xml_bytes = z.read("word/document.xml")
            tree = ET.fromstring(xml_bytes)
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paras = []
            curr_len = 0
            for p in tree.iter(f"{ns}p"):
                texts = [t.text for t in p.iter(f"{ns}t") if t.text]
                if texts:
                    line = "".join(texts)
                    paras.append(line)
                    curr_len += len(line) + 1
                    if curr_len >= limit:
                        break
            return "\n".join(paras)[:limit]
        except Exception:
            return ""
    if ext == ".pdf":
        try:
            import pypdf

            reader = pypdf.PdfReader(filepath)
            pages_text = []
            curr_len = 0
            for page in reader.pages:
                pt = page.extract_text() or ""
                if pt:
                    pages_text.append(pt)
                    curr_len += len(pt) + 1
                    if curr_len >= limit:
                        break
            return "\n".join(pages_text)[:limit]
        except Exception:
            return ""
    if ext in _TEXT_EXTENSIONS:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read(limit)
        except Exception:
            return ""
    return ""


def resolve_broker_target(target: str, user_tier: int = 5) -> dict:
    """
    Natively resolves Raugus VFS keys (devcore.*), AST symbol keys (<module>::<symbol>),
    invariant block tags (id UUID or symbol/section name), and filesystem paths.
    Returns normalized target metadata without leaking physical filesystem paths to cloud models.
    """
    clean_target = (target or "").strip().strip("'\"")
    if not clean_target:
        return {"status": "EMPTY", "error": "Empty target specified."}

    phonebook = getattr(resolver, "phonebook", {})
    entry = None
    target_key = None

    # 1. Direct Raugus Map VFS Key Match
    if clean_target in phonebook:
        target_key = clean_target
        entry = dict(phonebook[clean_target])
        entry["key"] = target_key

    # 2. Block Tag / Invariant UUID Match via get_block_by_tag
    if not entry and hasattr(resolver, "get_block_by_tag"):
        try:
            matched_entry = resolver.get_block_by_tag(clean_target, user_tier=user_tier)
            if matched_entry:
                entry = matched_entry
                target_key = matched_entry.get("key", clean_target)
        except Exception:
            pass

    # 3. Filesystem Path Match (if direct path or relative path provided)
    if not entry:
        norm_path = normalize_cross_platform_path(clean_target)
        for k, v in phonebook.items():
            rp = v.get("real_path")
            if rp and normalize_cross_platform_path(rp) == norm_path:
                entry = dict(v)
                target_key = k
                entry["key"] = k
                break

        if not entry and os.path.exists(norm_path):
            is_dir = os.path.isdir(norm_path)
            entry = {
                "type": "directory" if is_dir else "file",
                "real_path": norm_path,
                "required_tier": 5 if not resolver.is_sensitive_path(norm_path) else 3,
                "sensitive": resolver.is_sensitive_path(norm_path),
                "id": None,
                "symbol_name": os.path.basename(norm_path),
                "key": norm_path,
            }
            target_key = clean_target

    if not entry:
        return {
            "status": "NOT_FOUND",
            "target": clean_target,
            "error": f"Target '{clean_target}' could not be resolved in Raugus Map or filesystem.",
        }

    req_tier = int(entry.get("required_tier", 5))
    if int(user_tier) < req_tier:
        return {
            "status": "DENIED",
            "target": clean_target,
            "error": f"Access denied to target. Tier {req_tier} required.",
        }

    real_p = entry.get("real_path", "")
    if real_p:
        real_p = normalize_cross_platform_path(real_p)

    target_type = entry.get("type", "file")
    if target_type == "file" and entry.get("sensitive"):
        target_type = "vault_file"

    return {
        "status": "OK",
        "target": clean_target,
        "key": target_key,
        "target_type": target_type,
        "real_path": real_p,
        "tag_id": entry.get("id"),
        "symbol_name": entry.get("symbol_name"),
        "line_span": [entry.get("start_line"), entry.get("end_line")] if entry.get("start_line") is not None else None,
        "content_hash": entry.get("content_hash"),
        "sensitive": bool(entry.get("sensitive")),
        "entry": entry,
    }


def chunk_target_by_ast(meta: dict, max_chunk_chars: int = 6000) -> list:
    """
    Splits the target into AST blocks (functions, classes, markdown sections) or bounded chunks.
    Preserves invariant tag IDs, symbol names, line spans, and content hashes for every block.
    """
    phonebook = getattr(resolver, "phonebook", {})
    real_path = meta.get("real_path")

    # If already a specific symbol or section
    if meta.get("line_span") and real_path and os.path.exists(real_path):
        s_line, e_line = meta["line_span"]
        with open(real_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        chunk_text = "".join(lines[max(0, s_line - 1): min(len(lines), e_line)])
        c_hash = meta.get("content_hash") or hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]
        return [{
            "key": meta.get("key"),
            "tag_id": meta.get("tag_id") or f"ast-{c_hash}",
            "symbol_name": meta.get("symbol_name"),
            "type": meta.get("target_type"),
            "line_span": meta.get("line_span"),
            "content_hash": c_hash,
            "text": chunk_text,
        }]

    # If target is a directory
    if meta.get("target_type") == "directory" or (real_path and os.path.isdir(real_path)):
        chunks = []
        if real_path and os.path.exists(real_path):
            base_depth = real_path.rstrip(os.sep).count(os.sep)
            for dirpath, dirnames, filenames in os.walk(real_path):
                curr_depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
                if curr_depth >= 2:
                    dirnames[:] = []
                else:
                    dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))

                for fname in sorted(filenames):
                    if fname.startswith(".") or fname.startswith("~$") or fname.lower() in _SKIP_FILENAMES:
                        continue
                    full_p = os.path.join(dirpath, fname)
                    file_text = _extract_file_text(full_p, max_chunk_chars)
                    if file_text.strip():
                        rel_name = os.path.relpath(full_p, real_path)
                        f_hash = hashlib.sha256(file_text.encode("utf-8")).hexdigest()[:12]
                        f_tag = None
                        for k, v in phonebook.items():
                            if v.get("real_path") == full_p:
                                f_tag = v.get("id")
                                break
                        chunks.append({
                            "key": rel_name,
                            "tag_id": f_tag or f"file-{f_hash}",
                            "symbol_name": rel_name,
                            "type": "vault_file" if meta.get("sensitive") else "file",
                            "line_span": [1, file_text.count("\n") + 1],
                            "content_hash": f_hash,
                            "text": file_text,
                        })
                        if len(chunks) >= 12:
                            break
                if len(chunks) >= 12:
                    break
        return chunks

    # If target is a file / module: Check if child AST blocks exist in phonebook
    chunks = []
    target_key = meta.get("key")
    if target_key and real_path and os.path.exists(real_path):
        prefix = f"{target_key}::"
        child_entries = []
        for k, v in phonebook.items():
            if k.startswith(prefix) and v.get("start_line") is not None:
                # Prioritize top-level functions, classes, and sections
                if v.get("type") in ("function", "async_function", "class", "section"):
                    child_entries.append((v.get("start_line", 0), k, v))

        if child_entries:
            child_entries.sort(key=lambda x: x[0])
            with open(real_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for s_line, k, v in child_entries:
                e_line = v.get("end_line", s_line)
                block_lines = lines[max(0, s_line - 1): min(len(lines), e_line)]
                block_text = "".join(block_lines)
                if block_text.strip():
                    chunks.append({
                        "key": k,
                        "tag_id": v.get("id"),
                        "symbol_name": v.get("symbol_name") or k.split("::")[-1],
                        "type": v.get("type", "ast_block"),
                        "line_span": [s_line, e_line],
                        "content_hash": v.get("content_hash"),
                        "text": block_text[:max_chunk_chars],
                    })
            if chunks:
                return chunks

    # If unindexed or no child entries in phonebook, parse on-the-fly
    if real_path and os.path.isfile(real_path):
        ext = os.path.splitext(real_path)[1].lower()
        if ext == ".md":
            try:
                from generate_raugusmap import extract_markdown_sections
                md_secs = extract_markdown_sections(real_path)
                if md_secs:
                    with open(real_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    for sec_k, sec_data in md_secs.items():
                        s_line = sec_data["start_line"]
                        e_line = sec_data["end_line"]
                        sec_text = "".join(lines[max(0, s_line - 1): min(len(lines), e_line)])
                        if sec_text.strip():
                            chunks.append({
                                "key": f"{target_key or real_path}::{sec_k}",
                                "tag_id": f"sec-{sec_data['content_hash']}",
                                "symbol_name": sec_data["symbol_name"],
                                "type": "section",
                                "line_span": [s_line, e_line],
                                "content_hash": sec_data["content_hash"],
                                "text": sec_text[:max_chunk_chars],
                            })
                    if chunks:
                        return chunks
            except Exception:
                pass
        elif ext == ".py":
            try:
                from generate_raugusmap import extract_file_ast_symbols
                py_syms = extract_file_ast_symbols(real_path)
                if py_syms:
                    with open(real_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    for sym_k, sym_data in py_syms.items():
                        if sym_data.get("type") in ("function", "async_function", "class"):
                            s_line = sym_data["start_line"]
                            e_line = sym_data["end_line"]
                            sym_text = "".join(lines[max(0, s_line - 1): min(len(lines), e_line)])
                            if sym_text.strip():
                                chunks.append({
                                    "key": f"{target_key or real_path}::{sym_k}",
                                    "tag_id": f"sym-{sym_data['content_hash']}",
                                    "symbol_name": sym_data["symbol_name"],
                                    "type": sym_data["type"],
                                    "line_span": [s_line, e_line],
                                    "content_hash": sym_data["content_hash"],
                                    "text": sym_text[:max_chunk_chars],
                                })
                    if chunks:
                        return chunks
            except Exception:
                pass

        full_text = _extract_file_text(real_path, max_chunk_chars * 2)
        if full_text.strip():
            f_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:12]
            chunks.append({
                "key": target_key or real_path,
                "tag_id": meta.get("tag_id") or f"doc-{f_hash}",
                "symbol_name": meta.get("symbol_name") or os.path.basename(real_path),
                "type": meta.get("target_type", "file"),
                "line_span": [1, full_text.count("\n") + 1],
                "content_hash": f_hash,
                "text": full_text[:max_chunk_chars],
            })

    return chunks


def read_target_documents(target_path: str, max_chars: int = 8000, return_meta: bool = True):
    """
    Reads a sensitive target (VFS key, AST symbol, section tag, file, or directory).
    If target resolves to a symbol or section, extracts only that slice.
    Returns (files_read, combined_text, meta) when return_meta=True, else (files_read, combined_text).
    """
    meta = resolve_broker_target(target_path)
    if meta.get("status") != "OK":
        empty_res = ([], "")
        return ([], "", meta) if return_meta else empty_res

    chunks = chunk_target_by_ast(meta, max_chunk_chars=max_chars)
    if not chunks:
        empty_res = ([], "")
        return ([], "", meta) if return_meta else empty_res

    files_read = []
    text_pieces = []
    total_len = 0

    for ch in chunks:
        t = ch.get("text", "")
        if t.strip():
            name = ch.get("symbol_name") or ch.get("key") or "block"
            files_read.append(name)
            text_pieces.append(f"--- BLOCK: {name} (tag: {ch.get('tag_id')}) ---\n{t}")
            total_len += len(t)
            if total_len >= max_chars:
                break

    combined = "\n\n".join(text_pieces)
    if return_meta:
        return files_read, combined, meta
    return files_read, combined


def run_local_qwen(system_prompt: str, user_prompt: str, max_tokens: int = 900, target_label: str = "sensitive_vault") -> str:
    """
    Invokes the local Qwen2.5-1.5B-Instruct GGUF model via llama-cli on CPU.
    Loads into RAM only for the duration of this call and exits immediately (0 MB idle RAM).
    """
    if not os.path.exists(LLAMA_CLI) or not os.path.exists(MODEL_PATH):
        log_siem_event(
            level="ERROR",
            message="[FAULT] Local Brain binary or GGUF model missing during sensitive vault invocation.",
            module_name="local_brain_broker",
            logger_name="agent.local_brain_broker",
        )
        return (
            "[LOCAL_BRAIN_UNAVAILABLE] The local Qwen2.5-1.5B model or llama-cli binary "
            "is still downloading or missing at ~/.local/models/."
        )

    cmd = [
        LLAMA_CLI,
        "-m",
        MODEL_PATH,
        "-sys",
        system_prompt,
        "-p",
        user_prompt,
        "-n",
        str(max_tokens),
        "-t",
        "8",
        "-c",
        "4096",
        "--temp",
        "0.2",
        "--no-display-prompt",
        "-st",
        "--log-disable",
    ]

    try:
        res = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=90,
        )
        out = res.stdout
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
                out = out[: -len(marker)].strip()

        est_tokens = max(1, (len(user_prompt) + len(out)) // 4)
        SwarmFlowLogger.log_tuple(
            modder_id="LocalPrivacyBroker",
            agent_id="Qwen2.5-1.5B-CPU",
            target_namespace=target_label,
            model_tier="qwen2.5-1.5b-instruct-q4_k_m (Local CPU)",
            token_volume=est_tokens,
        )
        log_siem_event(
            level="INFO",
            message=f"[AGENTIC] Ephemeral Local Brain (Qwen2.5-1.5B) completed inference on '{target_label}' (~{est_tokens} tokens, 0 MB idle RAM).",
            module_name="local_brain_broker",
            logger_name="agent.local_brain_broker",
        )
        return out
    except subprocess.TimeoutExpired:
        log_siem_event(
            level="ERROR",
            message=f"[FAULT] Local Brain timed out after 90s while processing '{target_label}'.",
            module_name="local_brain_broker",
            logger_name="agent.local_brain_broker",
        )
        return "[LOCAL_BRAIN_TIMEOUT] Local model timed out while processing the sensitive document."
    except Exception as e:
        log_siem_event(
            level="ERROR",
            message=f"[FAULT] Local Brain execution error on '{target_label}': {str(e)}",
            module_name="local_brain_broker",
            logger_name="agent.local_brain_broker",
        )
        return f"[LOCAL_BRAIN_ERROR] {str(e)}"


def is_exfiltration_query(query: str) -> bool:
    """
    Blocks queries from the Online Model that attempt to trick the Local Brain
    into dumping or quoting raw source files verbatim.
    """
    if not query:
        return False
    q_low = query.lower()
    forbidden_phrases = (
        "verbatim",
        "word for word",
        "exact text",
        "raw text",
        "full text",
        "entire file",
        "entire document",
        "dump the",
        "print all",
        "copy paste",
        "repeat the text",
        "quote the entire",
        "base64",
    )
    return any(p in q_low for p in forbidden_phrases)


def strip_verbatim_source_lines(generated_text: str, raw_source: str, target_path: str = "") -> str:
    """
    Ensures the Local Brain never accidentally echoes long raw lines (>60 chars)
    verbatim from the sensitive source file back to the Online Model.
    """
    if not generated_text or not raw_source:
        return generated_text
    raw_lines = {
        line.strip()
        for line in raw_source.splitlines()
        if len(line.strip()) > 60
    }
    if not raw_lines:
        return generated_text
    cleaned_lines = []
    redacted_count = 0
    for out_line in generated_text.splitlines():
        if out_line.strip() in raw_lines:
            cleaned_lines.append("[REDACTED_VERBATIM_SOURCE_LINE]")
            redacted_count += 1
        else:
            cleaned_lines.append(out_line)

    if redacted_count > 0:
        reason = f"[SECURITY_AUDIT] [VERBATIM_LEAK_BLOCKED] Redacted {redacted_count} verbatim source line(s) (>60 chars) from Local Brain output for '{target_path}'."
        log_siem_event(
            level="WARNING",
            message=reason,
            module_name="local_brain_broker",
            logger_name="security.local_brain_broker",
        )
        SwarmFlowLogger.log_intrusion_alert(
            modder_id="LocalPrivacyBroker",
            agent_id="VerbatimLineFilter",
            target_namespace=target_path or "sensitive_vault",
            reason=reason,
        )
    return "\n".join(cleaned_lines)


def generate_digest(target_path: str, custom_query: str = None) -> dict:
    if is_exfiltration_query(custom_query):
        reason = f"[SECURITY_AUDIT] [EXFILTRATION_BLOCKED] Online model attempted forbidden verbatim/raw extraction query on '{target_path}': {custom_query}"
        log_siem_event(
            level="ERROR",
            message=reason,
            module_name="local_brain_broker",
            logger_name="security.local_brain_broker",
        )
        SwarmFlowLogger.log_intrusion_alert(
            modder_id="MainCloudBrain",
            agent_id="ExfiltrationQueryGuard",
            target_namespace=target_path,
            reason=reason,
        )
        return {
            "status": "BLOCKED_EXFILTRATION_ATTEMPT",
            "error": "Raugus Local Broker: Requests for verbatim or raw source dumps are strictly forbidden. Ask for synthesized summaries or exam questions only.",
        }

    meta = resolve_broker_target(target_path)
    if meta.get("status") != "OK":
        return {
            "status": meta.get("status", "ERROR"),
            "target": target_path,
            "error": meta.get("error", "Failed to resolve target."),
        }

    chunks = chunk_target_by_ast(meta, max_chunk_chars=6000)
    if not chunks:
        return {
            "status": "EMPTY",
            "target": target_path,
            "files": [],
            "digest": "No readable documents found in the sensitive directory yet.",
            "provenance": {
                "target_type": meta.get("target_type"),
                "tag_id": meta.get("tag_id"),
                "content_hash": meta.get("content_hash"),
                "line_span": meta.get("line_span"),
                "blocks_processed": 0,
            },
        }

    files = [c.get("symbol_name") or c.get("key") for c in chunks]

    # Progressive Synthesis: single pass or map-reduce
    if len(chunks) == 1:
        raw_text = chunks[0]["text"]
        pre_scrubbed = offline_scrub_pii(raw_text, stage="input_digest")
        sys_prompt = (
            "You are the Raugus Local Privacy Broker AI running offline on the user's machine. "
            "Your job is to read sensitive local documents and provide a useful, sanitized summary "
            "or topic outline for the Main Cloud Brain WITHOUT revealing any raw passwords, API keys, "
            "personal names, emails, or confidential verbatim quotes."
        )
        if custom_query:
            u_prompt = (
                f"SENSITIVE DOCUMENT CONTENT:\n{pre_scrubbed}\n\n"
                f"MAIN BRAIN REQUEST: {custom_query}\n\n"
                "Provide a clear, accurate, sanitized answer that fulfills the Main Brain's request "
                "without leaking raw secrets, PII, or verbatim paragraphs."
            )
        else:
            u_prompt = (
                f"SENSITIVE DOCUMENT CONTENT:\n{pre_scrubbed}\n\n"
                "Provide:\n"
                "1. A concise 3-5 bullet summary of the core educational/technical topics covered.\n"
                "2. Key concepts that can be used to generate exam or quiz questions.\n"
                "Do NOT output raw credentials, personal names, or secret keys."
            )
        reply = run_local_qwen(sys_prompt, u_prompt, max_tokens=600, target_label=f"digest:{target_path}")
        safe_reply = strip_verbatim_source_lines(offline_scrub_pii(reply, stage="output_digest"), raw_text, target_path=target_path)
    else:
        # Bounded Map-Reduce across up to 6 blocks
        selected_chunks = chunks[:6]
        block_summaries = []
        for ch in selected_chunks:
            c_text = offline_scrub_pii(ch["text"], stage="input_chunk")
            c_sym = ch.get("symbol_name", "block")
            ch_sys = "You are the Raugus Local Privacy Broker AI. Summarize the technical topics in 1-2 concise bullet points."
            ch_u = f"SECTION ({c_sym}):\n{c_text[:3000]}\n\nSummarize the core topics in 1-2 concise bullets."
            b_reply = run_local_qwen(ch_sys, ch_u, max_tokens=200, target_label=f"chunk:{c_sym}")
            b_clean = offline_scrub_pii(b_reply, stage="chunk_summary")
            block_summaries.append(f"• [{c_sym}]: {b_clean}")

        comb_summary = "\n".join(block_summaries)
        consolidation_sys = (
            "You are the Raugus Local Privacy Broker AI. Combine section summaries into an organized topic outline. "
            "Never output raw passwords, personal names, or verbatim quotes."
        )
        consolidation_u = (
            f"SECTION SUMMARIES:\n{comb_summary}\n\n"
            "Produce an organized 3-5 bullet topic outline of the material covered."
        )
        reply = run_local_qwen(consolidation_sys, consolidation_u, max_tokens=600, target_label=f"digest_consolidation:{target_path}")
        combined_raw = "\n".join(c["text"] for c in selected_chunks)
        safe_reply = strip_verbatim_source_lines(offline_scrub_pii(reply, stage="output_digest"), combined_raw, target_path=target_path)

    return {
        "status": "OK",
        "target": target_path,
        "files": files,
        "provenance": {
            "target_type": meta.get("target_type"),
            "tag_id": meta.get("tag_id"),
            "content_hash": meta.get("content_hash"),
            "line_span": meta.get("line_span"),
            "blocks_processed": len(chunks),
        },
        "local_model": "qwen2.5-1.5b-instruct-q4_k_m (CPU Ephemeral)",
        "response": safe_reply,
    }


def generate_exam_questions(target_path: str, count: int = 5, custom_query: str = None) -> dict:
    if is_exfiltration_query(custom_query):
        reason = f"[SECURITY_AUDIT] [EXFILTRATION_BLOCKED] Online model attempted forbidden verbatim/raw extraction query in exam mode on '{target_path}': {custom_query}"
        log_siem_event(
            level="ERROR",
            message=reason,
            module_name="local_brain_broker",
            logger_name="security.local_brain_broker",
        )
        SwarmFlowLogger.log_intrusion_alert(
            modder_id="MainCloudBrain",
            agent_id="ExfiltrationQueryGuard",
            target_namespace=target_path,
            reason=reason,
        )
        return {
            "status": "BLOCKED_EXFILTRATION_ATTEMPT",
            "error": "Raugus Local Broker: Requests for verbatim or raw source dumps are strictly forbidden. Ask for synthesized summaries or exam questions only.",
        }

    meta = resolve_broker_target(target_path)
    if meta.get("status") != "OK":
        return {
            "status": meta.get("status", "ERROR"),
            "target": target_path,
            "error": meta.get("error", "Failed to resolve target."),
        }

    chunks = chunk_target_by_ast(meta, max_chunk_chars=6000)
    if not chunks:
        return {
            "status": "EMPTY",
            "target": target_path,
            "files": [],
            "error": "No readable documents found in the sensitive directory to generate exam questions from.",
            "provenance": {
                "target_type": meta.get("target_type"),
                "tag_id": meta.get("tag_id"),
                "content_hash": meta.get("content_hash"),
                "line_span": meta.get("line_span"),
                "blocks_processed": 0,
            },
        }

    files = [c.get("symbol_name") or c.get("key") for c in chunks]

    # Distribute questions across blocks if multi-block
    if len(chunks) == 1:
        raw_text = chunks[0]["text"]
        pre_scrubbed = offline_scrub_pii(raw_text, stage="input_exam")
        sys_prompt = (
            "You are the Raugus Local Exam Broker AI. Read the sensitive source material and generate "
            "educational exam questions in strict JSON format. Never include raw passwords, API keys, "
            "or personal PII in the questions or explanations. Output ONLY valid JSON."
        )
        extra_instructions = f"\nAdditional instructions from Main Brain: {custom_query}\n" if custom_query else ""
        u_prompt = (
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
            '- For "dropdown_blank", include exactly one "[BLANK]" in "text", an "options" list, and string "correct_text".\n'
            "- Return ONLY the raw JSON object without markdown code fences."
        )
        reply = run_local_qwen(sys_prompt, u_prompt, max_tokens=1400, target_label=f"exam:{target_path}")
        safe_reply = strip_verbatim_source_lines(offline_scrub_pii(reply, stage="output_exam"), raw_text, target_path=target_path)

        json_match = re.search(r"\{[\s\S]*\}", safe_reply)
        parsed_questions = None
        if json_match:
            try:
                parsed_questions = json.loads(json_match.group(0))
                if isinstance(parsed_questions, dict) and "questions" in parsed_questions:
                    for q in parsed_questions["questions"]:
                        q["source_tag_id"] = chunks[0].get("tag_id")
                        q["source_content_hash"] = chunks[0].get("content_hash")
                        q["source_symbol"] = chunks[0].get("symbol_name")
            except Exception:
                parsed_questions = None
    else:
        # Multi-block progressive question distribution
        target_count = max(1, count)
        step = max(1, len(chunks) // target_count)
        selected_chunks = [chunks[i] for i in range(0, len(chunks), step)][:target_count]
        all_q_list = []
        for ch in selected_chunks:
            ch_raw = ch["text"]
            ch_scrub = offline_scrub_pii(ch_raw, stage="input_exam_block")
            ch_sym = ch.get("symbol_name", "section")
            b_sys = "You are the Raugus Local Exam Broker AI. Output strictly valid JSON."
            b_u = (
                f"SOURCE MATERIAL ({ch_sym}):\n{ch_scrub[:3000]}\n\n"
                "Generate exactly 1 high-quality multiple_choice question testing a concept from this material. "
                "Output ONLY a JSON object with schema: {\"questions\": [{\"type\": \"multiple_choice\", \"text\": \"...\", \"options\": [\"...\"], \"correct_index\": 0, \"explanation\": \"...\"}]}"
            )
            b_reply = run_local_qwen(b_sys, b_u, max_tokens=400, target_label=f"exam_block:{ch_sym}")
            b_safe = strip_verbatim_source_lines(offline_scrub_pii(b_reply, stage="output_exam"), ch_raw, target_path=target_path)
            j_match = re.search(r"\{[\s\S]*\}", b_safe)
            if j_match:
                try:
                    obj = json.loads(j_match.group(0))
                    for q in obj.get("questions", []):
                        q["source_tag_id"] = ch.get("tag_id")
                        q["source_content_hash"] = ch.get("content_hash")
                        q["source_symbol"] = ch.get("symbol_name")
                        all_q_list.append(q)
                except Exception:
                    pass

        parsed_questions = {"questions": all_q_list} if all_q_list else None
        safe_reply = json.dumps(parsed_questions) if parsed_questions else "Failed to parse questions."

    return {
        "status": "OK",
        "target": target_path,
        "files": files,
        "provenance": {
            "target_type": meta.get("target_type"),
            "tag_id": meta.get("tag_id"),
            "content_hash": meta.get("content_hash"),
            "line_span": meta.get("line_span"),
            "blocks_processed": len(chunks),
        },
        "local_model": "qwen2.5-1.5b-instruct-q4_k_m (CPU Ephemeral)",
        "exam_payload": parsed_questions if parsed_questions else safe_reply,
    }


def generate_query_answer(target_path: str, query: str = None) -> dict:
    """
    Dedicated Q&A broker: answers targeted questions from the Main Cloud Brain
    by selecting the most relevant AST block(s) and running localized inference.
    """
    if is_exfiltration_query(query):
        reason = f"[SECURITY_AUDIT] [EXFILTRATION_BLOCKED] Online model attempted forbidden verbatim/raw extraction query in query mode on '{target_path}': {query}"
        log_siem_event(
            level="ERROR",
            message=reason,
            module_name="local_brain_broker",
            logger_name="security.local_brain_broker",
        )
        SwarmFlowLogger.log_intrusion_alert(
            modder_id="MainCloudBrain",
            agent_id="ExfiltrationQueryGuard",
            target_namespace=target_path,
            reason=reason,
        )
        return {
            "status": "BLOCKED_EXFILTRATION_ATTEMPT",
            "error": "Raugus Local Broker: Requests for verbatim or raw source dumps are strictly forbidden. Ask for synthesized answers or summaries only.",
        }

    if not query:
        return generate_digest(target_path, custom_query=None)

    meta = resolve_broker_target(target_path)
    if meta.get("status") != "OK":
        return {
            "status": meta.get("status", "ERROR"),
            "target": target_path,
            "error": meta.get("error", "Failed to resolve target."),
        }

    chunks = chunk_target_by_ast(meta, max_chunk_chars=6000)
    if not chunks:
        return {
            "status": "EMPTY",
            "target": target_path,
            "error": "No readable content found in the target to answer query.",
            "provenance": {
                "target_type": meta.get("target_type"),
                "tag_id": meta.get("tag_id"),
                "content_hash": meta.get("content_hash"),
                "line_span": meta.get("line_span"),
                "blocks_processed": 0,
            },
        }

    # Select top 1-2 chunks relevant to query keywords
    stop_words = {"the", "a", "an", "in", "to", "for", "of", "and", "or", "what", "how", "why", "is", "are"}
    q_tokens = [t.lower() for t in re.findall(r'[a-zA-Z0-9_]+', query) if t.lower() not in stop_words and len(t) >= 3]

    if len(chunks) == 1:
        selected_chunks = chunks
    else:
        scored = []
        for ch in chunks:
            sym_name = (ch.get("symbol_name") or "").lower()
            text_lower = ch.get("text", "").lower()
            score = 0
            for tok in q_tokens:
                if tok in sym_name:
                    score += 30
                if tok in text_lower:
                    score += 5
            scored.append((score, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected_chunks = [x[1] for x in scored[:2]]

    context_snippets = []
    for sc in selected_chunks:
        c_clean = offline_scrub_pii(sc["text"], stage="input_query")
        sym = sc.get("symbol_name") or sc.get("tag_id") or "block"
        context_snippets.append(f"--- CONTEXT BLOCK ({sym}) ---\n{c_clean[:3500]}")

    full_context = "\n\n".join(context_snippets)

    sys_prompt = (
        "You are the Raugus Local Privacy Broker AI running offline on the user's machine. "
        "Answer the Main Cloud Brain's specific technical or educational query based strictly on the provided context block(s). "
        "Provide a direct, factual, and concise answer without leaking raw passwords, API keys, or personal PII. "
        "Do NOT dump verbatim code lines or paragraphs."
    )
    user_prompt = (
        f"{full_context}\n\n"
        f"QUESTION: {query}\n\n"
        "Provide a clear, accurate, and sanitized answer to the question based on the context above."
    )

    reply = run_local_qwen(sys_prompt, user_prompt, max_tokens=700, target_label=f"query:{target_path}")
    raw_combined = "\n".join(sc["text"] for sc in selected_chunks)
    safe_reply = strip_verbatim_source_lines(offline_scrub_pii(reply, stage="output_query"), raw_combined, target_path=target_path)

    return {
        "status": "OK",
        "target": target_path,
        "mode": "query",
        "query": query,
        "provenance": {
            "target_type": meta.get("target_type"),
            "tag_id": meta.get("tag_id"),
            "content_hash": meta.get("content_hash"),
            "line_span": meta.get("line_span"),
            "blocks_processed": len(selected_chunks),
            "selected_blocks": [sc.get("symbol_name") or sc.get("tag_id") for sc in selected_chunks],
        },
        "local_model": "qwen2.5-1.5b-instruct-q4_k_m (CPU Ephemeral)",
        "response": safe_reply,
    }


def triage_symbol_keys(target_or_query: str, custom_query: str = None) -> dict:
    """
    Zero-Cost AST triage: Resolves target symbols/invariants from the local Raugus Map
    without consuming any paid cloud LLM tokens. Ranks symbols using deterministic
    keyword/path matching and returns compact metadata with provenance tags.
    """
    phonebook = getattr(resolver, "phonebook", {})

    target_norm = (target_or_query or "").strip().lower()
    query_norm = (custom_query or "").strip().lower()

    raw_tokens = re.findall(r'[a-zA-Z0-9_]+', f"{target_norm} {query_norm}")
    stop_words = {"the", "a", "an", "in", "to", "for", "of", "and", "or", "py", "json", "md", "endpoint"}
    search_tokens = [t for t in raw_tokens if t not in stop_words and len(t) >= 2]
    query_tokens = [t for t in re.findall(r'[a-zA-Z0-9_]+', query_norm) if t not in stop_words and len(t) >= 2]

    scored = []
    for key, entry in phonebook.items():
        if ".backups." in key or "/backups/" in entry.get("real_path", ""):
            continue

        sym_name = (entry.get("symbol_name") or "").lower()
        key_lower = key.lower()
        path_lower = (entry.get("real_path") or "").lower()
        tag_id = (entry.get("id") or "").lower()
        etype = entry.get("type")

        score = 0
        if target_norm and (target_norm == key_lower or target_norm == tag_id):
            score += 100
        elif target_norm and target_norm in key_lower:
            score += 40

        if etype in ("function", "async_function", "class", "method"):
            score += 25
        elif etype == "section":
            score -= 10

        for token in query_tokens:
            if token == sym_name:
                score += 50
            elif sym_name.startswith(token) or f"_{token}" in sym_name:
                score += 40
            elif token in sym_name:
                score += 20
            if token in key_lower:
                score += 15

        for token in search_tokens:
            if token in key_lower:
                score += 5
            if token in path_lower:
                score += 3

        if score > 0:
            scored.append((score, key, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_matches = []
    for _, key, entry in scored[:3]:
        top_matches.append({
            "key": key,
            "symbol_name": entry.get("symbol_name"),
            "line_span": [entry.get("start_line"), entry.get("end_line")],
            "tag_id": entry.get("id"),
            "content_hash": entry.get("content_hash"),
            "required_tier": entry.get("required_tier", 5),
        })

    recommendation = (
        f"Inspect using read_by_key('{top_matches[0]['key']}') or get_block_by_tag('{top_matches[0]['tag_id']}')"
        if top_matches else "No symbol match found. Consider broader search_keys query."
    )

    return {
        "status": "OK",
        "target": target_or_query,
        "query": custom_query,
        "mode": "triage",
        "provenance": {
            "target_type": "ast_symbol_index",
            "matches_found": len(top_matches),
            "top_match_tag": top_matches[0]["tag_id"] if top_matches else None,
        },
        "matches": top_matches,
        "recommendation": recommendation,
    }


def main():
    parser = argparse.ArgumentParser(description="Raugus Local Brain Privacy Broker")
    parser.add_argument("--target", required=True, help="Sensitive file, directory path, VFS key, or tag ID")
    parser.add_argument(
        "--mode",
        choices=["digest", "exam", "query", "triage"],
        default="digest",
        help="Mode: 'digest' for topic summary, 'exam' for exam JSON generation, 'query' for Q&A, 'triage' for AST symbol triage",
    )
    parser.add_argument("--query", default=None, help="Specific prompt/instructions from the Main Brain")
    parser.add_argument("--count", type=int, default=5, help="Number of exam questions to generate")
    args = parser.parse_args()

    if args.mode == "exam":
        res = generate_exam_questions(args.target, count=args.count, custom_query=args.query)
    elif args.mode == "triage":
        res = triage_symbol_keys(args.target, custom_query=args.query)
    elif args.mode == "query":
        res = generate_query_answer(args.target, query=args.query)
    else:
        res = generate_digest(args.target, custom_query=args.query)

    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
