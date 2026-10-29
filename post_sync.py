import os
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    token = ""
    token_file = root / "gethub_token.txt"
    if token_file.exists():
        token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        token = os.environ.get("GITHUB_TOKEN", "").strip()

    auth_eprofile = f"https://MikeyMike99:{token}@github.com/MikeyMike99/E-profile.git" if token else "origin"
    auth_devcore = f"https://MikeyMike99:{token}@github.com/MikeyMike99/DevCore.git" if token else "https://github.com/MikeyMike99/DevCore.git"

    res = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True
    )
    current_branch = res.stdout.strip() if res.returncode == 0 else "main"

    if current_branch != "main":
        subprocess.run(["git", "-c", "credential.helper=", "checkout", "-B", "main"], cwd=str(root))
        subprocess.run(["git", "-c", "credential.helper=", "branch", "-D", "clean-main"], cwd=str(root))
        subprocess.run(["git", "-c", "credential.helper=", "push", auth_eprofile, "--delete", "clean-main"], cwd=str(root))
        print("[post_sync] Switched server to single branch 'main' and pruned 'clean-main'.")

    subprocess.run(["git", "-c", "credential.helper=", "submodule", "sync"], cwd=str(root))
    subprocess.run(
        ["git", "-c", "credential.helper=", "config", "submodule.content/projects/engines/antigravity_agent.url", auth_devcore],
        cwd=str(root)
    )
    subprocess.run(
        ["git", "-c", "credential.helper=", "submodule", "update", "--init", "--remote", "--force"],
        cwd=str(root)
    )
    print("[post_sync] Verified DevCore submodule on 'main'.")


if __name__ == "__main__":
    main()
