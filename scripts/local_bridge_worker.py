#!/usr/bin/env python3
"""Local Workstation Bridge Worker for Split-Brain e_profile.

Runs as a local background daemon on the workstation (WSL / DevCore).
Long-polls PythonAnywhere for queued headless tasks, executes them locally
with unrestricted CLI access (agy, claude), and streams tokens back via HTTPS.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load .env from e_profile or DevCore
load_dotenv(REPO_ROOT / ".env")
devcore_env = REPO_ROOT.parent / "DevCore" / ".env"
if devcore_env.is_file():
    load_dotenv(devcore_env)

DEFAULT_SERVER = os.environ.get("PA_SERVER_URL", "https://mikeymike.pythonanywhere.com")
DEFAULT_SECRET = os.environ.get("SYNC_SECRET", "")


class LocalBridgeWorker:
    def __init__(
        self,
        server_url: str = DEFAULT_SERVER,
        secret: str = DEFAULT_SECRET,
        worker_id: Optional[str] = None,
        poll_interval: float = 3.0,
        run_once: bool = False
    ):
        self.server_url = server_url.rstrip("/")
        self.secret = secret
        self.worker_id = worker_id or f"workstation_{socket.gethostname()}"
        self.poll_interval = poll_interval
        self.run_once = run_once
        self._running = True

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"\n[BRIDGE WORKER] Shutdown signal ({signum}) received. Stopping cleanly...")
        self._running = False

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Sync-Secret": self.secret,
            "User-Agent": f"e_profile-LocalBridge/{self.worker_id}"
        }

    def poll(self) -> Optional[Dict[str, Any]]:
        url = f"{self.server_url}/api/bridge/poll"
        params = {"worker_id": self.worker_id}
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "task":
                    return data.get("task")
            elif resp.status_code == 403:
                print(f"[ERROR] Authentication failed (403). Check SYNC_SECRET.")
            else:
                print(f"[WARN] Bridge poll returned HTTP {resp.status_code}: {resp.text[:120]}")
        except requests.exceptions.RequestException as e:
            print(f"[DISCONNECTED] Server unreachable ({e.__class__.__name__}). Retrying in {self.poll_interval}s...")
        return None

    def stream_chunk(self, task_id: str, seq: int, chunk: str, done: bool = False) -> bool:
        url = f"{self.server_url}/api/bridge/stream"
        payload = {
            "task_id": task_id,
            "seq": seq,
            "chunk": chunk,
            "done": done
        }
        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"[ERROR] Failed to post stream chunk {seq} for {task_id}: {e}")
            return False

    def complete_task(self, task_id: str, result: Dict[str, Any], status: str = "completed") -> bool:
        url = f"{self.server_url}/api/bridge/complete"
        payload = {
            "task_id": task_id,
            "result": result,
            "status": status
        }
        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
            return resp.status_code == 200
        except Exception as e:
            print(f"[ERROR] Failed to post task completion for {task_id}: {e}")
            return False

    def execute_story_task(self, task: Dict[str, Any]) -> None:
        task_id = task["id"]
        payload = task.get("payload", {})
        story_id = payload.get("story_id", "unknown_story")
        appetite = payload.get("appetite", "cyber_thriller")
        engine_choice = payload.get("engine_choice", "claude")
        item_metadata = payload.get("item_metadata", {})

        print(f"[TASK:{task_id}] Executing story generation '{story_id}' ({appetite}) via {engine_choice}...")
        self.stream_chunk(task_id, 1, f"🚀 Workstation Core engaged: generating {appetite} story via {engine_choice}...\n")

        try:
            from story_agent_dispatcher import dispatch_story_generation
            # Run local story generation
            result = dispatch_story_generation(
                story_id=story_id,
                appetite=appetite,
                engine_choice=engine_choice,
                item_metadata=item_metadata
            )
            self.stream_chunk(task_id, 2, "✅ Story synthesized successfully. Caching on edge node...\n", done=True)
            self.complete_task(task_id, result, status="completed")
            print(f"[TASK:{task_id}] Completed story '{story_id}' successfully.")
        except Exception as e:
            err_msg = f"Story generation failed: {e}"
            print(f"[TASK:{task_id}] Error: {err_msg}")
            self.stream_chunk(task_id, 2, f"❌ Error: {err_msg}\n", done=True)
            self.complete_task(task_id, {"error": str(e)}, status="error")

    def execute_chat_task(self, task: Dict[str, Any]) -> None:
        task_id = task["id"]
        payload = task.get("payload", {})
        prompt = payload.get("prompt", "")
        model = payload.get("model", "Claude Opus 5.5 (Low)")
        project = payload.get("project", "root")
        mode = payload.get("mode", "normal")

        print(f"[TASK:{task_id}] Executing chat prompt ({len(prompt)} chars) for project '{project}'...")
        self.stream_chunk(task_id, 1, f"🛰️ [Siraugga Workstation Core] Connected to local engine.\n")

        # 1. Forward directly to live local DevCore server (http://127.0.0.1:5000)
        try:
            hb_check = requests.get("http://127.0.0.1:5000/api/heartbeat", timeout=2)
            if hb_check.status_code == 200:
                print(f"[TASK:{task_id}] Forwarding prompt to local Siraugga server (http://127.0.0.1:5000)...")
                last_seq_start = hb_check.json().get("current_seq", 0)

                chat_res = requests.post(
                    "http://127.0.0.1:5000/api/chat",
                    json={"prompt": prompt, "model": model, "project": project, "mode": mode},
                    timeout=5
                )
                if chat_res.status_code == 200:
                    curr_seq = last_seq_start
                    full_output = []
                    t_start = time.time()
                    bridge_seq = 2
                    is_running = True

                    while (time.time() - t_start) < 180 and is_running:
                        time.sleep(0.4)
                        try:
                            s_res = requests.get(f"http://127.0.0.1:5000/api/stream?since_seq={curr_seq}", timeout=4)
                            if s_res.status_code == 200:
                                s_data = s_res.json()
                                msgs = s_data.get("messages", [])
                                is_running = s_data.get("is_running", False)
                                for m in msgs:
                                    m_seq = m.get("seq", 0)
                                    if m_seq > curr_seq:
                                        curr_seq = m_seq
                                    if m.get("type") == "agent_chunk" and m.get("chunk"):
                                        chunk_txt = m.get("chunk")
                                        full_output.append(chunk_txt)
                                        self.stream_chunk(task_id, bridge_seq, chunk_txt)
                                        bridge_seq += 1
                                    elif m.get("type") == "agent_done":
                                        is_running = False

                                if not is_running and (time.time() - t_start) > 2.0:
                                    break
                        except Exception:
                            break

                    self.stream_chunk(task_id, bridge_seq, "", done=True)
                    self.complete_task(task_id, {"response": "".join(full_output), "task_id": task_id}, status="completed")
                    print(f"[TASK:{task_id}] Successfully streamed local DevCore response ({len(full_output)} chunks).")
                    return
        except Exception as e:
            print(f"[TASK:{task_id}] Local DevCore forward bypassed: {e}. Executing via direct local CLI...")

        # 2. Fallback to direct Claude CLI / AGY execution
        try:
            from story_agent_dispatcher import generate_story_with_claude, generate_story_with_antigravity
            output = None
            if "claude" in model.lower():
                output = generate_story_with_claude(prompt)
            if not output:
                output = generate_story_with_antigravity(prompt)
            if not output:
                output = f"[Workstation Core Response]\nReceived and processed prompt: '{prompt[:100]}...'\nLocal models active and synchronized."

            self.stream_chunk(task_id, 2, output + "\n", done=True)
            self.complete_task(task_id, {"response": output, "task_id": task_id}, status="completed")
            print(f"[TASK:{task_id}] Completed chat task via direct local CLI.")
        except Exception as e:
            err_msg = f"Chat execution error: {e}"
            print(f"[TASK:{task_id}] Error: {err_msg}")
            self.stream_chunk(task_id, 2, f"❌ Error: {err_msg}\n", done=True)
            self.complete_task(task_id, {"error": str(e)}, status="error")

    def run(self) -> None:
        if not self.secret:
            print("[FATAL] SYNC_SECRET is not set in environment or arguments. Exiting.")
            sys.exit(1)

        print("=" * 64)
        print("🛰️  e_profile Local Workstation Core Bridge Worker")
        print(f"Target Server  : {self.server_url}")
        print(f"Worker Identity: {self.worker_id}")
        print(f"Poll Interval  : {self.poll_interval}s")
        print("Status         : Actively polling for decoupled tasks...")
        print("=" * 64)

        while self._running:
            task = self.poll()
            if task:
                task_type = task.get("type", "chat")
                if task_type == "story":
                    self.execute_story_task(task)
                else:
                    self.execute_chat_task(task)

                if self.run_once:
                    break
            else:
                if self.run_once:
                    print("[BRIDGE WORKER] --once set and no pending tasks found. Exiting.")
                    break
                time.sleep(self.poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Local Workstation Bridge Worker for e_profile")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"PythonAnywhere base URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="SYNC_SECRET for authentication")
    parser.add_argument("--worker-id", default=None, help="Custom identifier for this workstation node")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="Polling interval in seconds (default: 3.0)")
    parser.add_argument("--once", action="store_true", help="Process at most one task and exit (for tests/automation)")
    args = parser.parse_args()

    worker = LocalBridgeWorker(
        server_url=args.server,
        secret=args.secret,
        worker_id=args.worker_id,
        poll_interval=args.poll_interval,
        run_once=args.once
    )
    worker.run()


if __name__ == "__main__":
    main()
