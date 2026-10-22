"""Regression and security test suite for password/PIN resets and profile management."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import server
from scripts.reset_admin import compute_token_hash, reset_admin_token


class TestPasswordResetWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_profiles_file = Path(self.temp_dir) / "profiles.json"

        self.admin_token = "admin_secret_123"
        self.user_token = "user_secret_456"
        self.admin_hash = compute_token_hash(self.admin_token)
        self.user_hash = compute_token_hash(self.user_token)

        self.initial_data = {
            "metadata": {"schema_version": 2, "last_migrated": "2026-10-22T00:00:00"},
            "data": {
                self.admin_hash: {
                    "username": "TestAdmin",
                    "label": "Administrator",
                    "uuid": "test-admin-uuid-001",
                    "permissions": ["view:real_name"],
                    "is_admin": True,
                    "is_employer": False,
                    "bypass_enabled": False,
                },
                self.user_hash: {
                    "username": "TestUser",
                    "label": "Standard User",
                    "uuid": "test-user-uuid-002",
                    "permissions": [],
                    "is_admin": False,
                    "is_employer": False,
                    "bypass_enabled": False,
                },
            },
        }

        self.mock_profiles_file.write_text(json.dumps(self.initial_data, indent=4), encoding="utf-8")

        self.orig_profiles_file = server.PROFILES_FILE
        server.PROFILES_FILE = self.mock_profiles_file

        server.app.config["TESTING"] = True
        server.app.config["SECRET_KEY"] = "test_key_accessibility_verification"
        self.client = server.app.test_client()

    def tearDown(self):
        server.PROFILES_FILE = self.orig_profiles_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_change_password_requires_login(self):
        response = self.client.get("/change_password", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_change_password_redirects_non_admin_to_login(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestUser"
            sess["label"] = "Standard User"
            sess["admin"] = False

        response = self.client.get("/change_password", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_change_password_redirects_admin_to_admin_panel(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestAdmin"
            sess["admin"] = True

        response = self.client.get("/change_password", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin", response.headers.get("Location", ""))

    def test_admin_reset_pin_unauthorized_for_standard_user(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestUser"
            sess["admin"] = False

        response = self.client.post(
            "/reset_pin",
            data={
                "token_hash": self.user_hash,
                "new_token": "fresh_pin_1234",
                "confirm_token": "fresh_pin_1234",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_reset_pin_validates_and_succeeds(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestAdmin"
            sess["admin"] = True

        admin_pin = "admin_reset_key_444"
        response = self.client.post(
            "/reset_pin",
            data={
                "token_hash": self.user_hash,
                "new_token": admin_pin,
                "confirm_token": admin_pin,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin", response.headers.get("Location", ""))

        profiles = server.load_profiles()
        new_hash = compute_token_hash(admin_pin)
        self.assertIn(new_hash, profiles)
        self.assertNotIn(self.user_hash, profiles)
        self.assertEqual(profiles[new_hash]["username"], "TestUser")

    def test_admin_edit_profile_with_new_pin_resets_password(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestAdmin"
            sess["admin"] = True

        updated_pin = "updated_user_pin_888"
        response = self.client.post(
            "/edit_profile",
            data={
                "token_hash": self.user_hash,
                "username": "TestUserRenamed",
                "label": "Updated Label",
                "token": updated_pin,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin", response.headers.get("Location", ""))

        profiles = server.load_profiles()
        new_hash = compute_token_hash(updated_pin)
        self.assertIn(new_hash, profiles)
        self.assertNotIn(self.user_hash, profiles)
        self.assertEqual(profiles[new_hash]["username"], "TestUserRenamed")
        self.assertEqual(profiles[new_hash]["label"], "Updated Label")

    def test_admin_edit_profile_without_pin_preserves_existing_password(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestAdmin"
            sess["admin"] = True

        response = self.client.post(
            "/edit_profile",
            data={
                "token_hash": self.user_hash,
                "username": "TestUserRenamedOnly",
                "label": "Standard User",
                "token": "",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        profiles = server.load_profiles()
        self.assertIn(self.user_hash, profiles)
        self.assertEqual(profiles[self.user_hash]["username"], "TestUserRenamedOnly")

    def test_delete_profile_blocks_admin_self_deletion(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestAdmin"
            sess["admin"] = True

        response = self.client.post(
            "/delete_profile",
            data={"token_hash": self.admin_hash},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        profiles = server.load_profiles()
        self.assertIn(self.admin_hash, profiles)

    def test_delete_profile_removes_target_user(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "TestAdmin"
            sess["admin"] = True

        response = self.client.post(
            "/delete_profile",
            data={"token_hash": self.user_hash},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        profiles = server.load_profiles()
        self.assertNotIn(self.user_hash, profiles)

    def test_cli_reset_admin_tool(self):
        new_admin_pin = "recovery_cli_pin_9876"
        success = reset_admin_token("TestAdmin", new_admin_pin, self.mock_profiles_file)
        self.assertTrue(success)

        profiles = json.loads(self.mock_profiles_file.read_text())["data"]
        new_admin_hash = compute_token_hash(new_admin_pin)
        self.assertIn(new_admin_hash, profiles)
        self.assertNotIn(self.admin_hash, profiles)


if __name__ == "__main__":
    unittest.main()
