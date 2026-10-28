"""Cyber Intelligence Hub & On-Demand Beginner Doc Suite Blueprint.

Enforces the Transient Disk Cache Architecture:
1. When an email is generated, the previous temporary disk cache is purged and replaced.
2. When a reader clicks "Read More" (/hub/story/<story_id>):
   - If present in the temporary disk cache: loads instantly.
   - If not cached: synthesized on-demand by the agent engine, written to disk, and served.
3. RAM is kept clean by streaming and reading from disk files on demand.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, abort, request, jsonify, redirect, url_for
import markdown

from config import Config
from doc_suite_engine import generate_full_intel_bundle

config = Config()
hub_bp = Blueprint('hub', __name__)

CACHE_DIR = config.ROOT_DIR / "cache"
TEMP_DOCS_DIR = CACHE_DIR / "temp_docs"
MANIFEST_FILE = CACHE_DIR / "current_digest_manifest.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DOCS_DIR.mkdir(parents=True, exist_ok=True)

def purge_temp_docs_cache() -> int:
    """Removes all temporary cached story files from disk to keep storage and RAM clean."""
    count = 0
    if TEMP_DOCS_DIR.exists():
        for item in TEMP_DOCS_DIR.glob("*.json"):
            try:
                item.unlink()
                count += 1
            except OSError:
                pass
    return count

def get_disk_cached_doc(story_id: str) -> Optional[dict]:
    """Retrieves documentation bundle from temporary disk cache if it exists."""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", story_id).strip("-")
    target_file = TEMP_DOCS_DIR / f"{safe_id}.json"
    if target_file.exists():
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def save_disk_cached_doc(story_id: str, bundle: dict) -> Path:
    """Writes the generated documentation bundle to temporary disk cache."""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", story_id).strip("-")
    target_file = TEMP_DOCS_DIR / f"{safe_id}.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)
    return target_file

def load_active_manifest() -> dict:
    """Loads the active email digest manifest from disk."""
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"dispatched_at": "Recent Digest", "total_items": 0, "items": []}

def save_active_manifest(items: list, dispatched_at: Optional[str] = None) -> Path:
    """Saves the current email digest items and wipes stale temporary cache files."""
    purge_temp_docs_cache()
    data = {
        "dispatched_at": dispatched_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_items": len(items),
        "items": items
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return MANIFEST_FILE

@hub_bp.route('/hub')
def hub_index():
    manifest = load_active_manifest()
    items = manifest.get("items", [])
    cached_count = len(list(TEMP_DOCS_DIR.glob("*.json"))) if TEMP_DOCS_DIR.exists() else 0
    return render_template(
        'hub.html',
        active_tab='hub',
        manifest=manifest,
        items=items,
        cached_count=cached_count
    )

@hub_bp.route('/hub/story/<story_id>')
def hub_story(story_id: str):
    """The 'Read More' destination: checks disk cache first (instant), generates via agent if uncached."""
    cached_bundle = get_disk_cached_doc(story_id)
    is_instant_cache = False

    if cached_bundle:
        bundle = cached_bundle
        is_instant_cache = True
        cache_badge = "⚡ Loaded Instantly from Disk Cache"
    else:
        # On-Demand Agent Generation
        manifest = load_active_manifest()
        found_intel = None
        for item in manifest.get("items", []):
            if item.get("story_id") == story_id:
                found_intel = item
                break

        if not found_intel:
            # Fallback for direct links or custom stories
            found_intel = {
                "story_id": story_id,
                "title": story_id.replace("-", " ").title(),
                "summary": f"Detailed vulnerability and threat advisory for {story_id}.",
                "source": "Genesis Intelligence Telemetry",
                "score": 85,
                "threat_level": "HIGH"
            }

        bundle = generate_full_intel_bundle(found_intel)
        save_disk_cached_doc(story_id, bundle)
        cache_badge = "✨ Generated on First Read & Cached to Disk"

    # Pre-render markdown for doc suite pillars
    rendered_pillars = {}
    doc_suite = bundle.get("doc_suite", {})
    for pillar_key, pillar_data in doc_suite.items():
        raw_md = pillar_data.get("content", "")
        rendered_html = markdown.markdown(
            raw_md,
            extensions=['tables', 'fenced_code', 'toc']
        )
        rendered_pillars[pillar_key] = {
            "title": pillar_data.get("title", pillar_key),
            "subtitle": pillar_data.get("subtitle", ""),
            "html": rendered_html
        }

    return render_template(
        'hub_story.html',
        active_tab='hub',
        story=bundle,
        story_obj=bundle.get("story", {}),
        rendered_pillars=rendered_pillars,
        is_instant_cache=is_instant_cache,
        cache_badge=cache_badge
    )

@hub_bp.route('/api/hub/story/<story_id>')
def api_hub_story(story_id: str):
    """Returns JSON payload for the story bundle (cached or generated)."""
    cached_bundle = get_disk_cached_doc(story_id)
    if cached_bundle:
        return jsonify({"status": "cached", "data": cached_bundle})

    manifest = load_active_manifest()
    found_intel = None
    for item in manifest.get("items", []):
        if item.get("story_id") == story_id:
            found_intel = item
            break

    if not found_intel:
        found_intel = {
            "story_id": story_id,
            "title": story_id.replace("-", " ").title(),
            "summary": f"Vulnerability advisory for {story_id}."
        }

    bundle = generate_full_intel_bundle(found_intel)
    save_disk_cached_doc(story_id, bundle)
    return jsonify({"status": "generated_and_cached", "data": bundle})

@hub_bp.route('/api/hub/new-digest', methods=['POST'])
def api_new_digest():
    """Replaces the active digest manifest and purges old temporary disk cache."""
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    dispatched_at = data.get("dispatched_at")

    if not items:
        return jsonify({"status": "error", "message": "No items provided"}), 400

    save_active_manifest(items, dispatched_at=dispatched_at)
    return jsonify({
        "status": "success",
        "message": f"Registered {len(items)} items. Previous disk cache purged.",
        "dispatched_at": dispatched_at
    })

@hub_bp.route('/api/hub/status')
def api_hub_status():
    """Returns disk cache metrics and active digest metadata."""
    manifest = load_active_manifest()
    cached_files = [f.name for f in TEMP_DOCS_DIR.glob("*.json")] if TEMP_DOCS_DIR.exists() else []
    return jsonify({
        "dispatched_at": manifest.get("dispatched_at"),
        "total_manifest_items": manifest.get("total_items", 0),
        "cached_temp_docs_count": len(cached_files),
        "cached_docs": cached_files
    })
