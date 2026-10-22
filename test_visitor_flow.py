"""Automated verification suite for public visitor flows, Zero-Trust clearance gating, and RBAC."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import server


class TestVisitorFlowsAndClearanceGating(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_profiles_file = Path(self.temp_dir) / "profiles.json"

        self.admin_token = "admin_secret_123"
        self.employer_token = "employer_secret_456"
        self.standard_token = "user_secret_789"

        self.admin_hash = hashlib.sha256(self.admin_token.encode("utf-8")).hexdigest()
        self.employer_hash = hashlib.sha256(self.employer_token.encode("utf-8")).hexdigest()
        self.standard_hash = hashlib.sha256(self.standard_token.encode("utf-8")).hexdigest()

        self.initial_data = {
            "metadata": {"schema_version": 2, "last_migrated": "2026-10-22T00:00:00"},
            "data": {
                self.admin_hash: {
                    "username": "TestAdmin",
                    "label": "Administrator",
                    "uuid": "admin-uuid-001",
                    "permissions": ["view:real_name", "master:view_tabs"],
                    "is_admin": True,
                    "is_employer": False,
                    "bypass_enabled": False,
                },
                self.employer_hash: {
                    "username": "EnterpriseEvaluator",
                    "label": "Employer Clearance",
                    "uuid": "employer-uuid-002",
                    "permissions": ["view:real_name", "master:view_tabs"],
                    "is_admin": False,
                    "is_employer": True,
                    "bypass_enabled": True,
                },
                self.standard_hash: {
                    "username": "PublicAuditor",
                    "label": "Restricted User",
                    "uuid": "user-uuid-003",
                    "permissions": ["view:tab:projects"],
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
        server.app.config["SECRET_KEY"] = "visitor_flow_test_secret_key"
        self.client = server.app.test_client()

    def tearDown(self):
        server.PROFILES_FILE = self.orig_profiles_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_public_visitor_landing_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("Michael Robberts", html)
        self.assertIn("Cybersecurity Analyst &amp; Native Accessibility Specialist", html)
        self.assertIn("Zero-Trust Architecture", html)
        self.assertIn("Clearance Authentication Gateway", html)
        self.assertNotIn("RESTRICTED_AREA // ACCESS_DENIED", html)
        self.assertIn("/bio", html)
        self.assertIn("/projects", html)
        self.assertIn("/certifications", html)

    def test_public_visitor_can_access_bio_without_authentication(self):
        response = self.client.get("/bio")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("System Architect &amp; Analyst", html)
        self.assertIn("The Mission &amp; Advocacy", html)

    def test_public_visitor_can_access_docs_without_authentication(self):
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)

    def test_public_visitor_accessing_clearance_modules_shows_clearance_required_page(self):
        for module in ["projects", "certifications", "blog"]:
            response = self.client.get(f"/{module}")
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)

            self.assertIn(f"CLEARANCE_REQUIRED // {module.upper()}", html)
            self.assertIn("MODULE PREVIEW // CONTENTS ARCHIVE", html)
            self.assertIn("AUTHENTICATE WITH CLEARANCE KEY", html)
            self.assertIn(f'value="/{module}"', html)
            self.assertNotIn("ACCESS DENIED: You lack permissions", html)

    def test_employer_bypass_link_unlocks_all_modules(self):
        bypass_url = "/access/employer-uuid-002"
        response = self.client.get(bypass_url, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        for module in ["projects", "certifications"]:
            mod_resp = self.client.get(f"/{module}")
            self.assertEqual(mod_resp.status_code, 200)
            mod_html = mod_resp.get_data(as_text=True)
            self.assertNotIn("CLEARANCE_REQUIRED", mod_html)

    def test_token_login_with_next_url_redirects_and_unlocks(self):
        response = self.client.post(
            "/login",
            data={
                "action": "login",
                "token": self.employer_token,
                "next": "/projects",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("CLEARANCE_REQUIRED", html)

    def test_token_login_with_specific_tab_permission_unlocks_only_authorized_tab(self):
        response = self.client.post(
            "/login",
            data={
                "action": "login",
                "token": self.standard_token,
                "next": "/projects",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        projects_resp = self.client.get("/projects")
        self.assertEqual(projects_resp.status_code, 200)
        self.assertNotIn("CLEARANCE_REQUIRED", projects_resp.get_data(as_text=True))

        certs_resp = self.client.get("/certifications")
        self.assertEqual(certs_resp.status_code, 200)
        self.assertIn("CLEARANCE_REQUIRED // CERTIFICATIONS", certs_resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
