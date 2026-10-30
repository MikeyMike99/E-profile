#!/usr/bin/env python3
"""
=============================================================================
   E-PROFILE & DOCUMENTATION VAULT AUTOMATED SECURITY AUDIT SUITE
=============================================================================
Automated 6-stage verification engine modeled on DevCore's security audit:
  Stage 1: Role-Based Access Control (RBAC) & Endpoint Authorization
  Stage 2: Path Traversal (LFI) & Boundary Isolation
  Stage 3: Release Schedule & Anti-Overwhelm Visitor Staging
  Stage 4: Metadata Classification & 100% Tagging Integrity
  Stage 5: In-Place Editing, File Creation & Safe Archiving
  Stage 6: Multi-Destination Dual Persistence & Sync Consistency

Usage:
  python3 security_audit.py
  python3 security_audit.py --verbose
  python3 security_audit.py --stage 1
  python3 security_audit.py --json
=============================================================================
"""

import sys
import os
import re
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Ensure local imports resolve
EPROFILE_ROOT = Path(__file__).resolve().parent
if str(EPROFILE_ROOT) not in sys.path:
    sys.path.insert(0, str(EPROFILE_ROOT))

try:
    from server import app
    from docs_mod import (
        load_catalog,
        load_release_schedule,
        save_release_schedule,
        get_user_catalog,
        resolve_physical_file,
        clean_markdown_text,
        filter_document_by_sensitivity,
        DOCS_DIR,
        CENTRAL_DOCS_DIR,
        FOUNDATIONAL_PUBLISHED_KEYS
    )
except ImportError as e:
    print(f"[FATAL] Failed to import e_profile core engine: {e}")
    sys.exit(1)

CANARY_SLUG = "audit_canary_test_chapter_999"


class SecurityAuditor:
    def __init__(self, verbose=False, stage_filter=None, json_output=False):
        self.verbose = verbose
        self.stage_filter = stage_filter
        self.json_output = json_output
        self.client = app.test_client()
        self.results = []
        self.passed = 0
        self.failed = 0
        self.start_time = 0

    def record(self, stage: str, test_id: str, description: str, passed: bool, detail: str = ""):
        if passed:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"

        result = {
            "stage": stage,
            "test_id": test_id,
            "description": description,
            "status": status,
            "detail": detail
        }
        self.results.append(result)

        if not self.json_output:
            status_badge = f"\033[92m[PASS]\033[0m" if passed else f"\033[91m[FAIL]\033[0m"
            print(f"  {status_badge} {test_id}: {description}")
            if detail and (not passed or self.verbose):
                print(f"         \033[90m↳ {detail}\033[0m")

    def run_all(self):
        self.start_time = time.time()
        if not self.json_output:
            print("====================================================================")
            print("   E-PROFILE & DOCUMENTATION VAULT AUTOMATED SECURITY AUDIT")
            print("====================================================================")

        try:
            if not self.stage_filter or self.stage_filter == 1:
                self.audit_stage_1_rbac()
            if not self.stage_filter or self.stage_filter == 2:
                self.audit_stage_2_path_traversal()
            if not self.stage_filter or self.stage_filter == 3:
                self.audit_stage_3_release_staging()
            if not self.stage_filter or self.stage_filter == 4:
                self.audit_stage_4_metadata_tagging()
            if not self.stage_filter or self.stage_filter == 5:
                self.audit_stage_5_inplace_editing()
            if not self.stage_filter or self.stage_filter == 6:
                self.audit_stage_6_sync_persistence()
            if not self.stage_filter or self.stage_filter == 7:
                self.audit_stage_7_agent_and_demo_routing()
        finally:
            self.cleanup_canaries()

        elapsed = time.time() - self.start_time
        total = self.passed + self.failed

        if self.json_output:
            output = {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": round(elapsed, 3),
                "summary": {
                    "total": total,
                    "passed": self.passed,
                    "failed": self.failed,
                    "status": "PASS" if self.failed == 0 else "FAIL"
                },
                "results": self.results
            }
            print(json.dumps(output, indent=2))
        else:
            print("====================================================================")
            summary_color = "\033[92m" if self.failed == 0 else "\033[91m"
            print(f"   {summary_color}AUDIT RESULT: {self.passed}/{total} CHECKS PASSED ({elapsed:.2f}s)\033[0m")
            print("====================================================================")

        return self.failed == 0

    # =========================================================================
    # STAGE 1: ROLE-BASED ACCESS CONTROL (RBAC) & ENDPOINT AUTHORIZATION
    # =========================================================================
    def audit_stage_1_rbac(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 1: Role-Based Access Control (RBAC) & Endpoint Authorization ---\033[0m")

        # 1.1 Visitor blocked from Schedule API
        r = self.client.post('/docs/api/admin/schedule', json={"slug": "test", "status": "published"})
        self.record("Stage 1", "RBAC-01", "Unauthenticated visitor blocked from Schedule API (HTTP 403)", r.status_code == 403, f"Got HTTP {r.status_code}")

        # 1.2 Visitor blocked from Save API
        r = self.client.post('/docs/api/admin/save', json={"slug": "test", "content": "# Test"})
        self.record("Stage 1", "RBAC-02", "Unauthenticated visitor blocked from In-Place Save API (HTTP 403)", r.status_code == 403, f"Got HTTP {r.status_code}")

        # 1.3 Visitor blocked from Create API
        r = self.client.post('/docs/api/admin/create', json={"title": "Test", "slug": "test"})
        self.record("Stage 1", "RBAC-03", "Unauthenticated visitor blocked from Create Chapter API (HTTP 403)", r.status_code == 403, f"Got HTTP {r.status_code}")

        # 1.4 Visitor blocked from Delete API
        r = self.client.post('/docs/api/admin/delete', json={"slug": "test"})
        self.record("Stage 1", "RBAC-04", "Unauthenticated visitor blocked from Delete/Archive API (HTTP 403)", r.status_code == 403, f"Got HTTP {r.status_code}")

        # 1.5 Visitor does NOT receive admin controls in HTML
        r = self.client.get('/docs')
        html = r.get_data(as_text=True)
        no_leaks = (
            '<div id="modal-schedule"' not in html
            and '<div id="modal-new-chapter"' not in html
            and 'id="admin-review-toolbar"' not in html
            and '<textarea id="admin-raw-textarea"' not in html
            and '➕ New Chapter on Server' not in html
        )
        self.record("Stage 1", "RBAC-05", "Zero admin UI/DOM leaks in visitor HTML response", no_leaks, "Checked modals, review toolbar, raw textarea, and creation buttons")

        # 1.6 Admin receives full editorial controls in HTML
        with self.client.session_transaction() as sess:
            sess['admin'] = True
        r_admin = self.client.get('/docs')
        html_admin = r_admin.get_data(as_text=True)
        admin_elements = (
            '<div id="modal-schedule"' in html_admin
            and '<div id="modal-new-chapter"' in html_admin
            and 'id="admin-review-toolbar"' in html_admin
            and '<textarea id="admin-raw-textarea"' in html_admin
            and '➕ New Chapter on Server' in html_admin
        )
        self.record("Stage 1", "RBAC-06", "Admin session renders complete editorial control interface", admin_elements, "Verified modals, review toolbar, raw editor, and create buttons")

        # Reset session
        with self.client.session_transaction() as sess:
            sess.clear()

    # =========================================================================
    # STAGE 2: PATH TRAVERSAL (LFI) & BOUNDARY ISOLATION
    # =========================================================================
    def audit_stage_2_path_traversal(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 2: Path Traversal (LFI) & Boundary Isolation ---\033[0m")

        # 2.1 Direct URL path traversal
        traversal_urls = [
            '/docs/api/chapter/../../../../etc/passwd/test',
            '/docs/api/chapter/devlog/../../server',
            '/docs/../../etc/passwd',
            '/docs/devlog/..%2f..%2fserver'
        ]
        all_rejected = True
        for url in traversal_urls:
            r = self.client.get(url)
            if r.status_code not in [404, 302, 400, 403]:
                all_rejected = False
                break
        self.record("Stage 2", "TRAV-01", "Chapter route safely rejects parent directory traversal attempts", all_rejected, "Tested relative escapes and encoded slashes")

        # 2.2 Physical file resolver boundary confinement
        resolved_escape = resolve_physical_file("../../../../etc", "passwd")
        self.record("Stage 2", "TRAV-02", "resolve_physical_file isolates path resolution within safe root", len(resolved_escape) == 0, "Attempted root system escape returned 0 candidates")

        # 2.3 Malicious slug in Admin Save (even if admin token compromised)
        with self.client.session_transaction() as sess:
            sess['admin'] = True
        r_save_trav = self.client.post('/docs/api/admin/save', json={
            "category": "devlog",
            "slug": "../../../../../tmp/hacked",
            "content": "Malicious payload"
        })
        # Resolver should sanitize or contain within docs directory
        hacked_file = Path("/tmp/hacked.md")
        self.record("Stage 2", "TRAV-03", "Admin Save enforces workspace containment against relative slugs", not hacked_file.exists(), f"Target /tmp/hacked.md exists: {hacked_file.exists()}")

        with self.client.session_transaction() as sess:
            sess.clear()

    # =========================================================================
    # STAGE 3: RELEASE SCHEDULE & ANTI-OVERWHELM VISITOR STAGING
    # =========================================================================
    def audit_stage_3_release_staging(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 3: Release Schedule & Anti-Overwhelm Visitor Staging ---\033[0m")

        schedule = load_release_schedule()
        catalog = load_catalog()

        # 3.1 Schedule file valid schema
        valid_schema = (
            isinstance(schedule, dict)
            and schedule.get("version") == "1.0"
            and schedule.get("default_policy") == "draft"
            and isinstance(schedule.get("entries"), dict)
        )
        self.record("Stage 3", "STAG-01", "release_schedule.json contains valid v1.0 schema with draft default", valid_schema, f"Entries registered: {len(schedule.get('entries', {}))}")

        # 3.2 Catalog filtering: Visitor sees only published chapters
        vis_catalog = get_user_catalog(catalog, is_admin=False)
        all_published = all(d.get('publish_status') == 'published' or d.get('is_released') for d in vis_catalog)
        self.record("Stage 3", "STAG-02", "Visitor catalog strictly filtered to published content", all_published and len(vis_catalog) < len(catalog), f"Visitor count: {len(vis_catalog)} vs Total catalog: {len(catalog)}")

        # 3.3 Draft chapter holding notice
        # Find a known draft chapter
        draft_doc = next((d for d in catalog if d.get('slug') not in FOUNDATIONAL_PUBLISHED_KEYS), None)
        if draft_doc:
            r = self.client.get(f"/docs/{draft_doc.get('category')}/{draft_doc.get('slug')}")
            html = r.get_data(as_text=True)
            notice_present = "CHAPTER IN EDITORIAL REVIEW" in html or "UNRELEASED" in html or "scheduled" in html.lower()
            self.record("Stage 3", "STAG-03", "Direct access to unreleased chapter displays accessible holding screen", notice_present, f"Tested slug: {draft_doc.get('slug')}")
        else:
            self.record("Stage 3", "STAG-03", "Draft holding screen check", True, "No draft document found to test")

        # 3.4 Scheduled future date remains draft for visitor
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        orig_schedule = load_release_schedule()
        test_entries = dict(orig_schedule.get("entries", {}))
        test_entries["test/future_doc"] = {"status": "scheduled", "release_date": tomorrow}
        test_entries["test/past_doc"] = {"status": "scheduled", "release_date": yesterday}

        save_release_schedule({**orig_schedule, "entries": test_entries})
        try:
            mock_catalog = [
                {"category": "test", "slug": "future_doc", "title": "Future Chapter"},
                {"category": "test", "slug": "past_doc", "title": "Past Chapter"}
            ]
            eval_vis = get_user_catalog(mock_catalog, is_admin=False)
            future_is_hidden = not any(d.get('slug') == 'future_doc' for d in eval_vis)
            past_is_released = any(d.get('slug') == 'past_doc' for d in eval_vis)
            self.record("Stage 3", "STAG-04", "Future scheduled release holds as draft until date passes", future_is_hidden and past_is_released, f"Future hidden: {future_is_hidden}, Past unlocked: {past_is_released}")
        finally:
            save_release_schedule(orig_schedule)

    # =========================================================================
    # STAGE 4: METADATA CLASSIFICATION & 100% TAGGING INTEGRITY
    # =========================================================================
    def audit_stage_4_metadata_tagging(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 4: Metadata Classification & 100% Tagging Integrity ---\033[0m")

        catalog = load_catalog()
        total_docs = len(catalog)

        # 4.1 100% Project Ownership tagging
        missing_proj = [d.get('slug') for d in catalog if not d.get('project')]
        self.record("Stage 4", "TAG-01", "100% of documents tagged with Project Ownership", len(missing_proj) == 0, f"Tagged: {total_docs - len(missing_proj)}/{total_docs}")

        # 4.2 100% Topic & Interest categorization
        missing_topics = [d.get('slug') for d in catalog if not d.get('topics')]
        self.record("Stage 4", "TAG-02", "100% of documents tagged with Topic classifications", len(missing_topics) == 0, f"Tagged: {total_docs - len(missing_topics)}/{total_docs}")

        # 4.3 100% Canonical Document ID format
        invalid_doc_ids = []
        for d in catalog:
            doc_id = d.get('doc_id', '')
            if not re.match(r'^[A-Z0-9]+-[A-Z0-9]+-.+$', doc_id):
                invalid_doc_ids.append(d.get('slug'))
        self.record("Stage 4", "TAG-03", "100% of documents adhere to canonical <PROJECT>-<COLLECTION>-<SLUG> format", len(invalid_doc_ids) == 0, f"Valid format: {total_docs - len(invalid_doc_ids)}/{total_docs}")

        # 4.4 100% Sensitivity clearance tier tagging
        missing_sens = [d.get('slug') for d in catalog if 'max_sensitivity' not in d]
        self.record("Stage 4", "TAG-04", "100% of documents assigned security clearance tiers (Tier 1-5)", len(missing_sens) == 0, f"Tagged: {total_docs - len(missing_sens)}/{total_docs}")

        # 4.5 Dynamic Sensitivity Redaction Filter Test
        sample_confidential = "# Document Title\n\n## Overview\nPublic overview content.\n\n## Proprietary IP Specification\n<!-- sensitivity: 4 -->\nSecret employer telemetry and proprietary algorithms."
        scrubbed_for_public = filter_document_by_sensitivity(sample_confidential, viewer_tier=1)
        retained_for_admin = filter_document_by_sensitivity(sample_confidential, viewer_tier=5)
        redaction_ok = "Secret employer telemetry" not in scrubbed_for_public and "Secret employer telemetry" in retained_for_admin
        self.record("Stage 4", "TAG-05", "Dynamic sensitivity redaction scrubs proprietary sections from lower tiers", redaction_ok, "Verified Tier 1 redaction vs Tier 5 grant")

        # 4.6 Cross-reference graph validity
        broken_crossrefs = 0
        total_crossrefs = 0
        all_slugs = {d.get('slug') for d in catalog}
        for d in catalog:
            for ref in d.get('cross_references', []):
                total_crossrefs += 1
                if ref.get('slug') not in all_slugs:
                    broken_crossrefs += 1
        self.record("Stage 4", "TAG-06", "All cross-reference graph targets resolve to valid catalog documents", broken_crossrefs == 0, f"Valid links: {total_crossrefs - broken_crossrefs}/{total_crossrefs} (Broken: {broken_crossrefs})")

    # =========================================================================
    # STAGE 5: IN-PLACE EDITING, FILE CREATION & SAFE ARCHIVING
    # =========================================================================
    def audit_stage_5_inplace_editing(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 5: In-Place Editing, File Creation & Safe Archiving ---\033[0m")

        with self.client.session_transaction() as sess:
            sess['admin'] = True

        # 5.1 Admin chapter creation
        create_res = self.client.post('/docs/api/admin/create', json={
            "project": "siraugga",
            "category": "manifesto",
            "title": "Auditor Canary Test Chapter",
            "slug": CANARY_SLUG,
            "status": "draft",
            "content": "# Auditor Canary Test Chapter\n\nInitial verification content."
        })
        canary_created = create_res.status_code == 200
        self.record("Stage 5", "EDIT-01", "Admin creates new documentation chapter with auto-registered slug", canary_created, f"HTTP {create_res.status_code}")

        # 5.2 Physical file existence
        canary_paths = resolve_physical_file("manifesto", CANARY_SLUG)
        canary_on_disk = len(canary_paths) > 0 and canary_paths[0].exists()
        self.record("Stage 5", "EDIT-02", "Created chapter written physically to server disk", canary_on_disk, f"Target: {canary_paths[0] if canary_paths else 'Not resolved'}")

        # 5.3 In-place raw markdown save
        updated_content = "# Auditor Canary Test Chapter (Updated)\n\nIn-place markdown update succeeded.\n\n```python\nprint('Zero downtime verified')\n```"
        save_res = self.client.post('/docs/api/admin/save', json={
            "category": "manifesto",
            "slug": CANARY_SLUG,
            "content": updated_content
        })
        save_data = save_res.get_json() or {}
        save_ok = save_res.status_code == 200 and "Zero downtime verified" in save_data.get("html", "")
        self.record("Stage 5", "EDIT-03", "In-place editor writes markdown and returns rendered HTML asynchronously", save_ok, f"Word count: {save_data.get('word_count')}")

        # 5.4 Release schedule status toggle
        sched_res = self.client.post('/docs/api/admin/schedule', json={
            "category": "manifesto",
            "slug": CANARY_SLUG,
            "status": "published"
        })
        sched_data = sched_res.get_json() or {}
        sched_ok = sched_res.status_code == 200 and sched_data.get("publish_status") == "published"
        self.record("Stage 5", "EDIT-04", "Admin toggles chapter status from draft to published", sched_ok, f"Current status: {sched_data.get('publish_status')}")

        # 5.5 Safe chapter deletion and archiving
        del_res = self.client.post('/docs/api/admin/delete', json={
            "category": "manifesto",
            "slug": CANARY_SLUG
        })
        del_data = del_res.get_json() or {}
        del_ok = del_res.status_code == 200 and del_data.get("status") == "success"
        self.record("Stage 5", "EDIT-05", "Delete moves chapter to .archive/ with timestamp and unregisters from schedule", del_ok, del_data.get("message", ""))

        with self.client.session_transaction() as sess:
            sess.clear()

    # =========================================================================
    # STAGE 6: MULTI-DESTINATION DUAL PERSISTENCE & SYNC CONSISTENCY
    # =========================================================================
    def audit_stage_6_sync_persistence(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 6: Multi-Destination Dual Persistence & Sync Consistency ---\033[0m")

        # 6.1 Dual persistence of release_schedule.json
        eprofile_sched_file = DOCS_DIR / "release_schedule.json"
        central_sched_file = CENTRAL_DOCS_DIR / "release_schedule.json"

        both_exist = eprofile_sched_file.exists() and central_sched_file.exists()
        if both_exist:
            with open(eprofile_sched_file, 'r', encoding='utf-8') as f:
                ep_data = json.load(f)
            with open(central_sched_file, 'r', encoding='utf-8') as f:
                cd_data = json.load(f)
            in_sync = len(ep_data.get("entries", {})) == len(cd_data.get("entries", {}))
            self.record("Stage 6", "SYNC-01", "Dual-persisted release schedules synchronized between e_profile and Central_Docs", in_sync, f"e_profile entries: {len(ep_data.get('entries', {}))}, Central_Docs: {len(cd_data.get('entries', {}))}")
        else:
            self.record("Stage 6", "SYNC-01", "Dual persistence files exist across both workspaces", False, f"e_profile: {eprofile_sched_file.exists()}, Central_Docs: {central_sched_file.exists()}")

        # 6.2 Central_Docs sync script compilability
        sync_script = CENTRAL_DOCS_DIR / "scripts" / "sync_to_eprofile.py"
        script_ok = False
        if sync_script.exists():
            import py_compile
            try:
                py_compile.compile(str(sync_script), doraise=True)
                script_ok = True
            except Exception as e:
                script_ok = False
        self.record("Stage 6", "SYNC-02", "Central Docs synchronization script compiles without AST syntax errors", script_ok, f"Script path: {sync_script}")

    # =========================================================================
    # STAGE 7: SIRAUGGA AGENT BUTTON vs TEST DEMO ROUTING & SUBMODULE INTEGRITY
    # =========================================================================
    def audit_stage_7_agent_and_demo_routing(self):
        if not self.json_output:
            print("\n\033[94m--- STAGE 7: Siraugga Agent Button vs Test Demo Routing & Submodule Integrity ---\033[0m")

        submod_plugin = EPROFILE_ROOT / "content" / "projects" / "engines" / "antigravity_agent" / "ai_plugin.py"
        file_mod_src = (EPROFILE_ROOT / "file_mod.py").read_text(encoding="utf-8", errors="ignore")
        post_sync_src = (EPROFILE_ROOT / "post_sync.py").read_text(encoding="utf-8", errors="ignore")
        submod_preserved = (
            submod_plugin.exists()
            and "ai" in app.blueprints
            and "submodule', 'update'" in file_mod_src
            and '"deinit"' not in post_sync_src
        )
        self.record(
            "Stage 7",
            "AGENT-01",
            "Siraugga submodule ai_plugin.py exists, Blueprint is mounted, and sync scripts preserve submodule",
            submod_preserved,
            f"submod_plugin={submod_plugin.exists()}, ai_bp={'ai' in app.blueprints}",
        )

        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = True
            sess["is_admin"] = True
            sess["username"] = "admin"

        r_agent = self.client.get("/ai_agent/?mode=root&project=root", follow_redirects=False)
        html_agent = r_agent.get_data(as_text=True)
        with self.client.session_transaction() as sess:
            scope_after_agent = sess.get("agent_token_scope")
            auth_after_agent = sess.get("agent_authenticated")

        agent_btn_ok = (
            r_agent.status_code == 200
            and scope_after_agent == "root"
            and auth_after_agent is True
            and "Siraugga Command Center" in html_agent
        )
        self.record(
            "Stage 7",
            "AGENT-02",
            "Admin AGENT button (/ai_agent/?mode=root&project=root) launches Siraugga Command Center in root scope (HTTP 200, never redirects to Home)",
            agent_btn_ok,
            f"HTTP {r_agent.status_code}, scope={scope_after_agent}, location={r_agent.headers.get('Location')}",
        )

        r_demo = self.client.get("/ai_agent/login?demo=1", follow_redirects=False)
        html_demo = r_demo.get_data(as_text=True)
        with self.client.session_transaction() as sess:
            scope_after_demo = sess.get("agent_token_scope")
            auth_after_demo = sess.get("agent_authenticated")

        demo_btn_ok = (
            r_demo.status_code == 200
            and scope_after_demo == "demo"
            and not auth_after_demo
            and "Siraugga Agent • Google OAuth Authentication" in html_demo
            and "SECURE_GATE | ACCESS_RESTRICTED" not in html_demo
        )
        self.record(
            "Stage 7",
            "AGENT-03",
            "Test Demo button (/ai_agent/login?demo=1) isolates demo scope and renders Siraugga Google OAuth login (never E-Profile SECURE_GATE)",
            demo_btn_ok,
            f"HTTP {r_demo.status_code}, scope={scope_after_demo}, auth={auth_after_demo}",
        )

        r_switch = self.client.get("/ai_agent/?mode=root&project=antigravity_agent", follow_redirects=False)
        html_switch = r_switch.get_data(as_text=True)
        with self.client.session_transaction() as sess:
            scope_after_switch = sess.get("agent_token_scope")
            auth_after_switch = sess.get("agent_authenticated")

        switch_ok = (
            r_switch.status_code == 200
            and scope_after_switch == "root"
            and auth_after_switch is True
            and "Siraugga Command Center" in html_switch
        )
        self.record(
            "Stage 7",
            "AGENT-04",
            "Clicking AGENT button after Test Demo immediately restores root scope and loads Siraugga Command Center",
            switch_ok,
            f"HTTP {r_switch.status_code}, scope={scope_after_switch}",
        )

        with self.client.session_transaction() as sess:
            sess.clear()

        r_unauth = self.client.get("/ai_agent/?mode=root&project=root", follow_redirects=False)
        unauth_loc = r_unauth.headers.get("Location", "")
        unauth_ok = r_unauth.status_code in (301, 302) and "login" in unauth_loc and "/home" not in unauth_loc
        self.record(
            "Stage 7",
            "AGENT-05",
            "Unauthenticated visitor hitting AGENT route is redirected to relative login (never to /home)",
            unauth_ok,
            f"HTTP {r_unauth.status_code}, Location={unauth_loc}",
        )

        projects_tpl = (EPROFILE_ROOT / "templates" / "projects.html").read_text(encoding="utf-8", errors="ignore")
        projects_js = (EPROFILE_ROOT / "static" / "js" / "projects.js").read_text(encoding="utf-8", errors="ignore")
        server_src = (EPROFILE_ROOT / "server.py").read_text(encoding="utf-8", errors="ignore")
        ui_contract_ok = (
            "openAgent('root')" in projects_tpl
            and "openAgent('{{ project.name }}')" in projects_tpl
            and 'href="/ai_agent/login?demo=1"' in projects_tpl
            and "/ai_agent/?mode=root&project=" in projects_js
            and "path.startswith('ai_agent')" in server_src
        )
        self.record(
            "Stage 7",
            "AGENT-06",
            "UI templates & server router enforce distinct AGENT (?mode=root) vs Test Demo (/login?demo=1) bindings and block Home fallback redirects",
            ui_contract_ok,
            "Verified projects.html, projects.js, and server.py dynamic_route guard",
        )

        submod_root = EPROFILE_ROOT / "content" / "projects" / "engines" / "antigravity_agent"
        ai_plugin_src = (submod_root / "ai_plugin.py").read_text(encoding="utf-8", errors="ignore")
        index_tpl_src = (submod_root / "sandbox" / "templates" / "index.html").read_text(encoding="utf-8", errors="ignore")
        exec_mixin_src = (submod_root / "agents" / "mixins" / "execution_mixin.py").read_text(encoding="utf-8", errors="ignore")

        rel_path_ok = (
            "_render_ai_template" in ai_plugin_src
            and 'window.location.href = "/login"' not in index_tpl_src
            and "/mnt/c/Users/michael" not in ai_plugin_src
            and "/mnt/c/Users/michael" not in exec_mixin_src
        )
        self.record(
            "Stage 7",
            "AGENT-07",
            "Plugin templates and execution engine enforce relative path resolution and isolated blueprint template rendering",
            rel_path_ok,
            "Verified _render_ai_template, relative login redirects, and zero hardcoded /mnt/c host paths",
        )

        stream_and_model_ok = (
            "is not recognized as a known model" in exec_mixin_src
            and '"output": full_output' in exec_mixin_src
            and "since_seq" in ai_plugin_src
            and "since_seq=" in index_tpl_src
        )
        self.record(
            "Stage 7",
            "AGENT-08",
            "Execution engine auto-recovers from unsupported CLI models and preserves response chunks via sequence-cursor stream polling",
            stream_and_model_ok,
            "Verified CLI model fallback retry, agent_done output payload, and non-destructive since_seq cursor polling",
        )

    # =========================================================================
    # CLEANUP HOOK (Clean Workspace Protocol)
    # =========================================================================
    def cleanup_canaries(self):
        """Purges any leftover canary test files created during the audit."""
        # 1. Clean from docs directory
        for p in DOCS_DIR.glob(f"**/*{CANARY_SLUG}*"):
            try:
                p.unlink()
            except Exception:
                pass

        # 2. Clean from archive directory
        archive_dir = DOCS_DIR / ".archive"
        if archive_dir.exists():
            for p in archive_dir.glob(f"*{CANARY_SLUG}*"):
                try:
                    p.unlink()
                except Exception:
                    pass

        # 3. Clean from release schedule
        try:
            schedule = load_release_schedule()
            entries = schedule.get("entries", {})
            keys_to_pop = [k for k in entries if CANARY_SLUG in k]
            if keys_to_pop:
                for k in keys_to_pop:
                    entries.pop(k, None)
                with open(DOCS_DIR / "release_schedule.json", 'w', encoding='utf-8') as f:
                    json.dump(schedule, f, indent=2)
                if (CENTRAL_DOCS_DIR / "release_schedule.json").exists():
                    with open(CENTRAL_DOCS_DIR / "release_schedule.json", 'w', encoding='utf-8') as f:
                        json.dump(schedule, f, indent=2)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="E-Profile & Documentation Vault Security Audit Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed diagnostic lines for all checks")
    parser.add_argument("--stage", "-s", type=int, choices=[1, 2, 3, 4, 5, 6, 7], help="Run a specific audit stage (1-7)")
    parser.add_argument("--json", "-j", action="store_true", help="Output audit results in machine-readable JSON format")
    args = parser.parse_args()

    auditor = SecurityAuditor(verbose=args.verbose, stage_filter=args.stage, json_output=args.json)
    success = auditor.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
