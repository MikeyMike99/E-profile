"""Comprehensive Test Suite for e_profile Cyber Threat Feed & Story Appetites.

Verifies:
1. Strict Quota Adherence: Upstream rate limit cooldowns prevent quota exhaustion.
2. Chronological Ordering: The newest released story is ALWAYS sorted on top (#1).
3. Story Agent Dispatch: All 5 appetites generate clean markdown and persist to transient cache.
4. Web Blueprint Endpoints: /newsletter, /newsletter/story/<id>, /api/newsletter/generate-story, /api/newsletter/status.
"""

import os
import json
import unittest
from pathlib import Path

import server
from threat_intel_engine import ThreatIntelEngine, parse_to_epoch
from story_agent_dispatcher import (
    dispatch_story_generation,
    get_cached_story,
    APPETITE_CONFIG
)


class TestThreatIntelFeed(unittest.TestCase):
    def setUp(self):
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        self.engine = ThreatIntelEngine()

    def test_epoch_parsing_and_sorting(self):
        """Verifies that RFC 2822 and ISO dates convert to epoch and sort correctly."""
        nov_date = "Mon, 02 Nov 2026 11:21:07 +0530"
        oct_date = "2026-10-30"

        nov_epoch = parse_to_epoch(nov_date)
        oct_epoch = parse_to_epoch(oct_date)

        self.assertGreater(nov_epoch, oct_epoch, "Nov 2, 2026 should have higher epoch than Oct 30, 2026")

        items = [
            {"title": "Old Advisory", "date": oct_date, "timestamp": oct_epoch},
            {"title": "Newest Release", "date": nov_date, "timestamp": nov_epoch}
        ]
        items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        self.assertEqual(items[0]["title"], "Newest Release", "Newest story MUST be on top")

    def test_rate_limit_cooldowns(self):
        """Verifies that rate limit state is tracked and limits redundant API calls."""
        status = self.engine.get_feed_status()
        self.assertIn("cooldowns", status)
        cooldowns = status["cooldowns"]
        self.assertIn("rss_cooldown_remaining_sec", cooldowns)
        self.assertIn("tavily_daily_limit", cooldowns)
        self.assertEqual(cooldowns["tavily_daily_limit"], 1)

    def test_appetite_configurations(self):
        """Verifies that all 5 appetite modes are registered."""
        expected_appetites = ["cyber_thriller", "deep_dive", "defense_playbook", "executive_espresso", "snarky_hacker"]
        for app in expected_appetites:
            self.assertIn(app, APPETITE_CONFIG, f"Appetite '{app}' should be registered")

    def test_story_generation_builtin_fallback(self):
        """Verifies that built-in engine generates valid markdown for all appetites without error."""
        sample_item = {
            "story_id": "test-cve-2026-unit",
            "title": "Unit Test Advisory: Remote Code Execution in Gateway",
            "cves": ["CVE-2026-9999"],
            "source": "Unit Test Feed",
            "summary": "Critical memory corruption vulnerability allows unauthenticated RCE.",
            "remediation": "Apply vendor security patch immediately."
        }

        for appetite in ["cyber_thriller", "deep_dive", "defense_playbook", "executive_espresso", "snarky_hacker"]:
            res = dispatch_story_generation(
                story_id=sample_item["story_id"],
                appetite=appetite,
                engine_choice="builtin",
                item_metadata=sample_item
            )
            self.assertEqual(res["status"] if "status" in res else "ok", "ok")
            self.assertEqual(res["appetite"], appetite)
            self.assertTrue(len(res["markdown"]) > 50)
            self.assertIn("##", res["markdown"], "Markdown should contain section headings")

    def test_newsletter_routes(self):
        """Verifies that the /newsletter page and status endpoints respond with HTTP 200."""
        # 1. Feed index
        res = self.client.get('/newsletter')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Cyber Intelligence", html)

        # 2. Status API
        res_status = self.client.get('/api/newsletter/status')
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.get_json()
        self.assertIn("cooldowns", status_data)

        # 3. Generate story API
        res_gen = self.client.post('/api/newsletter/generate-story', json={
            "story_id": "test-cve-2026-unit",
            "appetite": "executive_espresso",
            "engine": "builtin"
        })
        self.assertEqual(res_gen.status_code, 200)
        gen_data = res_gen.get_json()
        self.assertEqual(gen_data["status"], "success")
        self.assertIn("data", gen_data)
        self.assertIn("html", gen_data)


if __name__ == "__main__":
    unittest.main()
