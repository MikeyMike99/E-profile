"""Bridge task queue and connection manager for Split-Brain e_profile architecture.

Coordinates decoupled task execution between the PythonAnywhere web edge
and the local workstation headless core engine.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from config import Config
    ROOT_DIR = Config.ROOT_DIR
except Exception:
    ROOT_DIR = Path(__file__).resolve().parent

CACHE_DIR = ROOT_DIR / "cache"
TEMP_DOCS_DIR = CACHE_DIR / "temp_docs"
BRIDGE_QUEUE_FILE = CACHE_DIR / "bridge_queue.json"


def is_production_server() -> bool:
    """Accurately identifies PythonAnywhere production environment."""
    if os.environ.get("FORCE_BOOTSTRAP_SYNC") == "1":
        return True
    if os.name == "nt":
        return False
    if "WSL_DISTRO_NAME" in os.environ or "WSL_INTEROP" in os.environ or Path("/mnt/c").exists():
        return False
    try:
        proc_ver = Path("/proc/version")
        if proc_ver.exists() and any(k in proc_ver.read_text(encoding="utf-8", errors="ignore").lower() for k in ("microsoft", "wsl")):
            return False
    except Exception:
        pass
    return "PYTHONANYWHERE_DOMAIN" in os.environ or "PYTHONANYWHERE_SITE" in os.environ or Path("/var/www").exists()


class BridgeManager:
    """Thread-safe task queue and status coordinator for split-brain execution."""

    def __init__(self, queue_file: Optional[Path] = None):
        self.queue_file = queue_file or BRIDGE_QUEUE_FILE
        self._lock = threading.Lock()
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        TEMP_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            initial_data = {
                "tasks": [],
                "heartbeat": {"last_seen": 0.0, "worker_id": "", "status": "offline"},
                "streams": {},
                "results": {}
            }
            self._write_state(initial_data)

    def _read_state(self) -> Dict[str, Any]:
        try:
            if self.queue_file.exists():
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {
            "tasks": [],
            "heartbeat": {"last_seen": 0.0, "worker_id": "", "status": "offline"},
            "streams": {},
            "results": {}
        }

    def _write_state(self, state: Dict[str, Any]) -> None:
        try:
            tmp_file = self.queue_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            tmp_file.replace(self.queue_file)
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            state = self._read_state()
            hb = state.get("heartbeat", {})
            last_seen = float(hb.get("last_seen", 0.0))
            now = time.time()
            sec_ago = round(now - last_seen, 1) if last_seen > 0 else 999999.0
            is_online = (now - last_seen) < 45.0

            pending = [t for t in state.get("tasks", []) if t.get("status") == "pending"]
            processing = [t for t in state.get("tasks", []) if t.get("status") == "processing"]

            return {
                "mode": "split_brain",
                "is_production_edge": is_production_server(),
                "bridge_online": is_online,
                "status_label": "Online (Active Core)" if is_online else "Standby (Core Offline)",
                "worker_id": hb.get("worker_id", "none"),
                "last_seen_epoch": last_seen,
                "last_seen_sec_ago": sec_ago,
                "pending_tasks_count": len(pending),
                "processing_tasks_count": len(processing),
                "total_queued": len(state.get("tasks", []))
            }

    def record_heartbeat(self, worker_id: str = "local_core") -> Dict[str, Any]:
        with self._lock:
            state = self._read_state()
            state["heartbeat"] = {
                "last_seen": time.time(),
                "worker_id": worker_id,
                "status": "online"
            }
            self._write_state(state)
            return state["heartbeat"]

    def enqueue_task(self, task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            state = self._read_state()
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            task = {
                "id": task_id,
                "type": task_type,
                "payload": payload,
                "status": "pending",
                "created_at": time.time(),
                "started_at": None,
                "completed_at": None
            }
            tasks = state.setdefault("tasks", [])
            tasks.append(task)
            self._write_state(state)
            return task

    def poll_task(self, worker_id: str = "local_core") -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self._read_state()
            state["heartbeat"] = {
                "last_seen": time.time(),
                "worker_id": worker_id,
                "status": "online"
            }

            tasks = state.setdefault("tasks", [])
            for task in tasks:
                if task.get("status") == "pending":
                    task["status"] = "processing"
                    task["started_at"] = time.time()
                    task["worker_id"] = worker_id
                    self._write_state(state)
                    return task

            self._write_state(state)
            return None

    def append_stream_chunk(self, task_id: str, seq: int, chunk: str, done: bool = False) -> bool:
        with self._lock:
            state = self._read_state()
            streams = state.setdefault("streams", {})
            task_stream = streams.setdefault(task_id, [])
            task_stream.append({
                "seq": seq,
                "chunk": chunk,
                "done": done,
                "timestamp": time.time()
            })
            if len(task_stream) > 1000:
                task_stream = task_stream[-1000:]
                streams[task_id] = task_stream
            self._write_state(state)

        self._relay_to_runtime_stream(task_id, seq, chunk, done)
        return True

    def _relay_to_runtime_stream(self, task_id: str, seq: int, chunk: str, done: bool) -> None:
        try:
            runtime_dir = ROOT_DIR / "cache"
            runtime_stream = runtime_dir / "stream_events.json"
            events = []
            if runtime_stream.is_file():
                try:
                    events = json.loads(runtime_stream.read_text(encoding="utf-8"))
                    if not isinstance(events, list):
                        events = []
                except Exception:
                    events = []

            events.append({
                "seq": seq,
                "task_id": task_id,
                "msg": {"type": "done" if done else "chunk", "content": chunk}
            })
            if len(events) > 500:
                events = events[-500:]
            runtime_stream.write_text(json.dumps(events), encoding="utf-8")
        except Exception:
            pass

    def complete_task(self, task_id: str, result: Dict[str, Any], status: str = "completed") -> bool:
        with self._lock:
            state = self._read_state()
            tasks = state.setdefault("tasks", [])
            completed_task = None
            for t in tasks:
                if t.get("id") == task_id:
                    t["status"] = status
                    t["completed_at"] = time.time()
                    completed_task = t
                    break

            results = state.setdefault("results", {})
            results[task_id] = {
                "status": status,
                "result": result,
                "completed_at": time.time()
            }

            state["tasks"] = [
                t for t in tasks
                if t.get("status") in ("pending", "processing")
                or (time.time() - t.get("completed_at", time.time())) < 3600
            ]

            self._write_state(state)

        if completed_task and completed_task.get("type") == "story":
            try:
                story_id = result.get("story_id") or completed_task.get("payload", {}).get("story_id")
                appetite = result.get("appetite") or completed_task.get("payload", {}).get("appetite", "cyber_thriller")
                if story_id:
                    safe_story = re.sub(r"[^a-zA-Z0-9_-]", "-", story_id).strip("-")
                    target = TEMP_DOCS_DIR / f"{safe_story}_{appetite}.json"
                    with open(target, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2)
            except Exception:
                pass

        return True

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self._read_state()
            return state.get("results", {}).get(task_id)

    def get_stream_chunks(self, task_id: str, since_seq: int = -1) -> List[Dict[str, Any]]:
        with self._lock:
            state = self._read_state()
            chunks = state.get("streams", {}).get(task_id, [])
            return [c for c in chunks if c.get("seq", 0) > since_seq]


bridge_mgr = BridgeManager()
