"""Where e_profile gets its GitHub token: Bitwarden, never a plain-text file.

  1. GITHUB_TOKEN / GIT_TOKEN environment variable. On PythonAnywhere (no Bitwarden there),
     set it from Bitwarden in the web app's environment, not in a file inside this folder.
  2. Bitwarden, on the owner's machine: `bw get password "<item>"` using the session DevCore's
     Bitwarden bridge keeps unlocked (~/.config/devcore/bw_session) or BW_SESSION.
     Item name: "Siraugga GitHub token" (override with BW_GITHUB_ITEM).

The old gethub_token.txt is no longer read.
"""
import os
import shutil
import subprocess
from pathlib import Path

BW_ITEM = os.environ.get("BW_GITHUB_ITEM", "Siraugga GitHub token")
_cache = {"token": None}


def _bw_session() -> str:
    s = os.environ.get("BW_SESSION", "").strip()
    if s:
        return s
    try:
        return (Path.home() / ".config" / "devcore" / "bw_session").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def github_token() -> str:
    """The GitHub token, or '' when none is available (git then uses 'origin' unauthenticated)."""
    tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GIT_TOKEN") or "").strip()
    if tok:
        return tok
    if _cache["token"] is not None:
        return _cache["token"]
    tok = ""
    bw = shutil.which("bw") or str(Path.home() / ".local" / "bin" / "bw")
    session = _bw_session()
    if session and os.path.exists(bw):
        try:
            env = dict(os.environ, BW_SESSION=session, BW_NOINTERACTION="true")
            r = subprocess.run([bw, "get", "password", BW_ITEM], capture_output=True, text=True, timeout=20, env=env)
            if r.returncode == 0:
                tok = r.stdout.strip()
        except Exception:
            tok = ""
    _cache["token"] = tok
    return tok
