"""
Unit tests for Bring Your Own Subscription (BYOS) cryptographic vault,
7-day TTL countdown purge, and strict quota halt guard.
"""

import os
import shutil
import tempfile
import time
import unittest
from security.subscription_guard import (
    _derive_vault_key,
    encrypt_credential,
    decrypt_credential,
    set_user_subscription,
    get_user_subscription,
    delete_user_subscription,
    purge_expired_subscriptions,
    assert_user_execution_quota,
    get_user_runtime_chamber,
)


class TestSubscriptionGuard(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="devcore_byos_test_")
        self.master_key_file = os.path.join(self.test_dir, ".devcore_master.key")
        with open(self.master_key_file, "w", encoding="utf-8") as f:
            f.write("test_master_secret_invariant_key_12345\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_encryption_decryption_roundtrip(self):
        secret = "AIzaSyTestApiKeyMockSecretVal12345"
        encrypted = encrypt_credential(secret, base_dir=self.test_dir)
        self.assertNotEqual(secret, encrypted)
        decrypted = decrypt_credential(encrypted, base_dir=self.test_dir)
        self.assertEqual(secret, decrypted)

    def test_7_day_ttl_and_countdown(self):
        user_id = "developer_alex"
        secret = "AIzaSyAlexKeySecret123"
        res = set_user_subscription(
            user_id=user_id,
            provider="gemini",
            credential=secret,
            ttl_days=7.0,
            base_dir=self.test_dir
        )
        self.assertTrue(res["success"])
        self.assertAlmostEqual(res["days_remaining"], 7.0, delta=0.1)

        fetched = get_user_subscription(user_id, base_dir=self.test_dir, include_decrypted=True)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["credential"], secret)
        self.assertAlmostEqual(fetched["days_remaining"], 7.0, delta=0.1)
        self.assertTrue(fetched["hours_remaining"] > 160)

    def test_auto_purge_expired_subscription(self):
        user_id = "developer_expired"
        secret = "AIzaSyExpiredKey"
        set_user_subscription(
            user_id=user_id,
            provider="gemini",
            credential=secret,
            ttl_days=0.0001,
            base_dir=self.test_dir
        )

        time.sleep(0.02)
        import json
        vault_path = os.path.join(self.test_dir, "subscriptions.json")
        with open(vault_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data[user_id]["expires_at"] = time.time() - 10
        with open(vault_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        purged = purge_expired_subscriptions(base_dir=self.test_dir)
        self.assertEqual(purged, 1)

        fetched = get_user_subscription(user_id, base_dir=self.test_dir)
        self.assertIsNone(fetched)

    def test_strict_halt_for_non_admin_without_subscription(self):
        guest_user = {
            "username": "guest_coder",
            "role": "gamedev",
            "name": "Guest Coder"
        }
        allowed, reason, sub = assert_user_execution_quota(guest_user, base_dir=self.test_dir)
        self.assertFalse(allowed)
        self.assertIn("Personal subscription expired or missing", reason)
        self.assertIn("host billing bleed", reason)
        self.assertIsNone(sub)

    def test_admin_fallback_allowed_when_no_byos_configured(self):
        admin_user = {
            "username": "Michael (Admin)",
            "role": "admin",
            "name": "Michael (Admin)"
        }
        allowed, reason, sub = assert_user_execution_quota(admin_user, base_dir=self.test_dir)
        self.assertTrue(allowed)
        self.assertEqual(reason, "Admin host fallback")

    def test_ephemeral_ram_mode(self):
        user_id = "ephemeral_user"
        secret = "AIzaSyEphemeralSecret123"
        res = set_user_subscription(
            user_id=user_id,
            provider="gemini",
            credential=secret,
            storage_mode="ephemeral",
            base_dir=self.test_dir
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["is_ephemeral"])
        self.assertEqual(res["storage_mode"], "ephemeral")

        vault_path = os.path.join(self.test_dir, "subscriptions.json")
        if os.path.exists(vault_path):
            import json
            data = json.load(open(vault_path, "r", encoding="utf-8"))
            self.assertNotIn(user_id, data)

        fetched = get_user_subscription(user_id, base_dir=self.test_dir, include_decrypted=True)
        self.assertIsNotNone(fetched)
        self.assertTrue(fetched["is_ephemeral"])
        self.assertEqual(fetched["credential"], secret)

        deleted = delete_user_subscription(user_id, base_dir=self.test_dir)
        self.assertTrue(deleted)
        self.assertIsNone(get_user_subscription(user_id, base_dir=self.test_dir))

    def test_chamber_path_sanitization(self):
        chamber = get_user_runtime_chamber("user/../../bad!name@123")
        self.assertNotIn("..", str(chamber))
        self.assertNotIn("/", chamber.name)
        self.assertNotIn("\\", chamber.name)
        self.assertTrue(chamber.name.startswith("user_"))


if __name__ == "__main__":
    unittest.main()
