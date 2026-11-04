#!/usr/bin/env python3
"""Remote Sync & Split-Brain Control CLI for e_profile.

Provides unified management for PythonAnywhere deployments:
  1. Instant story batch synchronization via HTTP packages (0s, zero Git locks).
  2. Remote Git pull triggers over authenticated HTTP.
  3. Live bridge status, queue monitoring, and server diagnostics.
  4. Surgical file/folder push without requiring Git commits.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import List, Optional

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")
devcore_env = REPO_ROOT.parent / "DevCore" / ".env"
if devcore_env.is_file():
    load_dotenv(devcore_env)

DEFAULT_SERVER = os.environ.get("PA_SERVER_URL", "https://mikeymike.pythonanywhere.com")
DEFAULT_SECRET = os.environ.get("SYNC_SECRET", "")


class RemoteSyncController:
    def __init__(self, server_url: str = DEFAULT_SERVER, secret: str = DEFAULT_SECRET):
        self.server_url = server_url.rstrip("/")
        self.secret = secret

    def _headers(self) -> dict:
        return {
            "X-Sync-Secret": self.secret,
            "User-Agent": "e_profile-RemoteSyncCtl/1.0"
        }

    def check_status(self) -> None:
        print(f"\n🔍 Querying Split-Brain Bridge Status: {self.server_url} ...")
        t0 = time.time()
        try:
            resp = requests.get(f"{self.server_url}/api/bridge/status", headers=self._headers(), timeout=45)
            latency_ms = round((time.time() - t0) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                online = data.get("bridge_online", False)
                status_icon = "🟢" if online else "🟡"
                print("=" * 60)
                print(f"{status_icon} Status         : {data.get('status_label', 'Unknown')}")
                print(f"📡 Edge Host      : {self.server_url} (HTTP {latency_ms}ms)")
                print(f"🛰️ Worker ID      : {data.get('worker_id', 'None')}")
                print(f"⏱️ Last Heartbeat : {data.get('last_seen_sec_ago', 'N/A')}s ago")
                print(f"📥 Pending Tasks  : {data.get('pending_tasks_count', 0)}")
                print(f"⚙️ Active Tasks   : {data.get('processing_tasks_count', 0)}")
                print(f"📦 Total Queued   : {data.get('total_queued', 0)}")
                print("=" * 60)
            else:
                print(f"❌ Server returned HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")

    def trigger_git_pull(self) -> None:
        print(f"\n🔄 Triggering Remote Git Pull on {self.server_url} ...")
        t0 = time.time()
        try:
            resp = requests.post(
                f"{self.server_url}/api/sync/git-pull",
                headers=self._headers(),
                data={"secret": self.secret},
                timeout=60
            )
            elapsed = round(time.time() - t0, 2)
            if resp.status_code == 200:
                data = resp.json()
                print("=" * 60)
                if data.get("status") == "success":
                    print(f"✅ Git Pull Success in {elapsed}s (Exit code: {data.get('returncode')})")
                else:
                    print(f"⚠️ Git Pull Completed with warnings in {elapsed}s (Exit code: {data.get('returncode')})")
                if data.get("reloaded"):
                    print("♻️ PythonAnywhere WSGI automatically touched and reloaded.")
                if data.get("stdout"):
                    print(f"\n[STDOUT]:\n{data.get('stdout').strip()}")
                if data.get("stderr"):
                    print(f"\n[STDERR]:\n{data.get('stderr').strip()}")
                print("=" * 60)
            elif resp.status_code == 403:
                print("❌ Authentication failed (HTTP 403). Ensure SYNC_SECRET matches the server.")
            else:
                print(f"❌ Server returned HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"❌ Git pull request failed: {e}")

    def push_package(self, file_map: dict[str, bytes], label: str = "custom") -> None:
        if not file_map:
            print(f"⚠️ No files found to package for {label}.")
            return

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path, data in file_map.items():
                zf.writestr(rel_path.replace("\\", "/"), data)

        zip_bytes = zip_buf.getvalue()
        print(f"\n📦 Packaging {len(file_map)} file(s) for {label} ({round(len(zip_bytes)/1024, 1)} KB) ...")
        t0 = time.time()
        try:
            files = {"package": (f"{label}_sync.zip", zip_bytes, "application/zip")}
            data = {"secret": self.secret}
            resp = requests.post(
                f"{self.server_url}/api/sync/package",
                headers={"X-Sync-Secret": self.secret},
                data=data,
                files=files,
                timeout=60
            )
            elapsed = round(time.time() - t0, 2)
            if resp.status_code == 200:
                res = resp.json()
                print("=" * 60)
                print(f"✅ Synced {res.get('extracted_count', 0)} files to {self.server_url} in {elapsed}s!")
                if res.get("reloaded"):
                    print("♻️ PythonAnywhere WSGI touched and reloaded.")
                print("Files extracted:")
                for f in res.get("files", [])[:10]:
                    print(f"  • {f}")
                if len(res.get("files", [])) > 10:
                    print(f"  • ... and {len(res.get('files', [])) - 10} more.")
                print("=" * 60)
            else:
                print(f"❌ Package sync failed (HTTP {resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            print(f"❌ Package push failed: {e}")

    def push_stories(self) -> None:
        temp_docs = REPO_ROOT / "cache" / "temp_docs"
        if not temp_docs.is_dir():
            print(f"⚠️ No temp_docs directory found at {temp_docs}")
            return

        file_map = {}
        for p in temp_docs.glob("*.json"):
            rel = f"cache/temp_docs/{p.name}"
            file_map[rel] = p.read_bytes()

        self.push_package(file_map, label="stories")

    def push_path(self, target_rel_path: str) -> None:
        target = (REPO_ROOT / target_rel_path).resolve()
        if not target.exists():
            print(f"❌ Target path does not exist: {target}")
            return

        file_map = {}
        if target.is_file():
            rel = str(target.relative_to(REPO_ROOT)).replace("\\", "/")
            file_map[rel] = target.read_bytes()
        else:
            for p in target.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                    if any(k in rel for k in ('.git', 'profiles.json', '__pycache__', '.env')):
                        continue
                    file_map[rel] = p.read_bytes()

        self.push_package(file_map, label=f"path_{target.name}")

    def enqueue_test_chat(self, prompt: str) -> None:
        print(f"\n📨 Enqueueing test chat prompt to {self.server_url} ...")
        payload = {
            "type": "chat",
            "payload": {
                "prompt": prompt,
                "model": "Gemini 3.8 Flash (High)",
                "timestamp": time.time()
            }
        }
        try:
            resp = requests.post(
                f"{self.server_url}/api/bridge/enqueue",
                headers=self._headers(),
                json=payload,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                task = data.get("task", {})
                print(f"✅ Enqueued Task ID: {task.get('id')} (Status: {task.get('status')})")
                print("Run scripts/local_bridge_worker.py to process it locally!")
            else:
                print(f"❌ Enqueue failed (HTTP {resp.status_code}): {resp.text[:150]}")
        except Exception as e:
            print(f"❌ Enqueue failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Remote Sync & Split-Brain Control CLI for e_profile")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Target URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="SYNC_SECRET for authentication")
    parser.add_argument("--status", action="store_true", help="Check split-brain bridge status and queue health")
    parser.add_argument("--git-pull", action="store_true", help="Trigger remote git pull on PythonAnywhere")
    parser.add_argument("--push-stories", action="store_true", help="Package and push all generated stories in cache/temp_docs/")
    parser.add_argument("--push", help="Push a specific file or directory relative to repository root")
    parser.add_argument("--enqueue-chat", help="Enqueue a test chat prompt to verify the bridge queue")

    args = parser.parse_args()

    ctl = RemoteSyncController(server_url=args.server, secret=args.secret)

    if args.status:
        ctl.check_status()
    elif args.git_pull:
        ctl.trigger_git_pull()
    elif args.push_stories:
        ctl.push_stories()
    elif args.push:
        ctl.push_path(args.push)
    elif args.enqueue_chat:
        ctl.enqueue_test_chat(args.enqueue_chat)
    else:
        ctl.check_status()


if __name__ == "__main__":
    main()
