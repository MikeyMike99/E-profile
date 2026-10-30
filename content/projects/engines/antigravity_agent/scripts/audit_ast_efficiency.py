#!/usr/bin/env python3
"""
AST Token Reduction & Efficiency Auditor (audit_ast_efficiency.py)
Automated diagnostic evaluating AST surgical symbol extraction token savings,
latency bounds, and context headroom SLA (>= 80% reduction).
"""

import json
import os
import subprocess
import sys

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BENCHMARK_SCRIPT = os.path.join(DEVCORE_ROOT, "scripts", "benchmark_ast_efficiency.py")


def main():
    json_mode = "--json" in sys.argv
    strict_mode = "--strict" in sys.argv

    cmd = [sys.executable, BENCHMARK_SCRIPT, "--json"]
    proc = subprocess.run(cmd, cwd=DEVCORE_ROOT, text=True, capture_output=True)

    if proc.returncode != 0 and not proc.stdout.strip():
        payload = {
            "audit_id": "ast_efficiency",
            "name": "AST Token Reduction & Efficiency Auditor",
            "status": "FAIL",
            "error": proc.stderr.strip() or "Benchmark subprocess failed",
        }
        if json_mode:
            print(json.dumps(payload, indent=2))
        else:
            print(f"[FAIL] AST Efficiency Audit Error: {payload['error']}")
        sys.exit(1)

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        payload = {
            "audit_id": "ast_efficiency",
            "name": "AST Token Reduction & Efficiency Auditor",
            "status": "FAIL",
            "error": f"Failed to parse benchmark JSON: {str(e)}",
            "raw_output": proc.stdout[:500],
        }
        if json_mode:
            print(json.dumps(payload, indent=2))
        else:
            print(f"[FAIL] AST Efficiency JSON Parse Error: {str(e)}")
        sys.exit(1)

    is_pass = data.get("status") == "PASS" and data.get("avg_reduction_pct", 0) >= data.get("sla_target_pct", 80.0)

    audit_result = {
        "audit_id": "ast_efficiency",
        "name": "AST Token Reduction & Efficiency Auditor",
        "category": "efficiency",
        "status": "PASS" if is_pass else "FAIL",
        "summary": (
            f"Achieved {data.get('avg_reduction_pct', 0)}% average token reduction across "
            f"{data.get('cases_evaluated', 0)} AST targets with {data.get('headroom_multiplier', 0)}x context headroom."
        ),
        "sla_target_pct": data.get("sla_target_pct", 80.0),
        "avg_reduction_pct": data.get("avg_reduction_pct", 0),
        "headroom_multiplier": data.get("headroom_multiplier", 0),
        "total_tokens_spared": data.get("total_tokens_spared", 0),
        "total_full_tokens": data.get("total_full_tokens", 0),
        "total_ast_tokens": data.get("total_ast_tokens", 0),
        "cost_avoidance_usd": data.get("cost_avoidance_usd", 0.0),
        "total_parse_duration_ms": data.get("total_parse_duration_ms", 0.0),
        "cases": data.get("cases", []),
    }

    is_interactive = sys.stdout.isatty() and not json_mode

    if not is_interactive or json_mode:
        print(json.dumps(audit_result, indent=2))
    else:
        status_badge = "[PASS]" if is_pass else "[FAIL]"
        print(f"{status_badge} AST Token Reduction & Efficiency Audit")
        print(f"       Summary: {audit_result['summary']}")
        print(f"       Tokens Spared: {audit_result['total_tokens_spared']:,} / {audit_result['total_full_tokens']:,}")
        print(f"       Cost Avoidance: ${audit_result['cost_avoidance_usd']} USD")
        print(f"       Parse Latency: {audit_result['total_parse_duration_ms']:.2f} ms")

    if strict_mode and not is_pass:
        sys.exit(1)
    sys.exit(0 if is_pass else 1)


if __name__ == "__main__":
    main()
