"""Unit tests for Subscriber Security, Rate Limiting, Verification, and Compliance."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import notify_mod


class TestSubscriberSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sub_file = Path(self.temp_dir) / "subscribers.json"
        self.supp_file = Path(self.temp_dir) / "suppression.json"

        self.orig_sub = notify_mod.SUBSCRIBERS_FILE
        self.orig_supp = notify_mod.SUPPRESSION_FILE

        notify_mod.SUBSCRIBERS_FILE = self.sub_file
        notify_mod.SUPPRESSION_FILE = self.supp_file

    def tearDown(self):
        notify_mod.SUBSCRIBERS_FILE = self.orig_sub
        notify_mod.SUPPRESSION_FILE = self.orig_supp
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_email_masking(self):
        self.assertEqual(notify_mod.mask_email("security@domain.com"), "s***y@d***n.com")
        self.assertEqual(notify_mod.mask_email("a@b.com"), "a***@b***.com")
        self.assertEqual(notify_mod.mask_email(""), "***")

    def test_disposable_domain_rejection(self):
        self.assertTrue(notify_mod.is_disposable_domain("hacker@mailinator.com"))
        self.assertTrue(notify_mod.is_disposable_domain("bot@tempmail.com"))
        self.assertFalse(notify_mod.is_disposable_domain("valid@gmail.com"))
        self.assertFalse(notify_mod.is_disposable_domain("analyst@cybercorp.net"))

        with self.assertRaises(ValueError):
            notify_mod.add_subscriber("bot@mailinator.com", ["newsletter"])

    def test_rate_limiting(self):
        test_ip = "192.168.1.100"
        for _ in range(5):
            self.assertTrue(notify_mod._check_rate_limit(test_ip, max_requests=5, window_seconds=60))
        # 6th request within window must be rejected
        self.assertFalse(notify_mod._check_rate_limit(test_ip, max_requests=5, window_seconds=60))

    def test_file_permissions_0o600(self):
        notify_mod.add_subscriber("reader@example.com", ["newsletter"], status="active")
        self.assertTrue(self.sub_file.exists())
        mode = oct(self.sub_file.stat().st_mode & 0o777)
        self.assertEqual(mode, "0o600")

    def test_double_opt_in_verification_workflow(self):
        # 1. Add pending subscriber
        entry = notify_mod.add_subscriber("newuser@example.com", ["newsletter", "releases"], status="pending")
        self.assertEqual(entry["status"], "pending")
        token = entry["token"]
        self.assertTrue(len(token) >= 32)

        # Pending user should NOT appear in active recipients
        active_recipients = [s["email"] for s in notify_mod.recipients_for("newsletter")]
        self.assertNotIn("newuser@example.com", active_recipients)

        # 2. Verify token
        ok, msg, verified = notify_mod.verify_subscriber_token(token)
        self.assertTrue(ok)
        self.assertEqual(verified["status"], "active")

        # Now active user MUST appear in active recipients
        active_recipients = [s["email"] for s in notify_mod.recipients_for("newsletter")]
        self.assertIn("newuser@example.com", active_recipients)

    def test_unsubscribe_and_suppression(self):
        entry = notify_mod.add_subscriber("optout@example.com", ["newsletter"], status="active")
        token = entry["token"]

        self.assertFalse(notify_mod.is_suppressed("optout@example.com"))

        ok, msg = notify_mod.unsubscribe_subscriber_token(token)
        self.assertTrue(ok)

        # Must be suppressed and removed from recipients
        self.assertTrue(notify_mod.is_suppressed("optout@example.com"))
        active = [s["email"] for s in notify_mod.recipients_for("newsletter")]
        self.assertNotIn("optout@example.com", active)


if __name__ == "__main__":
    result = unittest.main(exit=False)
    import os
    os._exit(0 if result.result.wasSuccessful() else 1)
