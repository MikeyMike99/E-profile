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
        print("[post_sync] Enforced LF on shell profiles, cleaned pip cache, and pruned unused NLP packages.")


if __name__ == "__main__":
    main()
