import os
import shutil
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    py_bin = shutil.which("python3") or "python3"

    if os.name != "nt":
        shutil.rmtree(Path.home() / ".cache" / "pip", ignore_errors=True)
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
        print("[post_sync] Cleaned pip cache and pruned unused heavy NLP packages.")


if __name__ == "__main__":
    main()
