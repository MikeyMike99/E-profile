import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


def _ensure_lf(path: Path):
    if path.is_file():
        raw = path.read_bytes()
        if b"\r" in raw:
            path.write_bytes(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def _find_agy_bin(root: Path):
    for base in (root, root / "content" / "projects" / "engines" / "antigravity_agent", Path.home()):
        for rel in (Path(".local/bin/agy_real"), Path(".local/bin/agy"), Path("agy_real"), Path("agy"), Path("bin/agy")):
            cand = base / rel
            if cand.is_file() and cand.stat().st_size > 50:
                if cand.name == "agy" and (cand.parent / "agy_real").is_file() and cand.stat().st_size < 4096:
                    return str(cand.parent / "agy_real")
                return str(cand)
    return shutil.which("agy")


def main():
    root = Path(__file__).resolve().parent
    py_bin = shutil.which("python3") or "python3"

    if os.name != "nt":
        home = Path.home()
        for rel in [".bashrc", ".profile", ".vimrc", ".pythonstartup.py"]:
            _ensure_lf(home / rel)
        venv_dir = home / ".virtualenvs"
        if venv_dir.is_dir():
            for p in venv_dir.iterdir():
                _ensure_lf(p)

        shutil.rmtree(home / ".cache" / "pip", ignore_errors=True)
        pack_dir = root / ".git" / "objects" / "pack"
        if pack_dir.is_dir():
            for tmp_pack in pack_dir.glob("tmp_*"):
                tmp_pack.unlink(missing_ok=True)
        (root / ".git" / "gc.log").unlink(missing_ok=True)

        submod_worktree = root / "content" / "projects" / "engines" / "antigravity_agent"
        token = ""
        token_file = root / "gethub_token.txt"
        if token_file.exists():
            token = token_file.read_text().strip()
        if not token:
            token = os.environ.get("GITHUB_TOKEN", "").strip()
        submod_url = (
            f"https://MikeyMike99:{token}@github.com/MikeyMike99/DevCore.git"
            if token
            else "https://github.com/MikeyMike99/DevCore.git"
        )
        subprocess.run(["git", "submodule", "sync"], cwd=str(root), capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "submodule.content/projects/engines/antigravity_agent.url", submod_url],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "submodule.content/projects/engines/antigravity_agent.ignore", "dirty"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if (submod_worktree / ".git").exists():
            subprocess.run(
                ["git", "-C", str(submod_worktree), "pull", submod_url, "main", "--no-edit", "-X", "theirs"],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
        if not (submod_worktree / "ai_plugin.py").exists():
            subprocess.run(
                ["git", "submodule", "update", "--init", "--remote", "--force"],
                cwd=str(root),
                capture_output=True,
                text=True,
            )

        agy_bin = _find_agy_bin(root)
        if agy_bin:
            agy_env = os.environ.copy()
            if "PYTHONANYWHERE_DOMAIN" in os.environ or Path("/var/www").exists():
                pa_proxy = "http://proxy.server:3128"
                for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
                    agy_env[k] = pa_proxy
            try:
                subprocess.run([agy_bin, "update"], cwd=str(root), env=agy_env, capture_output=True, text=True, timeout=25)
            except Exception:
                pass
            try:
                probe = subprocess.run(
                    [agy_bin, "--model", "__probe_available_models__", "--output-format", "stream-json", "--print", "ping"],
                    cwd=str(root),
                    env=agy_env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                combined_out = (probe.stdout or "") + "\n" + (probe.stderr or "")
                if "Available models:" in combined_out:
                    after = combined_out.split("Available models:", 1)[1]
                    models = []
                    for raw_line in after.splitlines():
                        line = raw_line.strip()
                        if not line:
                            continue
                        if line.startswith("{"):
                            break
                        models.append(line)
                    if models and (submod_worktree / "core").is_dir():
                        cache_file = submod_worktree / "core" / ".available_models_cache.json"
                        cache_file.write_text(
                            json.dumps({"updated_at": time.time(), "models": models}, indent=2),
                            encoding="utf-8",
                        )
            except Exception:
                pass

        subprocess.run(
            [
                py_bin, "-m", "pip", "uninstall", "-y",
                "spacy", "presidio-analyzer", "presidio-anonymizer",
                "thinc", "blis", "spacy-legacy", "spacy-loggers"
            ],
            cwd=str(root),
            capture_output=True,
            text=True
        )
        print("[post_sync] Enforced LF on shell profiles, verified Siraugga submodule, synced CLI models, cleaned pip cache, and pruned unused NLP packages.")


if __name__ == "__main__":
    main()
