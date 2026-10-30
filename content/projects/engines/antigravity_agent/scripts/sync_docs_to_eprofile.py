#!/usr/bin/env python3
"""
Sync Docs to E-Profile Forwarder
================================
Delegates all documentation synchronization and catalog generation to the
canonical Central_Docs script to guarantee single-source-of-truth consistency.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    repo_root = Path(__file__).resolve().parent.parent
    canonical_script = repo_root.parent / "Central_Docs" / "scripts" / "sync_to_eprofile.py"
    if not canonical_script.exists():
        print(f"[ERROR] Canonical synchronization script not found at: {canonical_script}")
        sys.exit(1)
    cmd = [sys.executable, str(canonical_script)] + sys.argv[1:]
    res = subprocess.run(cmd)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
