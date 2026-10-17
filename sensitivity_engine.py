"""
Sensitivity Engine (Silent Zero-Trust Multi-Tier Markdown Filter)

Implements granular, section-by-section sensitivity scoring and silent
rendering across technical documentation without broadcasting confirmation vectors.

Tiers:
  Tier 1 (Public): High-level overviews, problem analysis, architecture concepts, Beginner Q&A.
  Tier 2 (Architectural): Component interactions, diagnostic test benchmarks, failure mode logs.
  Tier 3 (Technical Specs): System schemas, parameters, environment flags, CLI contracts.
  Tier 4 (Proprietary IP): Verbatim production source code, build scripts, engine recipes.
  Tier 5 (Vault Secrets): Cryptographic salting, KMS recovery phrases, raw binary payloads.

Principle of Silent Operation:
  Higher-tier code and sensitive blocks are seamlessly transformed into architectural
  synopses or silently omitted. Zero loud "Access Denied" road blocks.
"""

import re
from typing import Tuple

def score_section(section_text: str, category: str = "") -> int:
    """
    Computes a sensitivity score (1-5) for a specific markdown section.
    Supports explicit annotations (e.g., <!-- sensitivity: 4 --> or [Sensitivity: Tier 4])
    as well as intelligent heuristic scoring.
    """
    sec_lower = section_text.lower()
    has_code = "```" in section_text

    # Explicit author annotation
    tag_match = re.search(r'<!--\s*(?:sensitivity|tier)\s*:\s*([1-5])\s*-->', section_text, re.IGNORECASE)
    if not tag_match:
        tag_match = re.search(r'\[(?:sensitivity|tier)\s*:\s*(?:tier\s*)?([1-5])\]', section_text, re.IGNORECASE)
    if tag_match:
        return int(tag_match.group(1))

    # Tier 5: Critical Secrets & Cryptographic Primitives
    if any(k in sec_lower for k in [
        "kms mnemonic", "seed phrase recovery", "raw salt", "nvda_client_64",
        "b64decode", "thought vector obfuscator", "binary stamper and pe trailer"
    ]):
        return 5

    # Tier 4: Verbatim Production Source Code & Execution Recipes
    if has_code and any(k in sec_lower for k in [
        "source citation", "from-scratch creation", "line-by-line construction",
        "taskkill", "pyinstaller", "add_dll_directory", "ctypes.windll",
        "class sessiontailer", "class opaquevfs", "def "
    ]):
        return 4
    if category in ["manual", "guides"] and has_code:
        return 4

    # Tier 3: Technical Specifications, Configs, and Schemas
    if has_code or any(k in sec_lower for k in [
        "config", "spec", "diagnostic", "benchmark", "setup.iss", "json schema",
        "timing threshold", "cli flags", "supervisor loop"
    ]):
        return 3

    # Tier 2: Architectural Analysis & Why Order Matters
    if any(k in sec_lower for k in [
        "proves", "architecture", "order matters", "workflow", "failure mode",
        "post-mortem", "flowchart", "topology"
    ]):
        return 2

    # Tier 1: Public Educational, Overview, and Q&A
    return 1

def filter_document_by_sensitivity(raw_markdown: str, viewer_tier: int = 1) -> str:
    """
    Silently transforms or omits sections exceeding the viewer's clearance tier.
    """
    if viewer_tier >= 5:
        return raw_markdown

    # Normalize CRLF to LF
    content_norm = raw_markdown.replace("\r\n", "\n")
    
    # Split by H2 markdown headings
    sections = re.split(r"(?m)^(?=## )", content_norm)
    output_sections = []

    for sec in sections:
        score = score_section(sec)
        
        if score <= viewer_tier:
            output_sections.append(sec)
        else:
            # Section exceeds clearance: perform SILENT transformation
            if "```" in sec:
                # Extract section topic
                m_head = re.match(r"##\s+([^(\n]+)", sec)
                topic = m_head.group(1).strip() if m_head else "Production Implementation"
                
                synopsis = (
                    f"\n> **[Implementation Architecture Specification: {topic}]**\n"
                    f"> *In production, this module coordinates validated directory discovery, "
                    f"platform-specific execution boundaries, and zero-trust exception handling. "
                    f"Verbatim implementation details are abstracted in public preview.*\n"
                )
                filtered_sec = re.sub(r"```[a-zA-Z0-9_]*\n[\s\S]*?```", synopsis, sec)
                output_sections.append(filtered_sec)
            else:
                # If pure sensitive text with score >= 4, silently omit
                if score >= 4:
                    pass
                else:
                    output_sections.append(sec)

    return "".join(output_sections)

def compute_document_sensitivity(raw_markdown: str, category: str = "") -> Tuple[int, int]:
    """
    Computes (base_sensitivity, max_sensitivity) for an entire document.
    """
    content_norm = raw_markdown.replace("\r\n", "\n")
    sections = re.split(r"(?m)^(?=## )", content_norm)
    
    scores = [score_section(s, category) for s in sections if s.strip()]
    if not scores:
        return 1, 1
        
    return min(scores), max(scores)
