"""Comprehensive Test Suite for Cyber Threat Intelligence Email Preferences & Safe Engagement Engine.

Verifies:
1. Subscriber preference lifecycle (creation, update, schema normalization).
2. Token-based preference center retrieval and updates.
3. RFC 8058 One-Click Unsubscribe (GET & POST).
4. Multi-cadence personalized email assembly (Hybrid Brief, Daily Full Story, Quick Threat Wire, Weekly Digest).
5. Safe engagement hooks (Alt-Appetite Teaser, Audio Edition CTA, Zero-Day Radar).
6. Anonymous aggregate metrics tracking (sends and clicks) in traffic_metrics.json.
7. Local mock mailbox dispatch verification.
"""

import os
import json
import unittest
from pathlib import Path

from config import Config
from server import app
from notify_mod import (
    SUBSCRIBERS_FILE,
    METRICS_FILE,
    load_subscribers,
    subscribe_newsletter,
    get_subscriber_by_token,
    get_subscriber_by_email,
    purge_subscriber_by_token,
    update_subscriber_preferences,
    unsubscribe_by_token,
    record_newsletter_send,
    record_newsletter_click,
    encode_tracking_token,
    decode_tracking_token,
    touch_subscriber_activity,
    purge_inactive_subscribers,
    notify_newsletter,
    _store_lock,
    _metrics_lock
)
from email_engine import (
    build_personalized_newsletter_email,
    load_local_mailbox,
    clear_local_mailbox
)


class TestNewsletterPreferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        # Backup existing subscribers and metrics files if present
        self.subscribers_backup = None
        if SUBSCRIBERS_FILE.exists():
            try:
                self.subscribers_backup = SUBSCRIBERS_FILE.read_text(encoding="utf-8")
            except Exception:
                pass

        self.metrics_backup = None
        if METRICS_FILE.exists():
            try:
                self.metrics_backup = METRICS_FILE.read_text(encoding="utf-8")
            except Exception:
                pass

        # Clear test mailbox
        clear_local_mailbox()

        # Initialize clean test subscribers file
        with _store_lock:
            SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SUBSCRIBERS_FILE.write_text(json.dumps([], indent=2), encoding="utf-8")

        # Initialize clean metrics
        with _metrics_lock:
            base_metrics = {
                "total_views": 100,
                "unique_visitors": ["v1"],
                "paths": {"/": 100},
                "newsletter": {
                    "sends": {"total": 0, "by_format": {}, "by_appetite": {}},
                    "clicks": {"total": 0, "by_slot": {}}
                }
            }
            METRICS_FILE.write_text(json.dumps(base_metrics, indent=2), encoding="utf-8")

    def tearDown(self):
        # Restore backups
        with _store_lock:
            if self.subscribers_backup is not None:
                SUBSCRIBERS_FILE.write_text(self.subscribers_backup, encoding="utf-8")
            elif SUBSCRIBERS_FILE.exists():
                SUBSCRIBERS_FILE.unlink()

        with _metrics_lock:
            if self.metrics_backup is not None:
                METRICS_FILE.write_text(self.metrics_backup, encoding="utf-8")

    def test_01_subscribe_and_schema_normalization(self):
        """Verify subscriber registration creates complete V1 schema."""
        sub = subscribe_newsletter(
            email="analyst@soc-defense.org",
            delivery_format="hybrid_brief",
            primary_appetite="cyber_thriller",
            topics=["zero_days", "cisa_kev"]
        )
        self.assertEqual(sub["email"], "analyst@soc-defense.org")
        self.assertEqual(sub["status"], "active")
        self.assertTrue(sub["subscriber_id"].startswith("sub_"))
        self.assertTrue(len(sub["token"]) >= 24)
        self.assertEqual(sub["delivery"]["format"], "hybrid_brief")
        self.assertEqual(sub["delivery"]["cadence"], "daily")
        self.assertEqual(sub["content"]["primary_appetite"], "cyber_thriller")
        self.assertEqual(sub["content"]["topics"], ["zero_days", "cisa_kev"])
        self.assertTrue(sub["engagement_modules"]["alt_appetite_teaser"])
        self.assertTrue(sub["engagement_modules"]["audio_link"])
        self.assertTrue(sub["engagement_modules"]["zero_day_radar"])

    def test_02_subscribe_via_api_endpoint(self):
        """Verify POST /api/newsletter/subscribe endpoint."""
        res = self.client.post("/api/newsletter/subscribe", json={
            "email": "ciso@enterprise.com",
            "format": "full_story_daily",
            "appetite": "executive_espresso"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue("token" in data)

        # Confirm persisted in store
        sub = get_subscriber_by_token(data["token"])
        self.assertIsNotNone(sub)
        self.assertEqual(sub["email"], "ciso@enterprise.com")
        self.assertEqual(sub["delivery"]["format"], "full_story_daily")
        self.assertEqual(sub["content"]["primary_appetite"], "executive_espresso")

    def test_03_token_lookup_and_preference_update(self):
        """Verify token retrieval and updating cadence and engagement modules."""
        sub = subscribe_newsletter("hacker@redteam.net", "hybrid_brief", "snarky_hacker")
        token = sub["token"]

        # Update to weekly digest with no audio link
        updated = update_subscriber_preferences(
            token=token,
            delivery_format="weekly_digest",
            primary_appetite="deep_dive",
            engagement_modules={"alt_appetite_teaser": True, "audio_link": False, "zero_day_radar": True}
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["delivery"]["format"], "weekly_digest")
        self.assertEqual(updated["delivery"]["cadence"], "weekly")
        self.assertEqual(updated["content"]["primary_appetite"], "deep_dive")
        self.assertFalse(updated["engagement_modules"]["audio_link"])
        self.assertTrue(updated["engagement_modules"]["zero_day_radar"])

    def test_04_rfc8058_one_click_unsubscribe(self):
        """Verify RFC 8058 compliant GET and POST unsubscribe."""
        sub = subscribe_newsletter("user@test.org", "hybrid_brief", "cyber_thriller")
        token = sub["token"]

        # POST RFC 8058 One-Click Unsubscribe
        res = self.client.post("/newsletter/unsubscribe", json={"token": token})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")

        # Confirm status updated to unsubscribed
        refreshed = get_subscriber_by_token(token)
        self.assertEqual(refreshed["status"], "unsubscribed")

    def test_05_email_builder_hybrid_brief_with_hooks(self):
        """Verify Hybrid Brief email rendering with headlines, dossier, and safe hooks."""
        sub = {
            "email": "reader@example.com",
            "token": "tok_1234567890abcdef123456",
            "status": "active",
            "delivery": {"format": "hybrid_brief", "cadence": "daily"},
            "content": {"primary_appetite": "cyber_thriller", "topics": ["zero_days"]},
            "engagement_modules": {
                "alt_appetite_teaser": True,
                "audio_link": True,
                "zero_day_radar": True
            }
        }
        manifest = {
            "dispatched_at": "2026-11-02 10:00:00",
            "items": [
                {
                    "story_id": "cve-2026-0001",
                    "title": "Ivanti Connect Secure Zero-Day Exploit",
                    "threat_level": "CRITICAL",
                    "score": 95,
                    "cves": ["CVE-2026-0001"],
                    "summary": "Active unauthenticated remote code execution.",
                    "remediation": "Apply emergency hotfix immediately.",
                    "source": "CISA"
                },
                {
                    "story_id": "cve-2026-0002",
                    "title": "SolarWinds Access Bypass",
                    "threat_level": "HIGH",
                    "score": 88,
                    "cves": ["CVE-2026-0002"],
                    "summary": "Improper authentication on management interface.",
                    "remediation": "Restrict management access to internal VPN.",
                    "source": "NVD"
                }
            ]
        }

        subject, html_body, plain_text, headers = build_personalized_newsletter_email(
            subscriber=sub,
            manifest=manifest,
            base_url="https://mikey-mike.com"
        )

        # Subject verification
        self.assertIn("Ivanti Connect Secure Zero-Day Exploit", subject)
        self.assertIn("Cyber Intel Brief", subject)

        # Headers verification (RFC 8058)
        self.assertIn("List-Unsubscribe", headers)
        self.assertIn("https://mikey-mike.com/newsletter/unsubscribe?token=tok_1234567890abcdef123456", headers["List-Unsubscribe"])
        self.assertEqual(headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

        # HTML slot verifications
        self.assertIn("Cyber Threat Intelligence Dispatch", html_body)
        self.assertIn("Hybrid Brief (Headlines + Featured Dossier)", html_body)
        self.assertIn("🍿 Cyber Thriller", html_body)
        self.assertIn("Advisory Headlines Brief", html_body)
        self.assertIn("SolarWinds Access Bypass", html_body)
        self.assertIn("Featured Dossier", html_body)
        self.assertIn("Ivanti Connect Secure Zero-Day Exploit", html_body)

        # Safe Hooks verification
        # 1. Alt-appetite teaser
        self.assertIn("Alternate Perspective Preview", html_body)
        self.assertIn("Curiosity Hook", html_body)
        # 2. Audio Edition CTA
        self.assertIn("Accessible Audio Suite", html_body)
        self.assertIn("Stream Audio", html_body)
        # 3. Bonus Zero-Day Radar
        self.assertIn("Bonus Zero-Day & KEV Radar", html_body)
        self.assertIn("CVE-2026-0001", html_body)

    def test_06_email_builder_quick_threat_wire(self):
        """Verify Quick Threat Wire renders rapid bullet items without long narratives."""
        sub = {
            "email": "analyst@rapidwire.io",
            "token": "tok_wire_1234567890123456",
            "status": "active",
            "delivery": {"format": "quick_threat_wire", "cadence": "daily"},
            "content": {"primary_appetite": "defense_playbook", "topics": ["cisa_kev"]},
            "engagement_modules": {"alt_appetite_teaser": False, "audio_link": True, "zero_day_radar": False}
        }
        manifest = {
            "dispatched_at": "2026-11-02 10:00:00",
            "items": [
                {
                    "story_id": "cve-2026-1111",
                    "title": "Fortinet FortiGate RCE",
                    "threat_level": "CRITICAL",
                    "score": 98,
                    "cves": ["CVE-2026-1111"],
                    "summary": "Heap buffer overflow in sslvpnd.",
                    "remediation": "Upgrade firmware to 7.4.3.",
                    "source": "Fortinet"
                }
            ]
        }

        subject, html_body, plain_text, headers = build_personalized_newsletter_email(sub, manifest, "https://mikey-mike.com")
        self.assertIn("[Threat Wire]", subject)
        self.assertIn("Rapid Threat Wire (1-Min Bulletins)", html_body)
        self.assertIn("Fortinet FortiGate RCE", html_body)
        # Verify Alt-Appetite teaser was omitted since alt_appetite_teaser is False
        self.assertNotIn("Alternate Perspective Preview", html_body)
        # Audio link is True
        self.assertIn("Accessible Audio Suite", html_body)

    def test_07_tracking_redirector_and_anonymous_metrics(self):
        """Verify /newsletter/r/<link_id> redirects safely and updates traffic_metrics.json without PII."""
        token = encode_tracking_token("alt_teaser", "/newsletter/story/cve-2026-0001?appetite=snarky_hacker")
        self.assertTrue(len(token) > 0)

        # Perform redirect request
        res = self.client.get(f"/newsletter/r/{token}")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.location, "/newsletter/story/cve-2026-0001?appetite=snarky_hacker")

        # Verify aggregate metrics in traffic_metrics.json
        with _metrics_lock:
            metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
            nl_metrics = metrics.get("newsletter", {})
            clicks = nl_metrics.get("clicks", {})
            self.assertEqual(clicks.get("total"), 1)
            self.assertEqual(clicks.get("by_slot", {}).get("alt_teaser"), 1)

    def test_08_end_to_end_dispatch_to_local_mailbox(self):
        """Verify full dispatch flow delivers customized emails to mock mailbox."""
        # Subscribe 2 test users with different preferences
        subscribe_newsletter("user1@agency.gov", "hybrid_brief", "cyber_thriller")
        subscribe_newsletter("user2@enterprise.com", "quick_threat_wire", "executive_espresso")

        # Trigger newsletter dispatch
        result = notify_newsletter(base_url="http://localhost:5001")
        self.assertEqual(result["sent"], 2)

        # Check local mailbox
        emails = load_local_mailbox(limit=10)
        self.assertEqual(len(emails), 2)

        recipients = [e["to"] for e in emails]
        self.assertIn("user1@agency.gov", recipients)
        self.assertIn("user2@enterprise.com", recipients)

        # Verify headers in local mailbox
        user1_mail = next(e for e in emails if e["to"] == "user1@agency.gov")
        self.assertIn("List-Unsubscribe", user1_mail.get("headers", {}))
        self.assertEqual(user1_mail["headers"].get("List-Unsubscribe-Post"), "List-Unsubscribe=One-Click")

        # Verify sends counter updated in traffic_metrics.json
        with _metrics_lock:
            metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
            sends = metrics.get("newsletter", {}).get("sends", {})
            self.assertEqual(sends.get("total"), 2)
            self.assertEqual(sends.get("by_format", {}).get("hybrid_brief"), 1)
            self.assertEqual(sends.get("by_format", {}).get("quick_threat_wire"), 1)

    def test_09_terms_and_conditions_note_and_route(self):
        """Verify subscription forms include Terms & Conditions note, link, and route."""
        # 1. Check newsletter template renders terms consent note and link
        res = self.client.get("/newsletter")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("/terms", html)
        self.assertIn("Terms and Conditions", html)
        self.assertIn("By clicking", html)

        # 2. Check /terms and /terms-and-conditions endpoints
        res_terms = self.client.get("/terms")
        self.assertEqual(res_terms.status_code, 200)
        terms_content = res_terms.get_data(as_text=True)
        self.assertIn("Cyber Threat Intelligence Feed & Dispatches: Terms and Conditions", terms_content)
        self.assertIn("1-Click Unsubscribe & Complete Data Purge Guarantee", terms_content)

        res_alias = self.client.get("/terms-and-conditions")
        self.assertEqual(res_alias.status_code, 200)

    def test_10_one_click_unsubscribe_purge_with_devcore_fammaly(self):
        """Verify embedded 1-click email button and complete data purge with devcore.fammaly@gmail.com."""
        test_email = "devcore.fammaly@gmail.com"

        # 1. Subscribe test user
        sub = subscribe_newsletter(test_email, "hybrid_brief", "cyber_thriller")
        token = sub["token"]
        self.assertIsNotNone(get_subscriber_by_email(test_email))
        self.assertIsNotNone(get_subscriber_by_token(token))

        # 2. Dispatch newsletter and inspect email body
        clear_local_mailbox()
        notify_newsletter(base_url="https://cyber.test")
        mailbox = load_local_mailbox()
        target_email = next((m for m in mailbox if m.get("to") == test_email), None)
        self.assertIsNotNone(target_email)

        email_html = target_email.get("html", "")
        email_text = target_email.get("text", "")

        # Verify embedded 1-click unsubscribe & purge button
        self.assertIn("1-Click Unsubscribe & Purge Data", email_html)
        self.assertIn(f"/newsletter/unsubscribe?token={token}&purge=1", email_html)
        self.assertIn("1-Click Unsubscribe & Purge Data:", email_text)

        # 3. Trigger 1-Click Unsubscribe via GET (simulating user clicking the email button)
        purge_url = f"/newsletter/unsubscribe?token={token}&purge=1"
        res = self.client.get(purge_url)
        self.assertEqual(res.status_code, 200)
        res_html = res.get_data(as_text=True)
        self.assertIn("Unsubscribed & Data Purged Successfully", res_html)
        self.assertIn(test_email, res_html)

        # 4. Verify subscriber data is completely purged from memory and disk
        self.assertIsNone(get_subscriber_by_email(test_email))
        self.assertIsNone(get_subscriber_by_token(token))
        with _store_lock:
            all_subs = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            remaining_emails = [s.get("email") for s in all_subs]
            self.assertNotIn(test_email, remaining_emails)

        # 5. Also verify POST with purge=True completes full purge
        sub2 = subscribe_newsletter(test_email, "quick_threat_wire", "defense_playbook")
        token2 = sub2["token"]
        self.assertIsNotNone(get_subscriber_by_email(test_email))

        res_post = self.client.post("/newsletter/unsubscribe", json={"token": token2, "purge": True})
        self.assertEqual(res_post.status_code, 200)
        self.assertTrue(res_post.get_json()["purged"])
        self.assertIsNone(get_subscriber_by_email(test_email))
        self.assertIsNone(get_subscriber_by_token(token2))

    def test_11_terms_and_email_credibility_activity_inbox_relief(self):
        """Verify Terms & Conditions content, data handling disclosure, dev updates, credibility, and relief button."""
        test_email = "devcore.fammaly@gmail.com"
        sub = subscribe_newsletter(test_email, "hybrid_brief", "cyber_thriller")
        token = sub["token"]

        # 1. Dispatch email and verify content modules
        clear_local_mailbox()
        notify_newsletter(base_url="https://cyber.test")
        mailbox = load_local_mailbox()
        target_email = next((m for m in mailbox if m.get("to") == test_email), None)
        self.assertIsNotNone(target_email)

        email_html = target_email.get("html", "")
        email_text = target_email.get("text", "")

        # A. Inbox relief notice
        expected_relief = "If you have not subscribed to this newsletter, please just hit that pretty button below to relieve your inbox."
        self.assertIn(expected_relief, email_html)
        self.assertIn(expected_relief, email_text)

        # B. Pretty 1-click unsubscribe button
        self.assertIn("1-Click Unsubscribe & Purge Data", email_html)
        self.assertIn(f"/newsletter/unsubscribe?token={token}&purge=1", email_html)

        # C. E-Profile development advertising & new releases
        self.assertIn("E-Profile Development & Engineering News", email_html)
        self.assertIn("What's Happening in E-Profile Development & New Releases", email_html)
        self.assertIn("Accessible Audio Suite", email_html)
        self.assertIn("E-PROFILE DEVELOPMENT & RELEASES:", email_text)

        # D. Subscription activity requirement
        self.assertIn("Subscription Activity Requirement", email_html)
        self.assertIn("require subscribers to visit the site from time to time", email_html)
        self.assertIn("SUBSCRIPTION ACTIVITY REQUIREMENT:", email_text)

        # E. Author credibility, Credly badge & LinkedIn
        self.assertIn("Michael Robberts", email_html)
        self.assertIn("https://www.linkedin.com/in/michael-robberts-40b68a180", email_html)
        self.assertIn("https://www.credly.com/users/michael-robberts.d08637aa", email_html)
        self.assertIn("data-share-badge-id=\"95063855-9875-40cd-9d3f-13bc9ad1448e\"", email_html)
        self.assertIn("https://www.linkedin.com/in/michael-robberts-40b68a180", email_text)
        self.assertIn("https://www.credly.com/users/michael-robberts.d08637aa", email_text)

        # 2. Verify Terms & Conditions Page
        res_terms = self.client.get("/terms")
        self.assertEqual(res_terms.status_code, 200)
        terms_html = res_terms.get_data(as_text=True)

        # Zero Database Architecture disclosure
        self.assertIn("We do not maintain or operate a database.", terms_html)
        self.assertIn("subscribers.json", terms_html)

        # Development advertising disclosure
        self.assertIn("Scope of Dispatches, Development Advertising & Policy Notices", terms_html)

        # Subscription activity requirement
        self.assertIn("Subscription Activity Requirement & Inactivity Purge Policy", terms_html)
        self.assertIn("Presumption of Non-Subscription", terms_html)

        # Author Credibility & Credly / LinkedIn embeds
        self.assertIn("https://www.linkedin.com/in/michael-robberts-40b68a180", terms_html)
        self.assertIn("https://www.credly.com/users/michael-robberts.d08637aa", terms_html)
        self.assertIn("data-share-badge-id=\"95063855-9875-40cd-9d3f-13bc9ad1448e\"", terms_html)
        self.assertIn("Python for Data Science", terms_html)

    def test_12_subscriber_activity_touch_and_purge(self):
        """Verify activity timestamps, email click tracking updates, and inactive purge."""
        test_email = "devcore.fammaly@gmail.com"
        sub = subscribe_newsletter(test_email, "hybrid_brief", "cyber_thriller")
        token = sub["token"]

        # Initial last_active_at
        initial_sub = get_subscriber_by_token(token)
        self.assertIn("last_active_at", initial_sub)

        # Simulate clicking tracked link in email
        track_tok = encode_tracking_token("dev_releases", "/projects", sub_token=token)
        res_redir = self.client.get(f"/newsletter/r/{track_tok}")
        self.assertEqual(res_redir.status_code, 302)
        self.assertEqual(res_redir.location, "/projects")

        # Simulate preference center view
        res_pref = self.client.get(f"/newsletter/preferences?token={token}")
        self.assertEqual(res_pref.status_code, 200)

        # Test inactive subscriber purge logic with an expired subscriber
        stale_email = "stale.reader@example.com"
        stale_sub = subscribe_newsletter(stale_email, "quick_threat_wire", "snarky_hacker")
        with _store_lock:
            subs = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            for s in subs:
                if s.get("email") == stale_email:
                    s["last_active_at"] = "2025-01-01 00:00:00"
            SUBSCRIBERS_FILE.write_text(json.dumps(subs, indent=2), encoding="utf-8")

        purged_list = purge_inactive_subscribers(inactivity_days=30)
        self.assertEqual(len(purged_list), 1)
        self.assertEqual(purged_list[0]["email"], stale_email)
        self.assertIsNone(get_subscriber_by_email(stale_email))
        self.assertIsNotNone(get_subscriber_by_email(test_email))


if __name__ == "__main__":
    unittest.main()
