"""devcore_locator - single source of truth for locating the DevCore plugin.

DevCore runs both as a standalone component and as a plugin mounted into the
e_profile host. Before the host can ``import ai_plugin`` it must first find the
DevCore directory on disk. That discovery used to be re-implemented at every
mount point (server.py, bootstrap.py, and the vendored forwarder shims), which
is exactly the kind of copy that drifts. This module centralizes it.

Resolution order (first match wins):
  1. $DEVCORE_PATH            - explicit override
  2. <e_profile>/../DevCore   - sibling checkout (normal dev layout)
  3. ~/DevCore                - home checkout
  4. the vendored forwarder   - content/projects/engines/antigravity_agent

A candidate is accepted only if it exists and contains MARKER ("ai_plugin.py"),
unless require_marker=False.
"""
from __future__ import annotations

import os
import sys
import importlib
from pathlib import Path

MARKER = "ai_plugin.py"


def eprofile_root() -> Path:
    """Directory of the e_profile host (this file lives at its root)."""
    return Path(__file__).resolve().parent


def candidate_dirs() -> list[Path]:
    """Ordered, de-duplicated list of places DevCore might live."""
    root = eprofile_root()
    cands: list[Path] = []
    env = os.environ.get("DEVCORE_PATH")
    if env:
        cands.append(Path(env))
    cands.append(root.parent / "DevCore")
    cands.append(Path.home() / "DevCore")
    cands.append(root / "content" / "projects" / "engines" / "antigravity_agent")

    seen: set[Path] = set()
    out: list[Path] = []
    for c in cands:
        try:
            key = c.resolve()
        except Exception:
            key = c
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def find_devcore(require_marker: bool = True) -> Path | None:
    """Return the first existing candidate (containing MARKER), else None."""
    for c in candidate_dirs():
        if not c.exists():
            continue
        if require_marker and not (c / MARKER).is_file():
            continue
        return c
    return None


def default_clone_target() -> Path:
    """Where bootstrap should clone DevCore to when it is missing."""
    return eprofile_root().parent / "DevCore"


def resolve_devcore() -> Path:
    """Find DevCore, falling back to the default clone target path."""
    found = find_devcore()
    return found if found is not None else default_clone_target()


def mount() -> Path | None:
    """Locate DevCore and prepend it to sys.path so ``import ai_plugin`` works.

    Returns the DevCore path, or None if it could not be found.
    """
    dc = find_devcore()
    if dc is None:
        return None
    p = str(dc)
    if p not in sys.path:
        sys.path.insert(0, p)
    return dc


def load_from(start_file) -> "object | None":
    """Bootstrap helper for deeply-nested forwarder shims.

    Walk upward from ``start_file`` until a directory containing this module is
    found, put it on sys.path, import it, and return the module. Lets a shim
    reach this locator without hard-coding how many parents up the host root is.
    Returns the imported module, or None if not found.
    """
    cur = Path(start_file).resolve()
    for parent in [cur.parent, *cur.parents]:
        if (parent / "devcore_locator.py").is_file():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return importlib.import_module("devcore_locator")
    return None
