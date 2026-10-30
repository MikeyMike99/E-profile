#!/usr/bin/env python3
"""
=============================================================================
   DEVCORE THREAT VECTOR AUDIT FORWARDER (audit_threat_vectors.py)
=============================================================================
Transparently forwards threat vector audit commands to the canonical test
suite in Central_Docs.

Usage:
  python3 scripts/audit_threat_vectors.py
  python3 scripts/audit_threat_vectors.py --json
=============================================================================
"""

import sys
import subprocess
from pathlib import Path

CANONICAL_AUDITOR = Path(__file__).resolve().parent.parent.parent / "Central_Docs" / "scripts" / "audit_threat_vectors.py"

if not CANONICAL_AUDITOR.exists():
    print(f"[FATAL] Canonical audit script not found at: {CANONICAL_AUDITOR}")
    sys.exit(1)

res = subprocess.run([sys.executable, str(CANONICAL_AUDITOR)] + sys.argv[1:])
sys.exit(res.returncode)
