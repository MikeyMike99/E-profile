"""
DevCore AI Plugin Forwarder
===========================
Centrally managed in DevCore. Delegates directly to DevCore/ai_plugin.py.
DevCore discovery is centralized in e_profile/devcore_locator.py; this shim
walks up to that locator and falls back to inline discovery if it is absent.
"""

import os
import sys
from pathlib import Path

_dc = None
_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "devcore_locator.py").is_file():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        try:
            import devcore_locator
            _dc = devcore_locator.mount()
        except Exception:
            _dc = None
        break

if _dc is None:
    # Fallback: original inline discovery, kept so the forwarder works even when
    # the host locator cannot be reached.
    _devcore_env = os.environ.get("DEVCORE_PATH")
    _candidates = [
        Path(_devcore_env) if _devcore_env else None,
        _here.parents[4] / "DevCore",
        Path.home() / "DevCore",
    ]
    _canonical_dir = next((c for c in _candidates if c and (c / "ai_plugin.py").is_file()), None)
    if _canonical_dir and str(_canonical_dir) not in sys.path:
        sys.path.insert(0, str(_canonical_dir))

from ai_plugin import *  # noqa: F401, F403
