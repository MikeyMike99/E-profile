"""Audio Playback Suite (JOSHY) Download Staging, Telemetry, and Fleet Review Engine."""

import hashlib
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from config import Config

config = Config()
audio_suite_bp = Blueprint("audio_suite", __name__)

RELEASES_FILE = config.CONTENT_DIR / "audio_suite_releases.json"
DOWNLOADS_FILE = config.CONTENT_DIR / "audio_suite_downloads.json"
LICENSES_FILE = config.CONTENT_DIR / "audio_suite_licenses.json"
FEEDBACK_FILE = config.CONTENT_DIR / "audio_suite_feedback.json"
DIST_DIR = Path("/mnt/c/Users/michael/Documents/Audio_pllayback_suite/dist")
STATIC_DOWNLOADS_DIR = config.STATIC_DIR / "downloads"

DEFAULT_RELEASE_DATA = {
    "version": "1.0.0",
    "release_title": "JOSHY Audio Playback Suite v1.0.0 (Accessible Edition)",
    "release_date": "2026-10-24",
    "stage_status": "PUBLISHED",
    "changelog": "High-performance accessible Windows audio playback and Spotify controller featuring dual-layer hardware trial hardening, self-healing NVDA/JAWS/SAPI client extraction, acoustic earcons, and automated cloud attestation.",
    "download_url": "https://github.com/Hein-Wagner-Academy-Cyber-Sentinel/nomvula_agri_finance",
    "packages": {
        "installer": {
            "id": "installer",
            "title": "JOSHY Windows Installer",
            "filename": "JOSHY-Setup.exe",
            "recommended": True,
            "badge": "RECOMMENDED FOR SCREEN READERS",
            "target_audience": "Blind and visually impaired users with NVDA, JAWS, or Windows Narrator. Installs desktop & start menu shortcuts and handles automatic extraction.",
            "size_bytes": 53075410,
            "size_formatted": "50.6 MB",
            "sha256": "68c828fd53640f44c02cf24ab26988ea41c532442e0d2fb2a22e71af55d5582b",
            "download_url": "/downloads/get/installer",
            "external_url": "https://github.com/Hein-Wagner-Academy-Cyber-Sentinel/nomvula_agri_finance",
            "downloads_count": 0,
        },
        "portable": {
            "id": "portable",
            "title": "JOSHY Standalone Portable Executable",
            "filename": "JOSHY.exe",
            "recommended": False,
            "badge": "PORTABLE SINGLE BINARY",
            "target_audience": "Single-binary native C machine-code executable. Runs instantly from USB or disk without administrative rights or installation.",
            "size_bytes": 148953600,
            "size_formatted": "142.1 MB",
            "sha256": "b729f11f228f1a1c3fe07b7e4d03bff6a8a97766a73636878044476349a1429b",
            "download_url": "/downloads/get/portable",
            "external_url": "https://github.com/Hein-Wagner-Academy-Cyber-Sentinel/nomvula_agri_finance",
            "downloads_count": 0,
        },
    },
}

HOTKEYS_REFERENCE = [
    {
        "action": "Play / Pause",
        "shortcut": "Space",
        "global_fallback": "Ctrl+Alt+Shift+Up",
        "description": "Toggles playback of currently selected song or Spotify stream.",
    },
    {
        "action": "Volume Up (+5%)",
        "shortcut": "] (Right Bracket)",
        "global_fallback": "Ctrl+Alt+]",
        "description": "Increases playback volume with acoustic high-pitch earcon limit cue.",
    },
    {
        "action": "Volume Down (-5%)",
        "shortcut": "[ (Left Bracket)",
        "global_fallback": "Ctrl+Alt+[",
        "description": "Decreases playback volume with acoustic low-pitch earcon limit cue.",
    },
    {
        "action": "Next Track",
        "shortcut": "Ctrl+Alt+Shift+Right",
        "global_fallback": "None",
        "description": "Skips forward to the next queued audio track in playlist.",
    },
    {
        "action": "Previous Track",
        "shortcut": "Ctrl+Alt+Shift+Left",
        "global_fallback": "None",
        "description": "Returns to previous audio track or restarts current track.",
    },
    {
        "action": "Jump to Search",
        "shortcut": "E (or Ctrl+F)",
        "global_fallback": "None",
        "description": "Focuses the search edit box and speaks current library count.",
    },
    {
        "action": "Cycle Buttons",
        "shortcut": "B (forward) / Shift+B (back)",
        "global_fallback": "None",
        "description": "Rapidly cycles keyboard focus between transport controls.",
    },
    {
        "action": "Show Song Lyrics",
        "shortcut": "Ctrl+Y (or Y)",
        "global_fallback": "None",
        "description": "Opens the synchronized accessible lyrics viewport.",
    },
    {
        "action": "Setup Wizard",
        "shortcut": "Ctrl+W",
        "global_fallback": "None",
        "description": "Launches the audio device and screen reader configuration wizard.",
    },
    {
        "action": "Help & Orientation",
        "shortcut": "F1",
        "global_fallback": "None",
        "description": "Speaks complete orientation overview and current player state.",
    },
]

SYSTEM_INVARIANTS = [
    {
        "name": "Screen Reader Synchronization",
        "spec": "NVDA 2022+, JAWS 2021+, Windows Narrator (SAPI5 native fallback)",
        "details": "Zero-dependency embedded NVDA controller client DLLs automatically extracted on first launch.",
    },
    {
        "name": "Operating System",
        "spec": "Windows 10 / Windows 11 (64-bit architecture)",
        "details": "Compiled with Nuitka into native standalone x64 C machine code binaries.",
    },
    {
        "name": "Hardware-Bound Evaluation Engine",
        "spec": "14-Day Evaluation with Quad-Store Registry & Inode Synchronization",
        "details": "Enforces monotonic clock checks, HMAC-SHA256 signatures, and cloud handshake attestation.",
    },
    {
        "name": "Spotify Controller Integration",
        "spec": "Spotify Web API with Headless Daemon Bridge",
        "details": "Supports local library playback and direct Spotify streaming with token persistence.",
    },
]


def format_file_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = min(int(math.log(size_bytes, 1024)), len(units) - 1)
    val = size_bytes / (1024 ** i)
    return f"{val:.1f} {units[i]}"


def get_releases_data() -> dict:
    if not RELEASES_FILE.exists():
        RELEASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        RELEASES_FILE.write_text(json.dumps(DEFAULT_RELEASE_DATA, indent=2), encoding="utf-8")
        return DEFAULT_RELEASE_DATA.copy()
    try:
        data = json.loads(RELEASES_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "packages" not in data:
            return DEFAULT_RELEASE_DATA.copy()
        return data
    except Exception:
        return DEFAULT_RELEASE_DATA.copy()


def save_releases_data(data: dict) -> bool:
    try:
        RELEASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        RELEASES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def get_downloads_log() -> dict:
    if not DOWNLOADS_FILE.exists():
        initial = {
            "total_downloads": 0,
            "packages": {
                "installer": 0,
                "portable": 0,
            },
            "events": [],
        }
        DOWNLOADS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DOWNLOADS_FILE.write_text(json.dumps(initial, indent=2), encoding="utf-8")
        return initial
    try:
        data = json.loads(DOWNLOADS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Malformed downloads log")
        return data
    except Exception:
        return {"total_downloads": 0, "packages": {}, "events": []}


def save_downloads_log(data: dict) -> bool:
    try:
        DOWNLOADS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DOWNLOADS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def record_download_event(package_id: str, client_ip: str, user_agent: str) -> None:
    downloads = get_downloads_log()
    releases = get_releases_data()

    downloads["total_downloads"] = downloads.get("total_downloads", 0) + 1
    pkg_counts = downloads.setdefault("packages", {})
    pkg_counts[package_id] = pkg_counts.get(package_id, 0) + 1

    pkg_meta = releases.get("packages", {}).get(package_id, {})
    if pkg_meta:
        pkg_meta["downloads_count"] = pkg_meta.get("downloads_count", 0) + 1
        save_releases_data(releases)

    now = int(time.time())
    raw_hash = f"{client_ip}-{user_agent[:40]}"
    client_hash = hashlib.sha256(raw_hash.encode("utf-8")).hexdigest()[:8]

    event = {
        "timestamp": now,
        "formatted_time": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        "package_id": package_id,
        "filename": pkg_meta.get("filename", package_id),
        "version": releases.get("version", "1.0.0"),
        "client_hash": client_hash,
        "user_agent": user_agent[:120],
    }

    events = downloads.setdefault("events", [])
    events.insert(0, event)
    if len(events) > 500:
        del events[500:]

    save_downloads_log(downloads)


def sync_dist_binaries_on_disk() -> dict:
    """Scans local compiled binaries in Audio_pllayback_suite/dist, calculates SHA-256 and sizes."""
    releases = get_releases_data()
    updated = {}

    if not DIST_DIR.exists():
        return {"success": False, "error": f"Dist directory not found at {DIST_DIR}"}

    for pkg_id, pkg in releases.get("packages", {}).items():
        filename = pkg.get("filename")
        if not filename:
            continue
        filepath = DIST_DIR / filename
        if filepath.exists() and filepath.is_file():
            hasher = hashlib.sha256()
            size = filepath.stat().st_size
            try:
                with open(filepath, "rb") as f:
                    while chunk := f.read(1048576):
                        hasher.update(chunk)
                sha256_hash = hasher.hexdigest()
                pkg["size_bytes"] = size
                pkg["size_formatted"] = format_file_size(size)
                pkg["sha256"] = sha256_hash
                pkg["last_synced"] = datetime.fromtimestamp(filepath.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                updated[pkg_id] = {
                    "filename": filename,
                    "size": pkg["size_formatted"],
                    "sha256": sha256_hash,
                }
            except Exception as exc:
                updated[pkg_id] = {"filename": filename, "error": str(exc)}

    save_releases_data(releases)
    return {"success": True, "updated": updated}


def get_licenses_summary() -> tuple:
    """Parses hardware-bound evaluation licenses and builds fleet statistics."""
    records = []
    if LICENSES_FILE.exists():
        try:
            raw = json.loads(LICENSES_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                records = list(raw.values())
        except Exception:
            records = []

    server_now = int(time.time())
    total_devices = len(records)
    active_trials = 0
    expired_trials = 0
    revoked_trials = 0

    enriched = []
    for rec in records:
        hwid = rec.get("hwid", "UNKNOWN")
        first_run = rec.get("first_run", server_now)
        last_seen = rec.get("last_seen", server_now)
        duration_days = rec.get("duration_days", 14)
        expires_at = first_run + (duration_days * 86400)
        is_revoked = rec.get("remote_revoked", False)
        app_version = rec.get("app_version", "1.0.0")

        if is_revoked:
            status = "REVOKED"
            revoked_trials += 1
            days_remaining = 0
        elif server_now >= expires_at:
            status = "EXPIRED"
            expired_trials += 1
            days_remaining = 0
        else:
            status = "ACTIVE"
            active_trials += 1
            days_remaining = max(0, int(math.ceil((expires_at - server_now) / 86400)))

        enriched.append({
            "hwid": hwid,
            "hwid_short": f"{hwid[:6]}...{hwid[-4:]}" if len(hwid) >= 12 else hwid,
            "app_version": app_version,
            "first_run_formatted": datetime.fromtimestamp(first_run).strftime("%Y-%m-%d %H:%M"),
            "last_seen_formatted": datetime.fromtimestamp(last_seen).strftime("%Y-%m-%d %H:%M"),
            "expires_at_formatted": datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M"),
            "duration_days": duration_days,
            "days_remaining": days_remaining,
            "status": status,
            "remote_revoked": is_revoked,
        })

    enriched.sort(key=lambda x: x["last_seen_formatted"], reverse=True)

    summary = {
        "total_devices": total_devices,
        "active_trials": active_trials,
        "expired_trials": expired_trials,
        "revoked_trials": revoked_trials,
    }
    return summary, enriched


def get_feedback_summary() -> list:
    """Retrieves in-app user bug reports and suggestions."""
    if not FEEDBACK_FILE.exists():
        return []
    try:
        data = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        data.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return data
    except Exception:
        return []


def render_downloads_page():
    releases = get_releases_data()
    downloads_log = get_downloads_log()

    packages_list = list(releases.get("packages", {}).values())
    for pkg in packages_list:
        pkg_id = pkg.get("id")
        pkg["downloads_count"] = downloads_log.get("packages", {}).get(pkg_id, 0)
        local_path = DIST_DIR / pkg.get("filename", "")
        pkg["local_available"] = local_path.exists()

    return render_template(
        "downloads.html",
        active_tab="downloads",
        releases=releases,
        packages=packages_list,
        system_invariants=SYSTEM_INVARIANTS,
        hotkeys=HOTKEYS_REFERENCE,
        is_admin=session.get("admin", False),
        is_employer=session.get("is_employer", False),
        permissions=session.get("permissions", []),
        dist_exists=DIST_DIR.exists(),
    )


def render_usage_page():
    releases = get_releases_data()
    downloads_log = get_downloads_log()
    summary, licenses = get_licenses_summary()
    feedback_list = get_feedback_summary()

    total_downloads = downloads_log.get("total_downloads", 0)
    package_breakdown = []
    for pkg_id, pkg in releases.get("packages", {}).items():
        count = downloads_log.get("packages", {}).get(pkg_id, 0)
        percentage = int(round((count / total_downloads) * 100)) if total_downloads > 0 else 0
        package_breakdown.append({
            "id": pkg_id,
            "title": pkg.get("title", pkg_id),
            "filename": pkg.get("filename", ""),
            "count": count,
            "percentage": percentage,
            "size": pkg.get("size_formatted", ""),
        })

    recent_events = downloads_log.get("events", [])[:25]

    return render_template(
        "telemetry.html",
        active_tab="usage",
        total_downloads=total_downloads,
        package_breakdown=package_breakdown,
        recent_downloads=recent_events,
        summary=summary,
        licenses=licenses,
        feedback_list=feedback_list,
        total_feedback=len(feedback_list),
        releases=releases,
        is_admin=session.get("admin", False),
        is_employer=session.get("is_employer", False),
        permissions=session.get("permissions", []),
    )


# --- BLUEPRINT ROUTES ---

@audio_suite_bp.route("/downloads")
def downloads_view():
    return render_downloads_page()


@audio_suite_bp.route("/usage")
@audio_suite_bp.route("/telemetry")
def usage_view():
    return render_usage_page()


@audio_suite_bp.route("/downloads/get/<package_id>")
def download_package(package_id):
    releases = get_releases_data()
    packages = releases.get("packages", {})

    if package_id not in packages:
        flash(f"Package identifier '{package_id}' not found.", "error")
        return redirect(url_for("audio_suite.downloads_view"))

    pkg = packages[package_id]
    filename = pkg.get("filename", f"{package_id}.exe")

    record_download_event(
        package_id=package_id,
        client_ip=request.remote_addr or "127.0.0.1",
        user_agent=request.user_agent.string if request.user_agent else "Unknown",
    )

    local_path = DIST_DIR / filename
    if local_path.exists() and local_path.is_file():
        return send_file(
            local_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/octet-stream",
        )

    static_path = STATIC_DOWNLOADS_DIR / filename
    if static_path.exists() and static_path.is_file():
        return send_file(
            static_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/octet-stream",
        )

    external_url = pkg.get("external_url") or releases.get("download_url")
    if external_url:
        return redirect(external_url)

    flash("Binary is temporarily unavailable for direct local stream. Please check back shortly.", "error")
    return redirect(url_for("audio_suite.downloads_view"))


@audio_suite_bp.route("/api/downloads/stage/update", methods=["POST"])
def stage_update_release():
    if not session.get("admin", False):
        return jsonify({"error": "Administrative clearance required."}), 403

    data = request.get_json(silent=True) or request.form.to_dict()
    releases = get_releases_data()

    if "version" in data and str(data["version"]).strip():
        releases["version"] = str(data["version"]).strip()
    if "release_title" in data and str(data["release_title"]).strip():
        releases["release_title"] = str(data["release_title"]).strip()
    if "stage_status" in data and str(data["stage_status"]).strip():
        status = str(data["stage_status"]).strip().upper()
        if status in ("PUBLISHED", "STAGED", "DRAFT"):
            releases["stage_status"] = status
    if "download_url" in data and str(data["download_url"]).strip():
        releases["download_url"] = str(data["download_url"]).strip()
    if "changelog" in data and str(data["changelog"]).strip():
        releases["changelog"] = str(data["changelog"]).strip()

    save_releases_data(releases)
    return jsonify({
        "success": True,
        "message": "Staged release metadata successfully updated.",
        "releases": releases,
    })


@audio_suite_bp.route("/api/downloads/stage/sync_dist", methods=["POST"])
def stage_sync_dist():
    if not session.get("admin", False):
        return jsonify({"error": "Administrative clearance required."}), 403

    result = sync_dist_binaries_on_disk()
    return jsonify(result)


@audio_suite_bp.route("/api/audio_suite/admin/toggle_revoke", methods=["POST"])
def toggle_license_revoke():
    if not session.get("admin", False):
        return jsonify({"error": "Administrative clearance required."}), 403

    data = request.get_json(silent=True) or {}
    hwid = str(data.get("hwid", "")).strip()
    if not hwid:
        return jsonify({"error": "Hardware identifier is required."}), 400

    licenses = {}
    if LICENSES_FILE.exists():
        try:
            licenses = json.loads(LICENSES_FILE.read_text(encoding="utf-8"))
        except Exception:
            licenses = {}

    if hwid not in licenses:
        return jsonify({"error": f"No license found for HWID '{hwid}'."}), 404

    record = licenses[hwid]
    current_revoked = record.get("remote_revoked", False)
    record["remote_revoked"] = not current_revoked

    server_now = int(time.time())
    first_run = record.get("first_run", server_now)
    duration_days = record.get("duration_days", 14)
    expires_at = first_run + (duration_days * 86400)

    if record["remote_revoked"]:
        new_status = "REVOKED"
    elif server_now >= expires_at:
        new_status = "EXPIRED"
    else:
        new_status = "ACTIVE"

    record["status"] = new_status
    LICENSES_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSES_FILE.write_text(json.dumps(licenses, indent=2), encoding="utf-8")

    return jsonify({
        "success": True,
        "hwid": hwid,
        "remote_revoked": record["remote_revoked"],
        "status": new_status,
        "message": f"Hardware trial for {hwid[:8]}... is now {new_status}.",
    })


@audio_suite_bp.route("/api/audio_suite/admin/extend_license", methods=["POST"])
def extend_license_duration():
    if not session.get("admin", False):
        return jsonify({"error": "Administrative clearance required."}), 403

    data = request.get_json(silent=True) or {}
    hwid = str(data.get("hwid", "")).strip()
    days = int(data.get("days", 14))

    if not hwid:
        return jsonify({"error": "Hardware identifier is required."}), 400

    licenses = {}
    if LICENSES_FILE.exists():
        try:
            licenses = json.loads(LICENSES_FILE.read_text(encoding="utf-8"))
        except Exception:
            licenses = {}

    if hwid not in licenses:
        return jsonify({"error": f"No license found for HWID '{hwid}'."}), 404

    record = licenses[hwid]
    record["duration_days"] = record.get("duration_days", 14) + max(1, days)
    record["remote_revoked"] = False

    server_now = int(time.time())
    first_run = record.get("first_run", server_now)
    expires_at = first_run + (record["duration_days"] * 86400)

    record["status"] = "ACTIVE" if server_now < expires_at else "EXPIRED"
    LICENSES_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSES_FILE.write_text(json.dumps(licenses, indent=2), encoding="utf-8")

    return jsonify({
        "success": True,
        "hwid": hwid,
        "duration_days": record["duration_days"],
        "status": record["status"],
        "message": f"Extended trial for {hwid[:8]}... to {record['duration_days']} total days.",
    })


@audio_suite_bp.route("/api/audio_suite/admin/delete_feedback", methods=["POST"])
def delete_feedback_item():
    if not session.get("admin", False):
        return jsonify({"error": "Administrative clearance required."}), 403

    data = request.get_json(silent=True) or {}
    feedback_id = str(data.get("id", "")).strip()
    if not feedback_id:
        return jsonify({"error": "Feedback ID is required."}), 400

    feedback_list = get_feedback_summary()
    new_list = [item for item in feedback_list if item.get("id") != feedback_id]

    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(new_list, indent=2), encoding="utf-8")

    return jsonify({
        "success": True,
        "deleted_id": feedback_id,
        "remaining_count": len(new_list),
    })
