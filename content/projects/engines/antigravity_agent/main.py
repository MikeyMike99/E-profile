"""
Siraugga / DevCore Antigravity Agent Node
=========================================
Centralized execution forwarder for the Siraugga framework.
The core agent engine, runtime, and sandbox are centrally managed in DevCore
and dynamically mounted into the host application via ai_plugin.py.
DevCore discovery is centralized in e_profile/devcore_locator.py.
"""

import os
import sys
from pathlib import Path

DEVCORE_DIR = None
_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "devcore_locator.py").is_file():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        try:
            import devcore_locator
            DEVCORE_DIR = devcore_locator.mount()
        except Exception:
            DEVCORE_DIR = None
        break

if DEVCORE_DIR is None:
    # Fallback: original inline discovery.
    _devcore_env = os.environ.get("DEVCORE_PATH")
    if _devcore_env and Path(_devcore_env).is_dir():
        DEVCORE_DIR = Path(_devcore_env)
    else:
        DEVCORE_DIR = _here.parents[4] / "DevCore"
        if not DEVCORE_DIR.is_dir():
            DEVCORE_DIR = Path.home() / "DevCore"
    if DEVCORE_DIR.is_dir() and str(DEVCORE_DIR) not in sys.path:
        sys.path.insert(0, str(DEVCORE_DIR))

if __name__ == "__main__":
    try:
        from core.server import app
        print("DevCore Antigravity Agent active.")
    except ImportError:
        print("DevCore engine ready (mounted via e_profile server).")
