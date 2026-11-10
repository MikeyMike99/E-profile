"""Keep this (local) e-profile's JOSHY and calibrator data in step with the cloud.

Runs inside the local e-profile server (started by DevCore's scripts/eprofile_server.sh
with EPROFILE_PA_USAGE_SYNC=on), every SYNC_HOURS:

1. PythonAnywhere (read-only, via the bootstrap endpoint): JOSHY 1.0.0 still reports
   to mikeymike.pythonanywhere.com.
2. Cloudflare D1 via api.mikeytech.dev/admin/export (JOSHY 1.0.1+ and the Echos Lab
   calibrator, both running 24/7 on Cloudflare).
3. Push back to D1: every install record (so a 1.0.0 user who upgrades keeps their
   trial dates), the PC's admin fields, and the JOSHY release info.

  content/audio_suite_licenses.json  per install (hardware id): usage fields from the
                                     newest report; admin fields (remote_revoked,
                                     duration_days) belong to this PC once it knows
                                     the install, so revoke/extend here.
  content/audio_suite_feedback.json  union by id, newest first
  content/audio_suite_downloads.json PythonAnywhere download events added once
  calibration_data.csv               new calibrator rows from D1 appended

State: cache/pa_usage_sync_state.json.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from config import Config

log = logging.getLogger("eprofile.pa_usage_sync")

PA_URL = (os.environ.get("PYTHONANYWHERE_URL") or "https://mikeymike.pythonanywhere.com").rstrip("/")
SYNC_HOURS = float(os.environ.get("EPROFILE_PA_USAGE_SYNC_HOURS", "3"))
CONTENT = Config.CONTENT_DIR
LICENSES = CONTENT / "audio_suite_licenses.json"
FEEDBACK = CONTENT / "audio_suite_feedback.json"
DOWNLOADS = CONTENT / "audio_suite_downloads.json"
STATE = Config.ROOT_DIR / "cache" / "pa_usage_sync_state.json"
MAX_EVENTS = 500
_lock = threading.Lock()


def _token() -> str:
    return os.environ.get("SYNC_SECRET") or os.environ.get("ADMIN_KEY") or ""


def fetch_remote(rel_path: str):
    """Read one JSON file from PythonAnywhere via the bootstrap endpoint (read-only 'cat')."""
    body = json.dumps({"action": "cat", "path": rel_path}).encode("utf-8")
    req = urllib.request.Request(
        f"{PA_URL}/__breakglass__?format=json", data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": f"Bearer {_token()}", "User-Agent": "eprofile-usage-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8", errors="replace"))
    if res.get("status") == "error":
        raise RuntimeError(res.get("message") or "remote error")
    return json.loads(res.get("content") or "null")


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


ADMIN_FIELDS = ("remote_revoked", "duration_days")


def merge_licenses(local: dict, remote: dict) -> tuple[dict, int]:
    """Usage fields from whichever side saw the install last; the earliest first_run
    always wins (a trial can never restart); admin fields stay as this PC has them."""
    merged, changed = dict(local or {}), 0
    for hwid, rec in (remote or {}).items():
        if not isinstance(rec, dict):
            continue
        mine = merged.get(hwid)
        if not isinstance(mine, dict):
            merged[hwid] = dict(rec)
            changed += 1
            continue
        new = dict(rec) if int(rec.get("last_seen") or 0) > int(mine.get("last_seen") or 0) else dict(mine)
        firsts = [int(x) for x in (mine.get("first_run"), rec.get("first_run")) if x]
        if firsts:
            new["first_run"] = min(firsts)
        for f in ADMIN_FIELDS:
            if f in mine:
                new[f] = mine[f]
        if new != mine:
            merged[hwid] = new
            changed += 1
    return merged, changed


def merge_feedback(local: list, remote: list) -> tuple[list, int]:
    by_id = {f.get("id"): f for f in (local or []) if isinstance(f, dict)}
    added = 0
    for f in remote or []:
        if isinstance(f, dict) and f.get("id") not in by_id:
            by_id[f.get("id")] = f
            added += 1
    merged = sorted(by_id.values(), key=lambda f: int(f.get("timestamp") or 0), reverse=True)
    return merged, added


def _event_key(e: dict) -> str:
    return f"{e.get('timestamp')}|{e.get('package_id')}|{e.get('client_hash')}"


def merge_downloads(local: dict, remote: dict, seen: set) -> tuple[dict, int]:
    """Add PythonAnywhere download events not imported before; bump totals for each."""
    data = local if isinstance(local, dict) else {}
    data.setdefault("total_downloads", 0)
    pkgs = data.setdefault("packages", {})
    events = data.setdefault("events", [])
    local_keys = {_event_key(e) for e in events}
    added = 0
    for e in (remote or {}).get("events", []) if isinstance(remote, dict) else []:
        key = _event_key(e)
        if key in seen or key in local_keys:
            seen.add(key)
            continue
        seen.add(key)
        events.append(dict(e, source="pythonanywhere"))
        data["total_downloads"] += 1
        pid = e.get("package_id") or "unknown"
        pkgs[pid] = pkgs.get(pid, 0) + 1
        added += 1
    events.sort(key=lambda e: int(e.get("timestamp") or 0), reverse=True)
    del events[MAX_EVENTS:]
    return data, added


def sync_once(fetch=fetch_remote) -> dict:
    """One sync pass. `fetch(rel_path)` is injectable for tests."""
    with _lock:
        state = _read(STATE, {})
        result = {}
        remote_lic = fetch("content/audio_suite_licenses.json")
        lic, n = merge_licenses(_read(LICENSES, {}), remote_lic)
        if n:
            _write(LICENSES, lic)
        result["installs_updated"] = n

        remote_fb = fetch("content/audio_suite_feedback.json")
        fb, n = merge_feedback(_read(FEEDBACK, []), remote_fb)
        if n:
            _write(FEEDBACK, fb)
        result["feedback_added"] = n

        # Events the local log already has (it started as a copy of PythonAnywhere's) are
        # skipped by merge_downloads; only events new on PythonAnywhere are counted.
        seen = set(state.get("imported_download_events", []))
        remote_dl = fetch("content/audio_suite_downloads.json")
        dl, n = merge_downloads(_read(DOWNLOADS, {}), remote_dl, seen)
        if n:
            _write(DOWNLOADS, dl)
        result["downloads_added"] = n

        state["imported_download_events"] = sorted(seen)[-2000:]
        state["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        state["last_result"] = result
        _write(STATE, state)
        return result


# --- Cloudflare D1 (api.mikeytech.dev) ----------------------------------------------

CLOUD_URL = (os.environ.get("JOSHY_API_URL") or "https://api.mikeytech.dev").rstrip("/")
RELEASES = CONTENT / "audio_suite_releases.json"
CALIBRATION_CSV = Config.ROOT_DIR / "calibration_data.csv"
CSV_HEADER = ["Time", "User", "X", "Z", "Key", "Dir", "Comment"]


def _cloud_secret() -> str:
    return os.environ.get("JOSHY_API_ADMIN_SECRET", "")


def cloud_request(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{CLOUD_URL}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {_cloud_secret()}", "Content-Type": "application/json",
        "Accept": "application/json", "User-Agent": "eprofile-cloud-sync/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def append_calibration(rows: list) -> int:
    """Append D1 calibrator rows to calibration_data.csv in the original column layout."""
    import csv
    if not rows:
        return 0
    new_file = not CALIBRATION_CSV.is_file()
    with open(CALIBRATION_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(CSV_HEADER)
        for r in rows:
            when = time.ctime(int(r.get("created_at") or 0)) if r.get("created_at") else r.get("time_text", "")
            w.writerow([when, r.get("user", ""), r.get("x", ""), r.get("z", ""),
                        r.get("key", ""), r.get("dir", ""), r.get("comment", "")])
    return len(rows)


def cloud_sync_once(api=cloud_request) -> dict:
    """Pull new JOSHY/calibrator data from D1, then push installs + release info back."""
    with _lock:
        state = _read(STATE, {})
        cloud = state.setdefault("cloud", {})
        result = {}
        q = f"/admin/export?feedback_since={int(cloud.get('feedback_since', 0))}" \
            f"&calibration_after={int(cloud.get('calibration_after', 0))}" \
            f"&downloads_after={int(cloud.get('downloads_after', 0))}"
        data = api("GET", q, None)

        dl_rows = data.get("downloads", [])
        if dl_rows:
            dl = _read(DOWNLOADS, {})
            dl.setdefault("total_downloads", 0)
            pkgs = dl.setdefault("packages", {})
            events = dl.setdefault("events", [])
            version = (_read(RELEASES, {}) or {}).get("version", "")
            for r in dl_rows:
                ts = int(r.get("created_at") or 0)
                pid = r.get("package_id") or "unknown"
                events.append({"timestamp": ts, "formatted_time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                               "package_id": pid, "filename": pid, "version": version,
                               "client_hash": r.get("client_hash", ""), "user_agent": r.get("user_agent", ""),
                               "source": "cloudflare"})
                dl["total_downloads"] += 1
                pkgs[pid] = pkgs.get(pid, 0) + 1
            events.sort(key=lambda e: int(e.get("timestamp") or 0), reverse=True)
            del events[MAX_EVENTS:]
            _write(DOWNLOADS, dl)
            cloud["downloads_after"] = max(int(r.get("id") or 0) for r in dl_rows)
        result["downloads_added"] = len(dl_rows)

        remote_lic = {r["hwid"]: {
            "hwid": r["hwid"], "first_run": r.get("first_run"), "last_seen": r.get("last_seen"),
            "duration_days": r.get("duration_days", 14), "app_version": r.get("app_version"),
            "remote_revoked": bool(r.get("remote_revoked")), "status": r.get("status")}
            for r in data.get("licenses", []) if r.get("hwid")}
        lic, n = merge_licenses(_read(LICENSES, {}), remote_lic)
        if n:
            _write(LICENSES, lic)
        result["installs_updated"] = n

        fb_rows = data.get("feedback", [])
        fb, n = merge_feedback(_read(FEEDBACK, []), fb_rows)
        if n:
            _write(FEEDBACK, fb)
        result["feedback_added"] = n
        if fb_rows:
            cloud["feedback_since"] = max(int(f.get("timestamp") or 0) for f in fb_rows)

        cal = data.get("calibration", [])
        result["calibration_added"] = append_calibration(cal)
        if cal:
            cloud["calibration_after"] = max(int(r.get("id") or 0) for r in cal)

        # Push: every install (D1 keeps the earliest first_run / latest last_seen) and
        # this PC's admin fields; then the release info apps are told about.
        records = list(_read(LICENSES, {}).values())
        if records:
            result["installs_pushed"] = api("POST", "/admin/licenses/merge", {"records": records}).get("merged", 0)
        rel = _read(RELEASES, None)
        if isinstance(rel, dict) and rel.get("version"):
            api("POST", "/admin/releases", rel)
            result["release_pushed"] = rel["version"]

        cloud["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        cloud["last_result"] = result
        _write(STATE, state)
        return result


def _record_error(key: str, exc: Exception) -> None:
    try:
        st = _read(STATE, {})
        st[key] = f"{datetime.now():%Y-%m-%d %H:%M} {exc}"
        _write(STATE, st)
    except Exception:
        pass


def _loop():
    time.sleep(20)
    while True:
        if _token():
            try:
                log.info("PythonAnywhere usage sync: %s", sync_once())
            except Exception as exc:
                log.warning("PythonAnywhere usage sync failed: %s", exc)
                _record_error("last_error", exc)
        if _cloud_secret():
            try:
                log.info("Cloud (D1) sync: %s", cloud_sync_once())
            except Exception as exc:
                log.warning("Cloud (D1) sync failed: %s", exc)
                _record_error("cloud_last_error", exc)
        time.sleep(max(0.25, SYNC_HOURS) * 3600)


def start() -> bool:
    if not (_token() or _cloud_secret()):
        log.warning("Usage sync not started: no SYNC_SECRET/ADMIN_KEY or JOSHY_API_ADMIN_SECRET")
        return False
    threading.Thread(target=_loop, name="usage-sync", daemon=True).start()
    return True
