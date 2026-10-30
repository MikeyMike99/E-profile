#!/usr/bin/env python3
"""
=============================================================================
   DEVCORE WORKSPACE PIPELINE FORWARDER (workspace_pipeline.py)
=============================================================================
Transparently forwards pipeline commands from DevCore or playground to the
central cross-repository pipeline orchestrator in Central_Docs.

Usage:
  python3 scripts/workspace_pipeline.py --status
  python3 scripts/workspace_pipeline.py --audit
  python3 scripts/workspace_pipeline.py --commit "your commit message"
=============================================================================
"""

import sys
import subprocess
from pathlib import Path

CENTRAL_PIPELINE = Path(__file__).resolve().parent.parent.parent / "Central_Docs" / "scripts" / "workspace_pipeline.py"

if not CENTRAL_PIPELINE.exists():
    print(f"[FATAL] Central pipeline script not found at: {CENTRAL_PIPELINE}")
    sys.exit(1)

res = subprocess.run([sys.executable, str(CENTRAL_PIPELINE)] + sys.argv[1:])
sys.exit(res.returncode)
