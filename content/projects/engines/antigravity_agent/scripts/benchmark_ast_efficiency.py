#!/usr/bin/env python3
"""
AST Token Reduction & Efficiency Benchmark Suite (benchmark_ast_efficiency.py)
Evaluates empirical token savings, symbol extraction latency, and context headroom
achieved by surgical AST block targeting versus full-module reads.
"""

import argparse
import ast
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

DEFAULT_SLA_PCT = 80.0
DEFAULT_BLENDED_RATE_PER_MTOK = 3.50


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    tokens = re.findall(r"\w+|[^\w\s]", text)
    return max(1, len(tokens))


def extract_ast_symbol(source_code: str, symbol_query: str) -> Tuple[Optional[str], int, int, float]:
    start_time = time.perf_counter()
    tree = ast.parse(source_code)
    lines = source_code.splitlines(keepends=True)

    parts = symbol_query.split(".")
    target_node = None

    if len(parts) == 1:
        target_name = parts[0]
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == target_name:
                target_node = node
                break
    elif len(parts) == 2:
        class_name, method_name = parts
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == method_name:
                        target_node = sub
                        break
                if target_node:
                    break

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    if not target_node:
        return None, 0, 0, elapsed_ms

    s_line = target_node.lineno
    e_line = target_node.end_lineno if hasattr(target_node, "end_lineno") and target_node.end_lineno else s_line
    symbol_text = "".join(lines[max(0, s_line - 1):e_line])
    return symbol_text, s_line, e_line, elapsed_ms


def extract_markdown_section(content: str, heading_pattern: str) -> Tuple[Optional[str], int, int, float]:
    start_time = time.perf_counter()
    lines = content.splitlines(keepends=True)
    headings = list(re.finditer(r"^(#{1,4}\s+.+)$", content, re.MULTILINE))

    match_idx = -1
    for idx, h in enumerate(headings):
        if re.search(heading_pattern, h.group(1), re.IGNORECASE):
            match_idx = idx
            break

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    if match_idx == -1:
        return None, 0, 0, elapsed_ms

    start_char = headings[match_idx].start()
    end_char = headings[match_idx + 1].start() if match_idx + 1 < len(headings) else len(content)
    section_text = content[start_char:end_char]

    s_line = content[:start_char].count("\n") + 1
    e_line = content[:end_char].count("\n")
    return section_text, s_line, e_line, elapsed_ms


BENCHMARK_CASES = [
    {
        "id": "telemetry_engine",
        "type": "python_ast",
        "file": "core/token_telemetry.py",
        "symbol": "get_telemetry_engine",
        "label": "Telemetry Engine Factory",
    },
    {
        "id": "telemetry_record_step",
        "type": "python_ast",
        "file": "core/token_telemetry.py",
        "symbol": "TokenTelemetryEngine.record_live_step",
        "label": "Telemetry Live Step Recorder",
    },
    {
        "id": "routes_api_telemetry",
        "type": "python_ast",
        "file": "core/routes/system.py",
        "symbol": "api_token_telemetry",
        "label": "System Route API Telemetry Handler",
    },
    {
        "id": "audit_registry_builtins",
        "type": "python_ast",
        "file": "core/audit_registry.py",
        "symbol": "AuditRegistry.register_builtin_audits",
        "label": "Audit Registry Builtin Registration",
    },
    {
        "id": "vfs_encrypted_init",
        "type": "python_ast",
        "file": "security/vfs.py",
        "symbol": "EncryptedVFS.__init__",
        "label": "Encrypted VFS Constructor",
    },
    {
        "id": "gemini_hotpatch_rule",
        "type": "markdown_section",
        "file": "GEMINI.md",
        "symbol": r"Zero-Restart In-Memory Reload",
        "label": "GEMINI.md Hot-Patch Specification Section",
    },
]


class ASTEfficiencyBenchmark:
    def __init__(self, repo_root: Optional[str] = None, sla_pct: float = DEFAULT_SLA_PCT):
        self.repo_root = repo_root or DEVCORE_ROOT
        self.sla_pct = sla_pct

    def run_all(self) -> Dict[str, Any]:
        results = []
        total_full_tokens = 0
        total_ast_tokens = 0
        total_duration_ms = 0.0

        for case in BENCHMARK_CASES:
            rel_file = case["file"]
            abs_file = os.path.join(self.repo_root, rel_file)
            if not os.path.exists(abs_file):
                continue

            try:
                with open(abs_file, "r", encoding="utf-8") as f:
                    full_source = f.read()
            except Exception as e:
                continue

            full_lines = len(full_source.splitlines())
            full_chars = len(full_source)
            full_tokens = estimate_tokens(full_source)

            case_type = case["type"]
            sym = case["symbol"]

            if case_type == "python_ast":
                slice_code, s_line, e_line, dur_ms = extract_ast_symbol(full_source, sym)
            elif case_type == "markdown_section":
                slice_code, s_line, e_line, dur_ms = extract_markdown_section(full_source, sym)
            else:
                slice_code, s_line, e_line, dur_ms = None, 0, 0, 0.0

            if slice_code is None:
                continue

            ast_lines = len(slice_code.splitlines())
            ast_chars = len(slice_code)
            ast_tokens = estimate_tokens(slice_code)

            tokens_saved = max(0, full_tokens - ast_tokens)
            reduction_pct = round(((full_tokens - ast_tokens) / full_tokens * 100.0), 2) if full_tokens > 0 else 0.0
            status = "PASS" if reduction_pct >= 75.0 else ("WARN" if reduction_pct >= 50.0 else "FAIL")

            total_full_tokens += full_tokens
            total_ast_tokens += ast_tokens
            total_duration_ms += dur_ms

            results.append({
                "id": case["id"],
                "label": case["label"],
                "target_file": rel_file,
                "symbol": sym,
                "type": case_type,
                "line_span": [s_line, e_line],
                "full_lines": full_lines,
                "full_chars": full_chars,
                "full_tokens": full_tokens,
                "ast_lines": ast_lines,
                "ast_chars": ast_chars,
                "ast_tokens": ast_tokens,
                "tokens_saved": tokens_saved,
                "reduction_pct": reduction_pct,
                "parse_duration_ms": round(dur_ms, 3),
                "status": status,
            })

        cases_evaluated = len(results)
        cases_passed = sum(1 for r in results if r["status"] == "PASS")
        total_tokens_saved = max(0, total_full_tokens - total_ast_tokens)
        avg_reduction = round((total_tokens_saved / total_full_tokens * 100.0), 2) if total_full_tokens > 0 else 0.0
        headroom_mult = round((total_full_tokens / max(1, total_ast_tokens)), 1)
        cost_saved = round((total_tokens_saved / 1_000_000.0) * DEFAULT_BLENDED_RATE_PER_MTOK, 4)

        overall_status = "PASS" if (avg_reduction >= self.sla_pct and cases_evaluated > 0) else "FAIL"

        return {
            "status": overall_status,
            "sla_target_pct": self.sla_pct,
            "avg_reduction_pct": avg_reduction,
            "headroom_multiplier": headroom_mult,
            "total_tokens_spared": total_tokens_saved,
            "total_full_tokens": total_full_tokens,
            "total_ast_tokens": total_ast_tokens,
            "cost_avoidance_usd": cost_saved,
            "cases_evaluated": cases_evaluated,
            "cases_passed": cases_passed,
            "total_parse_duration_ms": round(total_duration_ms, 3),
            "as_of": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "cases": results,
        }


def main():
    parser = argparse.ArgumentParser(description="AST Token Reduction & Efficiency Benchmark Suite")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero status if SLA is not met")
    parser.add_argument("--sla", type=float, default=DEFAULT_SLA_PCT, help="Minimum acceptable reduction percentage")
    parser.add_argument("--verbose", action="store_true", help="Print verbose details")
    args = parser.parse_args()

    bench = ASTEfficiencyBenchmark(sla_pct=args.sla)
    data = bench.run_all()

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"\n{'='*70}")
        print(f" AST Token Reduction & Efficiency Benchmark Summary ")
        print(f"{'='*70}")
        print(f"Status:               {data['status']}")
        print(f"Cases Evaluated:      {data['cases_evaluated']} (Passed: {data['cases_passed']})")
        print(f"Average Reduction:    {data['avg_reduction_pct']}% (SLA Target: >={data['sla_target_pct']}%)")
        print(f"Context Headroom:     {data['headroom_multiplier']}x extension")
        print(f"Full Module Tokens:   {data['total_full_tokens']:,}")
        print(f"AST Surgical Tokens:  {data['total_ast_tokens']:,}")
        print(f"Total Tokens Spared:  {data['total_tokens_spared']:,}")
        print(f"Cost Avoidance:       ${data['cost_avoidance_usd']:.4f} USD (@ ${DEFAULT_BLENDED_RATE_PER_MTOK}/MTok)")
        print(f"Total Parse Latency:  {data['total_parse_duration_ms']:.2f} ms")
        print(f"{'-'*70}")
        for c in data["cases"]:
            print(f"[{c['status']}] {c['label']}:")
            print(f"      Full: {c['full_tokens']} tok ({c['full_lines']} lines) -> AST: {c['ast_tokens']} tok ({c['ast_lines']} lines)")
            print(f"      Reduction: {c['reduction_pct']}% (Saved: {c['tokens_saved']} tok, Parse: {c['parse_duration_ms']} ms)")
        print(f"{'='*70}\n")

    if args.strict and data["status"] != "PASS":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
