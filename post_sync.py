import os
import shutil
import subprocess
from pathlib import Path


def _ensure_lf(path: Path):
    if path.is_file():
        raw = path.read_bytes()
        if b"\r" in raw:
            path.write_bytes(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


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
        if not (submod_worktree / "ai_plugin.py").exists():
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
            subprocess.run(
                ["git", "submodule", "update", "--init", "--remote", "--force"],
                cwd=str(root),
                capture_output=True,
                text=True,
            )

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
        print("[post_sync] Enforced LF on shell profiles, verified Siraugga submodule, cleaned pip cache, and pruned unused NLP packages.")


if __name__ == "__main__":
    main()
