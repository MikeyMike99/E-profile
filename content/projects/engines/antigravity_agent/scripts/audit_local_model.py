#!/usr/bin/env python3
"""
Local Model Service & Scalability Diagnostic Suite
Comprehensive automated diagnostic evaluating local Qwen 2.5 intent parsing, dynamic file size scalability, path security, and tool call extraction.
"""

import os
import subprocess
import sys

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BENCHMARK_SCRIPT = os.path.join(DEVCORE_ROOT, "scripts", "benchmark_local_model.py")


def main():
    cmd = [sys.executable, BENCHMARK_SCRIPT, "--unit-only", "--fuzz-intents", "--json"]

    for arg in sys.argv[1:]:
        if arg not in cmd:
            cmd.append(arg)

    proc = subprocess.run(cmd, cwd=DEVCORE_ROOT, text=True, capture_output=False)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
