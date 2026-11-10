"""Tests for pa_usage_sync merge rules (fake remote, temp files, no network)."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pa_usage_sync as s


def ev(ts, pkg="installer", h="aa"):
    return {"timestamp": ts, "package_id": pkg, "client_hash": h}


class MergeTests(unittest.TestCase):
    def test_licenses_keep_newest(self):
        local = {"a": {"last_seen": 10, "v": "old"}, "b": {"last_seen": 50}}
        remote = {"a": {"last_seen": 20, "v": "new"}, "b": {"last_seen": 40}, "c": {"last_seen": 1}}
        merged, n = s.merge_licenses(local, remote)
        self.assertEqual(merged["a"]["v"], "new")
        self.assertEqual(merged["b"]["last_seen"], 50)
        self.assertIn("c", merged)
        self.assertEqual(n, 2)

    def test_trial_never_restarts_and_admin_fields_stay_local(self):
        local = {"h": {"first_run": 100, "last_seen": 200, "remote_revoked": True, "duration_days": 30}}
        remote = {"h": {"first_run": 500, "last_seen": 900, "remote_revoked": False, "duration_days": 14, "app_version": "1.0.1"}}
        merged, n = s.merge_licenses(local, remote)
        self.assertEqual(n, 1)
        self.assertEqual(merged["h"]["first_run"], 100)       # earliest wins
        self.assertEqual(merged["h"]["last_seen"], 900)       # newest usage
        self.assertEqual(merged["h"]["app_version"], "1.0.1")
        self.assertTrue(merged["h"]["remote_revoked"])        # PC's revoke kept
        self.assertEqual(merged["h"]["duration_days"], 30)    # PC's extension kept

    def test_feedback_union(self):
        merged, n = s.merge_feedback([{"id": "1", "timestamp": 5}], [{"id": "1", "timestamp": 5}, {"id": "2", "timestamp": 9}])
        self.assertEqual([f["id"] for f in merged], ["2", "1"])
        self.assertEqual(n, 1)

    def test_downloads_counted_once(self):
        local = {"total_downloads": 3, "packages": {"installer": 3}, "events": [ev(1), ev(2), ev(3)]}
        seen = set()
        data, n = s.merge_downloads(local, {"events": [ev(3), ev(4, "portable")]}, seen)
        self.assertEqual(n, 1)
        self.assertEqual(data["total_downloads"], 4)
        self.assertEqual(data["packages"]["portable"], 1)
        data, n = s.merge_downloads(data, {"events": [ev(3), ev(4, "portable")]}, seen)
        self.assertEqual(n, 0)
        self.assertEqual(data["total_downloads"], 4)


class SyncOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(s, name, self.tmp / f"{name}.json")
                        for name in ("LICENSES", "FEEDBACK", "DOWNLOADS", "STATE")]
        for p in self.patches:
            p.start()
        s._write(s.DOWNLOADS, {"total_downloads": 1, "packages": {"installer": 1}, "events": [ev(1)]})
        self.remote = {
            "content/audio_suite_licenses.json": {"x": {"last_seen": 5}},
            "content/audio_suite_feedback.json": [{"id": "f", "timestamp": 1}],
            "content/audio_suite_downloads.json": {"events": [ev(1), ev(2)]},
        }

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_counts_only_events_missing_locally_and_only_once(self):
        r = s.sync_once(fetch=self.remote.get)  # local has ev(1); PA also has ev(2)
        self.assertEqual(r, {"installs_updated": 1, "feedback_added": 1, "downloads_added": 1})
        self.assertEqual(s._read(s.DOWNLOADS, {})["total_downloads"], 2)
        r = s.sync_once(fetch=self.remote.get)  # nothing new
        self.assertEqual(r, {"installs_updated": 0, "feedback_added": 0, "downloads_added": 0})
        self.remote["content/audio_suite_downloads.json"] = {"events": [ev(1), ev(2), ev(3, "portable")]}
        r = s.sync_once(fetch=self.remote.get)
        self.assertEqual(r["downloads_added"], 1)
        data = s._read(s.DOWNLOADS, {})
        self.assertEqual(data["total_downloads"], 3)
        self.assertEqual(data["packages"]["portable"], 1)


class CloudSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(s, name, self.tmp / f"{name}.json")
                        for name in ("LICENSES", "FEEDBACK", "STATE", "RELEASES", "DOWNLOADS")]
        self.patches.append(mock.patch.object(s, "CALIBRATION_CSV", self.tmp / "cal.csv"))
        for p in self.patches:
            p.start()
        s._write(s.LICENSES, {"old": {"hwid": "old", "first_run": 1, "last_seen": 2, "remote_revoked": True}})
        s._write(s.RELEASES, {"version": "1.0.1"})
        self.calls = []
        self.export = {
            "licenses": [{"hwid": "new", "first_run": 10, "last_seen": 20, "duration_days": 14, "remote_revoked": 0},
                         {"hwid": "old", "first_run": 1, "last_seen": 50, "duration_days": 14, "remote_revoked": 0}],
            "feedback": [{"id": "f1", "timestamp": 30, "message": "hi"}],
            "calibration": [{"id": 1, "created_at": 1794300000, "user": "u", "x": "1", "z": "2", "key": "w", "dir": "n", "comment": ""},
                            {"id": 2, "created_at": 1794300001, "user": "u", "x": "3", "z": "4", "key": "s", "dir": "s", "comment": "c"}],
            "downloads": [{"id": 7, "created_at": 1794300002, "package_id": "installer", "client_hash": "ab", "user_agent": "x"}],
        }
        s._write(s.DOWNLOADS, {"total_downloads": 5, "packages": {"installer": 5}, "events": []})

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def api(self, method, path, body):
        self.calls.append((method, path, body))
        if method == "GET":
            return self.export
        if path == "/admin/licenses/merge":
            return {"merged": len(body["records"])}
        return {"success": True}

    def test_pull_append_push_and_resume(self):
        r = s.cloud_sync_once(api=self.api)
        self.assertEqual(r["calibration_added"], 2)
        self.assertEqual(r["feedback_added"], 1)
        self.assertEqual(r["installs_pushed"], 2)
        self.assertEqual(r["release_pushed"], "1.0.1")
        lic = s._read(s.LICENSES, {})
        self.assertTrue(lic["old"]["remote_revoked"])   # local revoke not overwritten
        self.assertEqual(lic["old"]["last_seen"], 50)
        csv_lines = (self.tmp / "cal.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(csv_lines[0], "Time,User,X,Z,Key,Dir,Comment")
        self.assertEqual(len(csv_lines), 3)
        pushed = next(b for m, p, b in self.calls if p == "/admin/licenses/merge")
        self.assertTrue(next(x for x in pushed["records"] if x["hwid"] == "old")["remote_revoked"])
        dl = s._read(s.DOWNLOADS, {})
        self.assertEqual((dl["total_downloads"], dl["packages"]["installer"], len(dl["events"])), (6, 6, 1))
        # Second pass asks only for newer rows.
        self.export["calibration"], self.export["feedback"], self.export["downloads"] = [], [], []
        s.cloud_sync_once(api=self.api)
        self.assertIn("calibration_after=2", self.calls[-3][1])
        self.assertIn("feedback_since=30", self.calls[-3][1])
        self.assertIn("downloads_after=7", self.calls[-3][1])
        self.assertEqual(s._read(s.DOWNLOADS, {})["total_downloads"], 6)
        self.assertEqual(len((self.tmp / "cal.csv").read_text(encoding="utf-8").splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
