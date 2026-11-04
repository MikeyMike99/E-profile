"""Unit and integration tests for Split-Brain Bridge & HTTP Sync Architecture."""

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import server
import bridge_manager
import sync_mod
from bridge_manager import BridgeManager, is_production_server
from story_agent_dispatcher import dispatch_story_generation


class TestBridgeSyncArchitecture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.queue_file = Path(self.temp_dir) / "bridge_queue.json"
        self.mgr = BridgeManager(queue_file=self.queue_file)

        # Isolate global bridge_mgr in sync_mod to temporary queue
        self.orig_bridge_queue_file = bridge_manager.bridge_mgr.queue_file
        bridge_manager.bridge_mgr.queue_file = self.queue_file

        server.app.config["TESTING"] = True
        server.app.config["SECRET_KEY"] = "test_bridge_secret"
        self.client = server.app.test_client()

        self.orig_sync_secret = os.environ.get("SYNC_SECRET")
        os.environ["SYNC_SECRET"] = "unit_test_secret_123"

    def tearDown(self):
        bridge_manager.bridge_mgr.queue_file = self.orig_bridge_queue_file
        if self.orig_sync_secret is None:
            os.environ.pop("SYNC_SECRET", None)
        else:
            os.environ["SYNC_SECRET"] = self.orig_sync_secret
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. BRIDGE MANAGER CORE LOGIC
    # -------------------------------------------------------------------------

    def test_enqueue_and_poll_task(self):
        task = self.mgr.enqueue_task("chat", {"prompt": "Hello bridge"})
        self.assertTrue(task["id"].startswith("task_"))
        self.assertEqual(task["status"], "pending")

        polled = self.mgr.poll_task(worker_id="test_worker")
        self.assertIsNotNone(polled)
        self.assertEqual(polled["id"], task["id"])
        self.assertEqual(polled["status"], "processing")
        self.assertEqual(polled["worker_id"], "test_worker")

        # Second poll should be idle
        second_poll = self.mgr.poll_task(worker_id="test_worker")
        self.assertIsNone(second_poll)

    def test_stream_chunks_and_retrieval(self):
        task = self.mgr.enqueue_task("chat", {"prompt": "Stream test"})
        self.mgr.append_stream_chunk(task["id"], 1, "Token1 ")
        self.mgr.append_stream_chunk(task["id"], 2, "Token2", done=True)

        chunks = self.mgr.get_stream_chunks(task["id"])
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["chunk"], "Token1 ")
        self.assertEqual(chunks[1]["chunk"], "Token2")
        self.assertTrue(chunks[1]["done"])

    def test_complete_task_and_result(self):
        task = self.mgr.enqueue_task("story", {"story_id": "test_cve", "appetite": "deep_dive"})
        res_data = {"story_id": "test_cve", "markdown": "Detailed forensic analysis."}
        self.mgr.complete_task(task["id"], res_data, status="completed")

        stored = self.mgr.get_task_result(task["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "completed")
        self.assertEqual(stored["result"]["markdown"], "Detailed forensic analysis.")

    def test_heartbeat_and_status(self):
        self.mgr.record_heartbeat("worker_alpha")
        status = self.mgr.get_status()
        self.assertTrue(status["bridge_online"])
        self.assertEqual(status["worker_id"], "worker_alpha")
        self.assertLess(status["last_seen_sec_ago"], 5.0)

    # -------------------------------------------------------------------------
    # 2. HTTP SYNC ENDPOINTS
    # -------------------------------------------------------------------------

    def test_unauthorized_endpoints(self):
        # Missing secret
        r1 = self.client.post("/api/sync", data={"path": "test.txt"})
        self.assertEqual(r1.status_code, 403)

        r2 = self.client.post("/api/sync/package")
        self.assertEqual(r2.status_code, 403)

        r3 = self.client.post("/api/sync/git-pull")
        self.assertEqual(r3.status_code, 403)

        r4 = self.client.get("/api/bridge/poll")
        self.assertEqual(r4.status_code, 403)

    def test_package_sync_zip_extraction(self):
        # Create an in-memory zip
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("cache/temp_docs/test_sample_pkg.json", json.dumps({"test": "ok"}))
            # Malicious traversal attempts should be skipped
            zf.writestr("../outside_escape.txt", "escaped")
            zf.writestr(".git/HEAD", "fake_git")
            zf.writestr("profiles.json", "fake_passwords")

        zip_buf.seek(0)
        data = {
            "secret": "unit_test_secret_123",
            "package": (zip_buf, "package.zip")
        }
        res = self.client.post(
            "/api/sync/package",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 200)
        resp_json = res.get_json()
        self.assertEqual(resp_json["status"], "success")
        self.assertIn("cache/temp_docs/test_sample_pkg.json", resp_json["files"])
        self.assertNotIn("../outside_escape.txt", resp_json["files"])
        self.assertNotIn(".git/HEAD", resp_json["files"])
        self.assertNotIn("profiles.json", resp_json["files"])

        # Clean up test artifact
        test_file = Path(server.config.ROOT_DIR) / "cache" / "temp_docs" / "test_sample_pkg.json"
        test_file.unlink(missing_ok=True)

    def test_git_pull_endpoint(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.\n", stderr="")
            res = self.client.post(
                "/api/sync/git-pull",
                headers={"X-Sync-Secret": "unit_test_secret_123"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data["status"], "success")
            self.assertIn("Already up to date", data["stdout"])

    def test_bridge_http_lifecycle(self):
        # 1. Enqueue task via HTTP
        enq_res = self.client.post(
            "/api/bridge/enqueue",
            headers={"X-Sync-Secret": "unit_test_secret_123"},
            json={"type": "chat", "payload": {"prompt": "Unit test HTTP chat"}}
        )
        self.assertEqual(enq_res.status_code, 200)
        task_id = enq_res.get_json()["task"]["id"]

        # 2. Poll task via HTTP
        poll_res = self.client.get(
            f"/api/bridge/poll?worker_id=test_http_worker",
            headers={"X-Sync-Secret": "unit_test_secret_123"}
        )
        self.assertEqual(poll_res.status_code, 200)
        self.assertEqual(poll_res.get_json()["status"], "task")
        self.assertEqual(poll_res.get_json()["task"]["id"], task_id)

        # 3. Stream chunk via HTTP
        stream_res = self.client.post(
            "/api/bridge/stream",
            headers={"X-Sync-Secret": "unit_test_secret_123"},
            json={"task_id": task_id, "seq": 1, "chunk": "Stream token 1", "done": False}
        )
        self.assertEqual(stream_res.status_code, 200)

        # 4. Complete task via HTTP
        comp_res = self.client.post(
            "/api/bridge/complete",
            headers={"X-Sync-Secret": "unit_test_secret_123"},
            json={"task_id": task_id, "status": "completed", "result": {"output": "Done!"}}
        )
        self.assertEqual(comp_res.status_code, 200)

        # 5. Check bridge status
        stat_res = self.client.get("/api/bridge/status")
        self.assertEqual(stat_res.status_code, 200)
        stat_data = stat_res.get_json()
        self.assertTrue(stat_data["bridge_online"])
        self.assertEqual(stat_data["worker_id"], "test_http_worker")

    # -------------------------------------------------------------------------
    # 3. STORY DISPATCHER SPLIT-BRAIN ISOLATION
    # -------------------------------------------------------------------------

    def test_story_generation_in_production_edge(self):
        with patch("story_agent_dispatcher.is_production_server", return_value=True), \
             patch("subprocess.run") as mock_sub:
            res = dispatch_story_generation(
                story_id="cve-edge-safe-test",
                appetite="executive_espresso",
                engine_choice="claude"
            )
            # Must return instant rich built-in synthesis without calling subprocess
            self.assertFalse(mock_sub.called)
            self.assertEqual(res["engine"], "builtin (edge-safe)")
            self.assertIn("BLUF", res["markdown"])

            # Clean test cached story
            test_cached = Path(server.config.ROOT_DIR) / "cache" / "temp_docs" / "cve-edge-safe-test_executive_espresso.json"
            test_cached.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
