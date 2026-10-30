"""
=============================================================================
   AUTOMATED TEST SUITE FOR E-PROFILE AI AGENT ARCHITECTURE & BLUEPRINT
=============================================================================
Verifies:
  1. Security & RBAC isolation (Admin Root Scope vs Visitor Demo Scope).
  2. Blueprint endpoints, token minting, and session lifecycles.
  3. Project management and conversation transcript APIs.
  4. Chat dispatch, task cancellation, and sequence-cursor stream polling.
  5. Artifact retrieval and direct in-place update authorization.
  6. Platform parity, binary discovery heuristics, and zero hardcoded paths.
=============================================================================
"""

import ast
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import server
import ai_plugin


class TestEProfileAIAgent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        server.app.config["TESTING"] = True
        server.app.config["SECRET_KEY"] = "test_ai_agent_secret_key"
        self.client = server.app.test_client()

        self.orig_active_project = getattr(ai_plugin.project_mgr, "active_project", "")
        self.orig_message_queue = list(getattr(ai_plugin.agent_mgr, "message_queue", []))

    def tearDown(self):
        if hasattr(ai_plugin.project_mgr, "set_active_project"):
            ai_plugin.project_mgr.set_active_project(self.orig_active_project)
        if hasattr(ai_plugin.agent_mgr, "message_queue"):
            ai_plugin.agent_mgr.message_queue = list(self.orig_message_queue)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # SUITE 1: SECURITY & RBAC ISOLATION
    # =========================================================================

    def test_unauthenticated_agent_access_redirects_to_login(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        res = self.client.get("/ai_agent/", follow_redirects=False)
        self.assertIn(res.status_code, (301, 302))
        loc = res.headers.get("Location", "")
        self.assertIn("login", loc)
        self.assertNotIn("/home", loc)

    def test_admin_agent_access_establishes_root_scope(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = True
            sess["is_admin"] = True
            sess["username"] = "admin"

        res = self.client.get("/ai_agent/?mode=root&project=root", follow_redirects=False)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Siraugga Command Center", html)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("agent_token_scope"), "root")
            self.assertTrue(sess.get("agent_authenticated"))

    def test_demo_visitor_isolation_and_boundary(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = False
            sess["is_admin"] = False

        res = self.client.get("/ai_agent/login?demo=1", follow_redirects=False)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Siraugga Agent • Google OAuth Authentication", html)
        self.assertNotIn("SECURE_GATE | ACCESS_RESTRICTED", html)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("agent_token_scope"), "demo")
            self.assertFalse(sess.get("agent_authenticated"))

        # Gated demo visitor without authentication hitting /ai_agent/ must redirect to login?demo=1
        res_gated = self.client.get("/ai_agent/", follow_redirects=False)
        self.assertIn(res_gated.status_code, (301, 302))
        self.assertIn("login?demo=1", res_gated.headers.get("Location", ""))

    def test_visitor_blocked_from_raw_artifacts(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = False
            sess["is_admin"] = False
            sess["agent_token_scope"] = "demo"

        res = self.client.get("/ai_agent/api/artifacts?path=/etc/shadow")
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn("error", data)
        self.assertIn("Admin clearance required", data["error"])

    def test_visitor_blocked_from_artifact_save(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = False
            sess["is_admin"] = False
            sess["agent_token_scope"] = "demo"

        res = self.client.post("/ai_agent/api/artifacts/save", json={"path": "/tmp/test.md", "content": "exploit"})
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn("error", data)
        self.assertIn("Admin clearance required", data["error"])

    def test_path_traversal_rejection_in_project_and_artifact(self):
        with self.client.session_transaction() as sess:
            sess["admin"] = True
            sess["is_admin"] = True
            sess["agent_token_scope"] = "root"

        # Traversal attempt on non-existent path
        res = self.client.get("/ai_agent/api/artifacts?path=../../etc/passwd")
        self.assertEqual(res.status_code, 404)

        # Non-existent artifact returns 404
        res_missing = self.client.get("/ai_agent/api/artifacts?path=/nonexistent/path/artifact.md")
        self.assertEqual(res_missing.status_code, 404)

    # =========================================================================
    # SUITE 2: AI BLUEPRINT API & SESSION LIFECYCLE
    # =========================================================================

    def test_ui_config_endpoint(self):
        res = self.client.get("/ai_agent/api/ui-config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("header", data)
        self.assertIn("models", data["header"])

    def test_auth_demo_token_minting(self):
        res = self.client.post("/ai_agent/api/auth_demo")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("scope"), "demo")
        self.assertIsNotNone(data.get("token"))
        self.assertEqual(data.get("user", {}).get("role"), "gamedev")

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("agent_token_scope"), "demo")
            self.assertTrue(sess.get("agent_authenticated"))

    def test_scoped_api_key_storage(self):
        orig_key = os.environ.get("GEMINI_API_KEY")
        demo_test_dir = Path(self.temp_dir) / "demo_test"

        with patch("ai_plugin._get_demo_dirs", return_value=[str(demo_test_dir)]):
            with self.client.session_transaction() as sess:
                sess.clear()
                sess["admin"] = False
                sess["is_admin"] = False
                sess["agent_token_scope"] = "demo"

            res = self.client.post("/ai_agent/api/set_api_key", json={"api_key": "ai_test_key_sample", "scope": "demo"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("scope"), "demo")

            # Root environment variable must not be polluted with demo key
            self.assertEqual(os.environ.get("GEMINI_API_KEY"), orig_key)
            self.assertTrue((demo_test_dir / ".devcore_client_key.txt").is_file())

    def test_auth_me_identity_resolution(self):
        # Admin via session cookie
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = True
            sess["is_admin"] = True
            sess["username"] = "admin"
            sess["agent_token_scope"] = "root"

        res_admin = self.client.get("/ai_agent/api/auth/me")
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.get_json()["user"]["role"], "admin")

        # Bearer token resolution
        auth_res = ai_plugin.security_mgr.authenticate("dev", "dev")
        self.assertIsNotNone(auth_res)
        token = auth_res["token"]

        with self.client.session_transaction() as sess:
            sess.clear()

        res_bearer = self.client.get("/ai_agent/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_bearer.status_code, 200)
        self.assertEqual(res_bearer.get_json()["user"]["role"], "gamedev")

    def test_auth_logout_clears_session(self):
        with self.client.session_transaction() as sess:
            sess["agent_authenticated"] = True

        res = self.client.post("/ai_agent/api/auth/logout")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("agent_authenticated"))

    def test_auth_system_status(self):
        res = self.client.get("/ai_agent/api/auth/system-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("cli_installed", data)
        self.assertIn("has_api_key", data)
        self.assertIn("scope", data)

    # =========================================================================
    # SUITE 3: PROJECT & CONVERSATION WORKSPACE MANAGEMENT
    # =========================================================================

    def test_list_projects_and_switch_active(self):
        res_list = self.client.get("/ai_agent/api/projects")
        self.assertEqual(res_list.status_code, 200)
        data_list = res_list.get_json()
        self.assertIn("projects", data_list)
        self.assertIn("active", data_list)

        # Test switching project with mock to prevent out-of-bounds firewall errors
        with patch.object(ai_plugin.project_mgr, "set_active_project") as mock_set:
            res_active = self.client.post("/ai_agent/api/projects/active", json={"name": "game_demo"})
            self.assertEqual(res_active.status_code, 200)
            mock_set.assert_called_once_with("game_demo")

        # Test reset to root workspace directly
        res_reset = self.client.post("/ai_agent/api/projects/active", json={"name": ""})
        self.assertEqual(res_reset.status_code, 200)
        self.assertTrue(res_reset.get_json().get("success"))

    def test_conversation_lifecycle(self):
        # 1. List conversations
        res_list = self.client.get("/ai_agent/api/conversations")
        self.assertEqual(res_list.status_code, 200)
        data = res_list.get_json()
        self.assertIn("conversations", data)

        # 2. Rename conversation
        res_rename = self.client.post("/ai_agent/api/conversations/test-conv-001/rename", json={"title": "Updated Title"})
        self.assertEqual(res_rename.status_code, 200)
        self.assertEqual(res_rename.get_json()["title"], "Updated Title")

        # 3. Delete single conversation
        res_del = self.client.delete("/ai_agent/api/conversations/test-conv-001")
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()["success"])

    def test_delete_active_conversations(self):
        res = self.client.delete("/ai_agent/api/projects/active/conversations")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

    # =========================================================================
    # SUITE 4: CHAT ORCHESTRATION & STREAMING QUEUE
    # =========================================================================

    def test_start_chat_task_submission(self):
        async def mock_start_task(*args, **kwargs):
            return True

        with patch.object(ai_plugin.agent_mgr, "start_task", side_effect=mock_start_task):
            res = self.client.post("/ai_agent/api/chat", json={"prompt": "Unit test prompt"})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("message"), "Task started")

    def test_stream_sequence_cursor_polling(self):
        fake_rt = Path(self.temp_dir) / ".runtime"
        fake_rt.mkdir(parents=True, exist_ok=True)
        with patch("ai_plugin._get_runtime_dir", return_value=fake_rt):
            ai_plugin.agent_mgr.message_queue = [
                {"seq": 1, "msg": {"type": "chunk", "text": "Packet 1"}},
                {"seq": 2, "msg": {"type": "chunk", "text": "Packet 2"}},
                {"seq": 3, "msg": {"type": "chunk", "text": "Packet 3"}},
            ]

            # Poll since seq 1: packets 2 and 3 should be returned, packet 1 excluded
            res = self.client.get("/ai_agent/api/stream?since_seq=1")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn("messages", data)
            self.assertEqual(len(data["messages"]), 2)
            self.assertEqual(data["last_seq"], 3)
            self.assertEqual(data["messages"][0]["seq"], 2)
            self.assertEqual(data["messages"][1]["seq"], 3)

            # Queue items must be preserved (non-destructive polling)
            self.assertEqual(len(ai_plugin.agent_mgr.message_queue), 3)

    def test_kill_chat_task_cancellation(self):
        async def mock_cancel_task():
            return True

        with patch.object(ai_plugin.agent_mgr, "cancel_task", side_effect=mock_cancel_task):
            res = self.client.post("/ai_agent/api/kill")
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.get_json()["success"])

    # =========================================================================
    # SUITE 5: ARTIFACTS MANAGEMENT & DIRECT IN-PLACE UPDATES
    # =========================================================================

    def test_admin_fetch_artifact(self):
        test_file = Path(self.temp_dir) / "test_artifact.md"
        test_file.write_text("# Test Artifact Content\nReady for inspection.", encoding="utf-8")

        with self.client.session_transaction() as sess:
            sess["admin"] = True
            sess["is_admin"] = True
            sess["agent_token_scope"] = "root"

        res = self.client.get(f"/ai_agent/api/artifacts?path={test_file}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("content"), "# Test Artifact Content\nReady for inspection.")
        self.assertEqual(data.get("path"), str(test_file))

    def test_admin_save_artifact(self):
        save_file = Path(self.temp_dir) / "save_artifact.md"

        with self.client.session_transaction() as sess:
            sess["admin"] = True
            sess["is_admin"] = True
            sess["agent_token_scope"] = "root"

        res = self.client.post(
            "/ai_agent/api/artifacts/save",
            json={"path": str(save_file), "content": "## Updated In-Place Artifact Content"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])
        self.assertTrue(save_file.is_file())
        self.assertEqual(save_file.read_text(encoding="utf-8"), "## Updated In-Place Artifact Content")

    # =========================================================================
    # SUITE 6: PLATFORM & PYTHONANYWHERE PARITY
    # =========================================================================

    def test_binary_discovery_heuristics(self):
        bin_path = ai_plugin._find_agy_binary()
        # On dev host agy or agy_real exists; in mock/container it safely returns None or path
        if bin_path is not None:
            self.assertIsInstance(bin_path, str)
            self.assertTrue(Path(bin_path).exists())

    def test_zero_hardcoded_host_paths(self):
        src = (Path(ai_plugin.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("/mnt/c/Users/michael", src)

    def test_file_mod_terminal_scaffolding(self):
        file_mod_path = Path(server.__file__).parent / "file_mod.py"
        src = file_mod_path.read_text(encoding="utf-8")
        self.assertIn("agy --print", src)
        self.assertIn("timeout_seconds", src)


if __name__ == "__main__":
    unittest.main()
