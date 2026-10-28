"""
=============================================================================
   UNIT TEST SUITE FOR E-PROFILE HYBRID EMAIL ENGINE & ADMIN MAILBOX
=============================================================================
Tests:
  1. Local mock mailbox dispatch and JSON persistence.
  2. ID lookup, loading, and cache clearing.
  3. Dark-theme responsive HTML template builder.
  4. Flask route access control (Admin RBAC required for /admin/mailbox).
  5. Test email dispatch via admin POST endpoint.
  6. Feedback notification integration.
=============================================================================
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from config import Config
import email_engine


class TestEmailEngine(unittest.TestCase):
    def setUp(self):
        # Create isolated temporary directory for test mailbox
        self.temp_dir = tempfile.mkdtemp()
        self.test_mailbox_file = Path(self.temp_dir) / "test_mailbox.json"

        # Mock config mailbox file and email config
        self.orig_mailbox_file = Config.MAILBOX_FILE
        self.orig_backend = Config.MAIL_BACKEND
        self.orig_server = Config.MAIL_SERVER
        self.orig_port = Config.MAIL_PORT
        self.orig_use_tls = Config.MAIL_USE_TLS
        self.orig_username = Config.MAIL_USERNAME
        self.orig_password = Config.MAIL_PASSWORD
        self.orig_sender = Config.MAIL_DEFAULT_SENDER

        Config.MAILBOX_FILE = self.test_mailbox_file
        email_engine.config.MAILBOX_FILE = self.test_mailbox_file
        Config.MAIL_BACKEND = "local"
        email_engine.config.MAIL_BACKEND = "local"

        # Prevent tests from mutating physical .env file
        self.env_patcher = patch.object(email_engine, 'update_env_file', return_value=True)
        self.mock_update_env = self.env_patcher.start()

        # Set up Flask test client
        server.app.config["TESTING"] = True
        server.app.config["SECRET_KEY"] = "email_test_secret_key_2026"
        self.client = server.app.test_client()

    def tearDown(self):
        self.env_patcher.stop()
        Config.MAILBOX_FILE = self.orig_mailbox_file
        email_engine.config.MAILBOX_FILE = self.orig_mailbox_file
        Config.MAIL_BACKEND = self.orig_backend
        email_engine.config.MAIL_BACKEND = self.orig_backend
        Config.MAIL_SERVER = self.orig_server
        email_engine.config.MAIL_SERVER = self.orig_server
        Config.MAIL_PORT = self.orig_port
        email_engine.config.MAIL_PORT = self.orig_port
        Config.MAIL_USE_TLS = self.orig_use_tls
        email_engine.config.MAIL_USE_TLS = self.orig_use_tls
        Config.MAIL_USERNAME = self.orig_username
        email_engine.config.MAIL_USERNAME = self.orig_username
        Config.MAIL_PASSWORD = self.orig_password
        email_engine.config.MAIL_PASSWORD = self.orig_password
        Config.MAIL_DEFAULT_SENDER = self.orig_sender
        email_engine.config.MAIL_DEFAULT_SENDER = self.orig_sender
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_send_email(self):
        """Verify that send_email records to local mailbox in 'local' mode."""
        success, msg, record = email_engine.send_email(
            to_address="tester@example.com",
            subject="Test Dispatch",
            html_content="<p>Hello World</p>"
        )
        self.assertTrue(success)
        self.assertIn("local", msg.lower())
        self.assertEqual(record["to"], "tester@example.com")
        self.assertEqual(record["subject"], "Test Dispatch")
        self.assertEqual(record["status"], "DELIVERED_LOCAL")

        # Verify disk persistence
        self.assertTrue(self.test_mailbox_file.exists())
        items = email_engine.load_local_mailbox()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], record["id"])
        self.assertEqual(items[0]["to"], "tester@example.com")

    def test_get_email_by_id(self):
        """Verify retrieving single email record by unique UUID."""
        _, _, record = email_engine.send_email(
            to_address="target@domain.org",
            subject="Lookup Test",
            html_content="<p>Lookup Details</p>"
        )
        fetched = email_engine.get_email_by_id(record["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["subject"], "Lookup Test")

        non_existent = email_engine.get_email_by_id("non-existent-uuid")
        self.assertIsNone(non_existent)

    def test_clear_local_mailbox(self):
        """Verify clearing local mailbox resets list to empty."""
        email_engine.send_email("one@example.com", "First", "<p>1</p>")
        email_engine.send_email("two@example.com", "Second", "<p>2</p>")
        self.assertEqual(len(email_engine.load_local_mailbox()), 2)

        cleared = email_engine.clear_local_mailbox()
        self.assertTrue(cleared)
        self.assertEqual(len(email_engine.load_local_mailbox()), 0)

    def test_build_email_template(self):
        """Verify HTML template generation adheres to styling and accessibility."""
        html = email_engine.build_email_template(
            title="System Alert",
            body_html="<p>Zero-Trust Security Triggered</p>",
            action_url="https://eprofile.local/admin",
            action_label="Review Alert"
        )
        self.assertIn("System Alert", html)
        self.assertIn("Zero-Trust Security Triggered", html)
        self.assertIn("https://eprofile.local/admin", html)
        self.assertIn("Review Alert", html)
        self.assertIn("role=\"presentation\"", html)

    def test_admin_mailbox_requires_authentication(self):
        """Verify unauthenticated requests to /admin/mailbox are redirected to login."""
        res = self.client.get("/admin/mailbox", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_admin_mailbox_renders_with_session(self):
        """Verify authenticated admin can access /admin/mailbox."""
        with self.client.session_transaction() as sess:
            sess["admin"] = True
            sess["username"] = "Michael"

        res = self.client.get("/admin/mailbox")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Email Engine & Mailbox", res.data)

    def test_admin_send_test_email_route(self):
        """Verify POST /admin/mailbox/send_test dispatches and redirects."""
        with self.client.session_transaction() as sess:
            sess["admin"] = True

        res = self.client.post("/admin/mailbox/send_test", data={
            "to_address": "verified@server.local",
            "subject": "Admin Web Test",
            "message": "Testing from web admin console",
            "action_url": "https://example.com"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Web Test", res.data)
        self.assertIn(b"verified@server.local", res.data)

    def test_feedback_triggers_email_notification(self):
        """Verify that submitting audio suite feedback auto-generates a mailbox record."""
        feedback_payload = {
            "hwid": "HWID-TEST-12345678",
            "type": "bug",
            "subject": "Audio glitch on track jump",
            "message": "Noticeable click sound when jumping between tracks.",
            "app_version": "1.0.0"
        }
        res = self.client.post("/api/audio_suite/feedback", json=feedback_payload)
        self.assertEqual(res.status_code, 200)

        # Clean up test feedback from disk
        feedback_file = Config.ROOT_DIR / "content" / "audio_suite_feedback.json"
        if feedback_file.exists():
            try:
                data = json.loads(feedback_file.read_text(encoding="utf-8"))
                cleaned = [f for f in data if f.get("hwid") != "HWID-TEST-12345678"]
                feedback_file.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
            except Exception:
                pass

        # Verify an email alert was captured in local mailbox
        items = email_engine.load_local_mailbox()
        feedback_emails = [e for e in items if "Audio glitch on track jump" in e.get("subject", "")]
        self.assertGreaterEqual(len(feedback_emails), 1)
        self.assertEqual(feedback_emails[0]["to"], "admin@eprofile.local")

    def test_apply_gateway_settings(self):
        """Verify updating gateway settings in memory and in .env."""
        success, msg = email_engine.apply_gateway_settings(
            backend="smtp",
            server_host="smtp.testserver.net",
            server_port=587,
            use_tls=True,
            username="testuser@testserver.net",
            password="testpassword123",
            default_sender="testuser@testserver.net"
        )
        self.assertTrue(success)
        self.assertEqual(email_engine.config.MAIL_SERVER, "smtp.testserver.net")
        self.assertEqual(email_engine.config.MAIL_PORT, 587)
        self.assertEqual(email_engine.config.MAIL_USERNAME, "testuser@testserver.net")

    def test_apply_google_service_json(self):
        """Verify validating and saving Google JSON credentials."""
        dummy_json = json.dumps({
            "type": "service_account",
            "project_id": "test-cyber-project-2026",
            "client_email": "test-bot@test-cyber-project-2026.iam.gserviceaccount.com"
        })
        success, msg, meta = email_engine.apply_google_service_json(dummy_json)
        self.assertTrue(success)
        self.assertEqual(meta["project_id"], "test-cyber-project-2026")
        self.assertEqual(meta["client_email"], "test-bot@test-cyber-project-2026.iam.gserviceaccount.com")

        # Cleanup created file if in root
        test_file = Config.ROOT_DIR / ".google_credentials.json"
        if test_file.exists():
            test_file.unlink()

    def test_admin_save_settings_route(self):
        """Verify POST /admin/mailbox/save_settings updates settings via web form."""
        with self.client.session_transaction() as sess:
            sess["admin"] = True

        res = self.client.post("/admin/mailbox/save_settings", data={
            "backend": "local",
            "server": "smtp.gmail.com",
            "port": "587",
            "use_tls": "1",
            "username": "admin@gmail.com",
            "password": "",
            "default_sender": "admin@gmail.com"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Settings saved", res.data)

    @patch("smtplib.SMTP_SSL")
    def test_smtp_ssl_port_465(self, mock_smtp_ssl):
        """Verify that port 465 triggers SMTP_SSL rather than standard SMTP."""
        mock_instance = mock_smtp_ssl.return_value
        Config.MAIL_BACKEND = "smtp"
        email_engine.config.MAIL_BACKEND = "smtp"
        Config.MAIL_PORT = 465
        email_engine.config.MAIL_PORT = 465
        Config.MAIL_SERVER = "smtp.custom-ssl.net"
        email_engine.config.MAIL_SERVER = "smtp.custom-ssl.net"

        success, msg, record = email_engine.send_email(
            to_address="target@domain.org",
            subject="SSL Test",
            html_content="<p>SSL Test</p>"
        )
        self.assertTrue(success)
        mock_smtp_ssl.assert_called_once_with("smtp.custom-ssl.net", 465, timeout=10)
        mock_instance.sendmail.assert_called_once()
        mock_instance.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()

