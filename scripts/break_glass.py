#!/usr/bin/env python3
"""
DEVCORE & E-PROFILE BREAK-GLASS REMOTE CLI CLIENT
Emergency command & control client for managing PythonAnywhere and remote WSGI servers
even when the main web application has completely crashed.

Usage:
    python3 break_glass.py status
    python3 break_glass.py ls [path]
    python3 break_glass.py cat <remote_path>
    python3 break_glass.py put <local_file> [remote_path]
    python3 break_glass.py pull <remote_path> [local_path]
    python3 break_glass.py edit <remote_path>
    python3 break_glass.py rm <remote_path>
    python3 break_glass.py exec "<command>"
    python3 break_glass.py rollback
    python3 break_glass.py sync
    python3 break_glass.py cleanup
    python3 break_glass.py reload
    python3 break_glass.py logs [--lines N]
    python3 break_glass.py shell
"""

from __future__ import annotations

import os
import sys
import argparse
import json
import subprocess
import tempfile
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path


def _load_env_secrets() -> dict[str, str]:
    """Auto-discovers secrets and URLs from local .env files without dependencies."""
    secrets = {}
    candidate_paths = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path("/mnt/c/Users/michael/Documents/e_profile/.env"),
        Path("/mnt/c/Users/michael/Documents/DevCore/.env"),
        Path.home() / ".env",
    ]
    for p in candidate_paths:
        if p.is_file():
            try:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in secrets:
                        secrets[k] = v
            except Exception:
                pass
    return secrets


def _format_size(num_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}" if unit != 'B' else f"{num_bytes} B"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


class BreakGlassClient:
    def __init__(self, base_url: str, token: str, timeout: int = 35):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        if not self.base_url.startswith("http://") and not self.base_url.startswith("https://"):
            self.base_url = f"https://{self.base_url}"

    def send_request(self, payload: dict) -> dict:
        """Sends a JSON request to the remote break-glass endpoint."""
        url = f"{self.base_url}/__breakglass__?format=json"
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "DevCore-BreakGlass-Client/1.0"
        }
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_text = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(resp_text)
                except Exception:
                    return {"status": "raw", "content": resp_text}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                err_msg = err_json.get("message") or err_json.get("error") or str(e)
            except Exception:
                err_msg = err_body[:300] if err_body else str(e)
            return {"status": "error", "code": e.code, "message": f"HTTP {e.code}: {err_msg}"}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {e}"}

    def cmd_status(self) -> None:
        print(f"\n📡 Querying Break-Glass Status: {self.base_url} ...")
        res = self.send_request({"action": "status"})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return

        is_crashed = res.get("server_state") == "crashed"
        git = res.get("git", {})
        quota = res.get("quota", {})

        print("\n" + "=" * 65)
        print("  🚨 DEVCORE & E-PROFILE BREAK-GLASS STATUS")
        print("=" * 65)
        print(f"  Target Server:  {self.base_url}")
        print(f"  Server State:   {'🔴 CRASHED (Initialization Failed)' if is_crashed else '🟢 HEALTHY / STANDBY'}")
        print(f"  Git Branch:     {git.get('branch', 'unknown')} ({git.get('commit', 'unknown')[:8]})")
        print(f"  Git Status:     {git.get('status', 'clean')}")
        print(f"  Storage Quota:  {quota.get('used_mb', 0)} MB / {quota.get('total_mb', 0)} MB ({quota.get('pct', 0)}%)")
        print(f"  Python Version: {res.get('python_version', 'unknown').split()[0]}")

        if is_crashed or res.get("error_msg") != "None (Clean State)":
            print("\n  [CRITICAL ERROR MESSAGE]")
            print(f"  {res.get('error_msg')}")
            print("\n  [CRASH TRACEBACK]")
            print("-" * 65)
            print(res.get("traceback", "None"))
            print("-" * 65)

        missing_p = res.get("missing_packages", {})
        missing_f = res.get("missing_files", {})
        if any("MISSING" in s for s in missing_p.values()) or any("MISSING" in s for s in missing_f.values()):
            print("\n  [INTEGRITY ISSUES DETECTED]")
            for p, s in missing_p.items():
                if "MISSING" in s:
                    print(f"    - Package missing: {p}")
            for f, s in missing_f.items():
                if "MISSING" in s:
                    print(f"    - File/Directory missing: {f}")
        print("=" * 65 + "\n")

    def cmd_ls(self, rel_path: str = "") -> None:
        res = self.send_request({"action": "ls", "path": rel_path})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return

        entries = res.get("entries", [])
        curr = res.get("path", "")
        print(f"\n📂 Directory: {self.base_url} / {curr or '[root]'} ({len(entries)} items)")
        print("-" * 75)
        print(f"{'TYPE':<6} {'SIZE':<12} {'MODIFIED':<18} {'NAME'}")
        print("-" * 75)
        for e in entries:
            t = "DIR" if e.get("is_dir") else "FILE"
            sz = e.get("size_human", "-")
            m = e.get("mtime_str", "-")
            name = e.get("name") + ("/" if e.get("is_dir") else "")
            print(f"{t:<6} {sz:<12} {m:<18} {name}")
        print("-" * 75 + "\n")

    def cmd_cat(self, remote_path: str) -> None:
        res = self.send_request({"action": "cat", "path": remote_path})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        content = res.get("content", "")
        print(content)

    def cmd_put(self, local_path: str, remote_path: str = "") -> None:
        loc = Path(local_path)
        if not loc.is_file():
            print(f"❌ Local file does not exist: {local_path}")
            return
        r_path = remote_path if remote_path else loc.name
        content = loc.read_text(encoding="utf-8", errors="replace")
        print(f"⬆️  Uploading {loc} -> {r_path} ({len(content)} bytes)...")
        res = self.send_request({"action": "write", "path": r_path, "content": content, "reload": True})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(f"✅ Success: {res.get('message')}")
        if res.get("backed_up"):
            print("   (Automated remote backup created before overwrite)")
        if res.get("reloaded"):
            print("   (Remote WSGI reload triggered)")

    def cmd_pull(self, remote_path: str, local_path: str = "") -> None:
        print(f"⬇️  Downloading {remote_path} from remote...")
        res = self.send_request({"action": "cat", "path": remote_path})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        content = res.get("content", "")
        dest = Path(local_path) if local_path else Path(Path(remote_path).name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"✅ Downloaded to {dest} ({len(content)} bytes)")

    def cmd_edit(self, remote_path: str) -> None:
        print(f"⬇️  Fetching {remote_path} for interactive editing...")
        res = self.send_request({"action": "cat", "path": remote_path})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return

        orig_content = res.get("content", "")
        suffix = Path(remote_path).suffix or ".txt"
        with tempfile.NamedTemporaryFile("w+", suffix=suffix, delete=False, encoding="utf-8") as tf:
            tf.write(orig_content)
            temp_path = tf.name

        editor = os.environ.get("EDITOR") or ("nano" if sys.platform != "win32" else "notepad")
        try:
            subprocess.run([editor, temp_path], check=True)
            new_content = Path(temp_path).read_text(encoding="utf-8")
            if new_content == orig_content:
                print("ℹ️  No changes made. Aborting upload.")
            else:
                print(f"⬆️  Uploading updated {remote_path}...")
                upload_res = self.send_request({
                    "action": "write",
                    "path": remote_path,
                    "content": new_content,
                    "reload": True
                })
                if upload_res.get("status") == "error":
                    print(f"❌ Error: {upload_res.get('message')}")
                else:
                    print(f"✅ Updated and deployed: {remote_path}")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def cmd_rm(self, remote_path: str) -> None:
        confirm = input(f"⚠️  Are you sure you want to delete '{remote_path}' on remote server? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return
        res = self.send_request({"action": "rm", "path": remote_path})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(f"✅ {res.get('message')}")

    def cmd_exec(self, cmd_str: str) -> None:
        print(f"\n⚡ Executing on remote: {cmd_str} ...")
        res = self.send_request({"action": "exec", "cmd": cmd_str})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        code = res.get("returncode", 0)
        stdout = res.get("stdout", "")
        stderr = res.get("stderr", "")
        print(f"[Exit Code: {code}]")
        if stdout:
            print(stdout)
        if stderr:
            print(f"STDERR:\n{stderr}", file=sys.stderr)

    def cmd_rollback(self) -> None:
        confirm = input("⚠️  Roll back 1 Git commit (HEAD~1) on remote server? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return
        print("⏪ Reverting commit and touching WSGI config...")
        res = self.send_request({"action": "rollback"})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(f"✅ {res.get('message')}")
        if res.get("output"):
            print(res.get("output"))

    def cmd_sync(self) -> None:
        print("⚡ Triggering remote 2-way Git pull and auto-restart...")
        res = self.send_request({"action": "pull_and_restart"})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(f"✅ {res.get('message')}")
        if res.get("error"):
            print(f"⚠️  Note: {res.get('error')}")

    def cmd_cleanup(self) -> None:
        print("🧹 Running remote disk quota cleanup...")
        res = self.send_request({"action": "cleanup"})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(f"✅ {res.get('message')}")

    def cmd_reload(self) -> None:
        print("🔄 Touching remote WSGI reload configuration...")
        res = self.send_request({"action": "reload"})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(f"✅ {res.get('message')}")

    def cmd_logs(self) -> None:
        print("📜 Fetching remote error logs...")
        res = self.send_request({"action": "logs"})
        if res.get("status") == "error":
            print(f"❌ Error: {res.get('message')}")
            return
        print(res.get("logs", "No logs returned."))

    def cmd_shell(self) -> None:
        print("\n" + "=" * 65)
        print(f"  🔥 DEVCORE & E-PROFILE BREAK-GLASS INTERACTIVE SHELL")
        print(f"  Connected to: {self.base_url}")
        print("  Type 'help' for commands, 'exit' or 'quit' to close.")
        print("=" * 65 + "\n")

        while True:
            try:
                line = input("breakglass> ").strip()
                if not line:
                    continue
                if line.lower() in ["exit", "quit", "q"]:
                    print("Exiting break-glass shell.")
                    break
                if line.lower() == "help":
                    print("""
Available Shell Commands:
    status                 Check health, crash logs, git state, disk quota
    ls [path]              List remote files and folders
    cat <path>             Read a remote file
    put <local> [remote]   Upload a local file
    pull <remote> [local]  Download a remote file
    edit <path>            Edit a remote file in local editor
    rm <path>              Delete a remote file
    exec <command>         Execute arbitrary shell command on remote server
    rollback               Instantly revert 1 commit (HEAD~1) & reload
    sync                   Force git pull origin/main & restart
    cleanup                Purge disk caches & free PythonAnywhere quota
    reload                 Touch WSGI file to restart worker
    logs                   View recent system & error logs
    exit / quit            Exit shell
""")
                    continue

                parts = line.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd == "status":
                    self.cmd_status()
                elif cmd == "ls":
                    self.cmd_ls(arg)
                elif cmd == "cat":
                    if not arg:
                        print("Usage: cat <remote_path>")
                    else:
                        self.cmd_cat(arg)
                elif cmd == "put":
                    subparts = arg.split(maxsplit=1)
                    if not subparts:
                        print("Usage: put <local_file> [remote_path]")
                    else:
                        loc = subparts[0]
                        rem = subparts[1] if len(subparts) > 1 else ""
                        self.cmd_put(loc, rem)
                elif cmd == "pull":
                    subparts = arg.split(maxsplit=1)
                    if not subparts:
                        print("Usage: pull <remote_path> [local_path]")
                    else:
                        rem = subparts[0]
                        loc = subparts[1] if len(subparts) > 1 else ""
                        self.cmd_pull(rem, loc)
                elif cmd == "edit":
                    if not arg:
                        print("Usage: edit <remote_path>")
                    else:
                        self.cmd_edit(arg)
                elif cmd == "rm":
                    if not arg:
                        print("Usage: rm <remote_path>")
                    else:
                        self.cmd_rm(arg)
                elif cmd == "exec":
                    if not arg:
                        print("Usage: exec <command>")
                    else:
                        self.cmd_exec(arg)
                elif cmd == "rollback":
                    self.cmd_rollback()
                elif cmd == "sync":
                    self.cmd_sync()
                elif cmd == "cleanup":
                    self.cmd_cleanup()
                elif cmd == "reload":
                    self.cmd_reload()
                elif cmd == "logs":
                    self.cmd_logs()
                else:
                    # Treat unknown commands as remote execution!
                    self.cmd_exec(line)
            except KeyboardInterrupt:
                print("\nType 'exit' to quit.")
            except EOFError:
                print("\nExiting.")
                break


def main():
    parser = argparse.ArgumentParser(description="Break-Glass Remote Console Client")
    parser.add_argument("--url", help="Target URL (e.g. https://mikeymike.pythonanywhere.com)")
    parser.add_argument("--token", help="Admin Token / Secret")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Check server health, crash tracebacks, and disk quota")

    ls_p = subparsers.add_parser("ls", help="List remote directory")
    ls_p.add_argument("path", nargs="?", default="", help="Path relative to repo root")

    cat_p = subparsers.add_parser("cat", help="View remote file")
    cat_p.add_argument("path", help="Path of remote file")

    put_p = subparsers.add_parser("put", help="Upload local file to remote server")
    put_p.add_argument("local_path", help="Local file path")
    put_p.add_argument("remote_path", nargs="?", default="", help="Destination path on remote")

    pull_p = subparsers.add_parser("pull", help="Download remote file to local disk")
    pull_p.add_argument("remote_path", help="Remote file path")
    pull_p.add_argument("local_path", nargs="?", default="", help="Local destination path")

    edit_p = subparsers.add_parser("edit", help="Download, edit locally in $EDITOR, and deploy back")
    edit_p.add_argument("remote_path", help="Remote file path")

    rm_p = subparsers.add_parser("rm", help="Delete remote file")
    rm_p.add_argument("path", help="Remote file path")

    exec_p = subparsers.add_parser("exec", help="Run shell command on remote server")
    exec_p.add_argument("cmd", help="Command string to run")

    subparsers.add_parser("rollback", help="Revert last git commit (HEAD~1) and reload")
    subparsers.add_parser("sync", help="Trigger 2-way git sync and reload")
    subparsers.add_parser("cleanup", help="Run disk quota cleanup protocol")
    subparsers.add_parser("reload", help="Trigger WSGI reload")
    subparsers.add_parser("logs", help="Fetch remote error logs")
    subparsers.add_parser("shell", help="Launch interactive Break-Glass console")

    args = parser.parse_args()

    env_secrets = _load_env_secrets()
    url = args.url or os.environ.get("BREAK_GLASS_URL") or os.environ.get("PYTHONANYWHERE_URL") or env_secrets.get("PYTHONANYWHERE_URL") or "https://mikeymike.pythonanywhere.com"
    token = args.token or os.environ.get("BREAK_GLASS_KEY") or os.environ.get("SYNC_SECRET") or os.environ.get("ADMIN_KEY") or env_secrets.get("SYNC_SECRET") or env_secrets.get("ADMIN_KEY") or ""

    if not token:
        print("❌ Error: No authentication secret found in arguments, environment, or .env files.")
        print("   Specify via --token <KEY> or set SYNC_SECRET / ADMIN_KEY in .env.")
        sys.exit(1)

    client = BreakGlassClient(base_url=url, token=token)

    cmd = args.command or "shell"

    if cmd == "status":
        client.cmd_status()
    elif cmd == "ls":
        client.cmd_ls(args.path)
    elif cmd == "cat":
        client.cmd_cat(args.path)
    elif cmd == "put":
        client.cmd_put(args.local_path, args.remote_path)
    elif cmd == "pull":
        client.cmd_pull(args.remote_path, args.local_path)
    elif cmd == "edit":
        client.cmd_edit(args.remote_path)
    elif cmd == "rm":
        client.cmd_rm(args.path)
    elif cmd == "exec":
        client.cmd_exec(args.cmd)
    elif cmd == "rollback":
        client.cmd_rollback()
    elif cmd == "sync":
        client.cmd_sync()
    elif cmd == "cleanup":
        client.cmd_cleanup()
    elif cmd == "reload":
        client.cmd_reload()
    elif cmd == "logs":
        client.cmd_logs()
    elif cmd == "shell":
        client.cmd_shell()


if __name__ == "__main__":
    main()
