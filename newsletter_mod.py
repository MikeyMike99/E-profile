"""Cyber Intelligence Newsletter & On-Demand Beginner Doc Suite Blueprint.

Enforces the Transient Disk Cache Architecture:
1. When an email or feed is refreshed, the previous temporary disk cache is purged and replaced.
2. When a reader clicks "Read More" (/newsletter/story/<story_id>):
   - If present in the temporary disk cache: loads instantly.
   - If not cached: synthesized on-demand by the agent engine, written to disk, and served.
3. Multi-perspective Story Appetites:
   - Readers can generate stories matching their appetite (Cyber Thriller, Deep Dive Forensics,
     Defense Playbook, Executive Espresso, Snarky Hacker) powered by Claude or Antigravity.
4. RAM is kept clean by streaming and reading from disk files on demand.
5. Backwards compatibility: issues 301 Permanent Redirects for legacy /hub endpoints.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from flask import Blueprint, render_template, abort, request, jsonify, redirect, url_for, session
import markdown

from config import Config
from doc_suite_engine import generate_full_intel_bundle
from threat_intel_engine import ThreatIntelEngine
from story_agent_dispatcher import (
    dispatch_story_generation,
    get_cached_story,
    APPETITE_CONFIG
)

config = Config()
newsletter_bp = Blueprint('newsletter', __name__)
hub_bp = newsletter_bp

CACHE_DIR = config.ROOT_DIR / "cache"
TEMP_DOCS_DIR = CACHE_DIR / "temp_docs"
MANIFEST_FILE = CACHE_DIR / "current_digest_manifest.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DOCS_DIR.mkdir(parents=True, exist_ok=True)

threat_engine = ThreatIntelEngine()


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
    """Loads the active email/threat digest manifest from disk."""
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("items"):
                    return data
        except Exception:
            pass

    # Safe Instant Seed Initialization (Zero-blocking: eliminates synchronous external API delays on web requests)
    try:
        seed = threat_engine.get_seed_manifest()
        if seed and seed.get("items"):
            with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
                json.dump(seed, f, indent=2)
            return seed
    except Exception:
        pass

    return {"dispatched_at": "Recent Digest", "total_items": 0, "items": []}


def save_active_manifest(items: list, dispatched_at: Optional[str] = None) -> Path:
    """Saves the current digest items and wipes stale temporary cache files."""
    purge_temp_docs_cache()
    # Sort descending so newest is always on top
    for idx, it in enumerate(items):
        it["is_latest"] = (idx == 0)

    data = {
        "dispatched_at": dispatched_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_items": len(items),
        "items": items
    }
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return MANIFEST_FILE


# --- PRIMARY NEWSLETTER ROUTES ---

@newsletter_bp.route('/newsletter')
def newsletter_index():
    manifest = load_active_manifest()
    items = manifest.get("items", [])
    cached_count = len(list(TEMP_DOCS_DIR.glob("*.json"))) if TEMP_DOCS_DIR.exists() else 0
    feed_status = threat_engine.get_feed_status(cached=True)
    is_admin = bool(session.get("admin") or session.get("is_admin"))

    return render_template(
        'newsletter.html',
        active_tab='newsletter',
        manifest=manifest,
        items=items,
        cached_count=cached_count,
        feed_status=feed_status,
        appetites=APPETITE_CONFIG,
        is_admin=is_admin
    )


@newsletter_bp.route('/newsletter/story/<story_id>')
def newsletter_story(story_id: str):
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

    # Pre-load initial appetite story if cached (e.g. cyber_thriller)
    initial_appetite = "cyber_thriller"
    initial_story = get_cached_story(story_id, initial_appetite)
    initial_rendered_story = None
    if initial_story:
        initial_rendered_story = markdown.markdown(
            initial_story.get("markdown", ""),
            extensions=['tables', 'fenced_code']
        )

    return render_template(
        'newsletter_story.html',
        active_tab='newsletter',
        story=bundle,
        story_obj=bundle.get("story", {}),
        rendered_pillars=rendered_pillars,
        is_instant_cache=is_instant_cache,
        cache_badge=cache_badge,
        appetites=APPETITE_CONFIG,
        initial_appetite=initial_appetite,
        initial_story=initial_story,
        initial_rendered_story=initial_rendered_story
    )


# --- API ENDPOINTS ---

@newsletter_bp.route('/api/newsletter/generate-story', methods=['POST'])
def api_generate_appetite_story():
    """Generates or retrieves a cached incident story tailored to user appetite and engine."""
    data = request.get_json(silent=True) or {}
    story_id = data.get("story_id")
    appetite = data.get("appetite", "cyber_thriller")
    engine = data.get("engine", "claude")

    if not story_id:
        return jsonify({"status": "error", "message": "story_id is required"}), 400

    result = dispatch_story_generation(
        story_id=story_id,
        appetite=appetite,
        engine_choice=engine
    )

    rendered_html = markdown.markdown(
        result.get("markdown", ""),
        extensions=['tables', 'fenced_code']
    )

    return jsonify({
        "status": "success",
        "data": result,
        "html": rendered_html
    })


@newsletter_bp.route('/api/newsletter/refresh', methods=['POST'])
def api_newsletter_refresh():
    """Triggers a quota-compliant feed refresh. Admins can pass force=true."""
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))
    is_admin = bool(session.get("admin") or session.get("is_admin"))

    if force and not is_admin:
        force = False

    result = threat_engine.refresh_feed(force=force)
    return jsonify({
        "status": "success",
        "refresh_result": result
    })


@newsletter_bp.route('/api/newsletter/status')
def api_newsletter_status():
    """Returns feed status, quota meters, and disk cache metrics."""
    status_info = threat_engine.get_feed_status()
    cached_files = [f.name for f in TEMP_DOCS_DIR.glob("*.json")] if TEMP_DOCS_DIR.exists() else []
    status_info["cached_temp_docs_count"] = len(cached_files)
    status_info["cached_docs"] = cached_files
    return jsonify(status_info)


@newsletter_bp.route('/api/newsletter/story/<story_id>')
def api_newsletter_story(story_id: str):
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


@newsletter_bp.route('/api/newsletter/new-digest', methods=['POST'])
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


# --- BACKWARDS-COMPATIBILITY REDIRECTS & ALIASES ---

@newsletter_bp.route('/api/newsletter/subscribe', methods=['POST'])
def api_newsletter_subscribe():
    from notify_mod import subscribe_newsletter
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    email = data.get("email", "").strip()
    delivery_format = data.get("format", "hybrid_brief")
    primary_appetite = data.get("appetite", "cyber_thriller")
    topics = data.get("topics")
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(",") if t.strip()]
    engagement_modules = data.get("engagement_modules")

    try:
        sub = subscribe_newsletter(
            email=email,
            delivery_format=delivery_format,
            primary_appetite=primary_appetite,
            topics=topics,
            engagement_modules=engagement_modules
        )
        return jsonify({
            "status": "success",
            "message": f"Successfully subscribed {sub['email']} to Cyber Threat Intelligence.",
            "subscriber_id": sub.get("subscriber_id"),
            "token": sub.get("token")
        })
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Subscription failed: {str(exc)}"}), 500


@newsletter_bp.route('/newsletter/preferences', methods=['GET'])
def newsletter_preferences_view():
    from notify_mod import get_subscriber_by_token, touch_subscriber_activity, VALID_FORMATS, VALID_APPETITES, VALID_TOPICS
    token = request.args.get("token", "").strip()
    subscriber = get_subscriber_by_token(token) if token else None
    if subscriber and token:
        touch_subscriber_activity(token)

    return render_template(
        'newsletter_preferences.html',
        active_tab='newsletter',
        subscriber=subscriber,
        token=token,
        appetites=APPETITE_CONFIG,
        valid_formats=VALID_FORMATS,
        valid_topics=VALID_TOPICS
    )


@newsletter_bp.route('/newsletter/preferences', methods=['POST'])
def newsletter_preferences_update():
    from notify_mod import update_subscriber_preferences
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token = (data.get("token") or request.args.get("token", "")).strip()

    if not token:
        return jsonify({"status": "error", "message": "Preference token is required."}), 400

    delivery_format = data.get("format")
    primary_appetite = data.get("appetite")
    topics = data.get("topics")
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(",") if t.strip()]
    engagement_modules = data.get("engagement_modules")
    status = data.get("status")

    updated = update_subscriber_preferences(
        token=token,
        delivery_format=delivery_format,
        primary_appetite=primary_appetite,
        topics=topics,
        engagement_modules=engagement_modules,
        status=status
    )
    if not updated:
        return jsonify({"status": "error", "message": "Invalid or expired subscriber token."}), 404

    return jsonify({
        "status": "success",
        "message": "Preferences updated successfully.",
        "subscriber": updated
    })


@newsletter_bp.route('/terms', methods=['GET'])
@newsletter_bp.route('/terms-and-conditions', methods=['GET'])
def newsletter_terms_view():
    return render_template('terms.html', active_tab='newsletter', title='Terms and Conditions · Threat Intelligence')


@newsletter_bp.route('/newsletter/unsubscribe', methods=['GET', 'POST'])
def newsletter_unsubscribe():
    from notify_mod import unsubscribe_by_token, purge_subscriber_by_token, VALID_FORMATS, VALID_TOPICS
    token = request.args.get("token", "").strip()
    if not token and request.is_json:
        token = (request.get_json(silent=True) or {}).get("token", "").strip()
    elif not token and request.form:
        token = request.form.get("token", "").strip()

    if not token:
        return jsonify({"status": "error", "message": "Missing unsubscribe token."}), 400

    purge_arg = request.args.get("purge", "").lower()
    json_purge = (request.get_json(silent=True) or {}).get("purge") if request.is_json else None
    form_purge = request.form.get("purge", "").lower() if request.form else None

    should_purge = purge_arg in ("1", "true", "yes") or bool(json_purge) or (form_purge in ("1", "true", "yes"))

    if should_purge:
        purged_entry = purge_subscriber_by_token(token)
        if not purged_entry:
            return jsonify({"status": "error", "message": "Subscriber token not found or already purged."}), 404

        email = purged_entry.get("email", "")
        if request.method == "POST" or request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({
                "status": "success",
                "message": f"Subscriber {email} and all associated data have been permanently purged.",
                "purged": True,
                "email": email
            }), 200

        return render_template(
            'newsletter_preferences.html',
            active_tab='newsletter',
            subscriber={"status": "purged", "email": email},
            unsubscribed_notice=True,
            purged_notice=True,
            purged_email=email,
            token="",
            appetites=APPETITE_CONFIG,
            valid_formats=VALID_FORMATS,
            valid_topics=VALID_TOPICS
        )

    ok = unsubscribe_by_token(token, purge=False)
    if not ok:
        return jsonify({"status": "error", "message": "Subscriber token not found."}), 404

    if request.method == "POST" or request.headers.get("Accept") == "application/json" or request.is_json:
        return jsonify({"status": "success", "message": "You have been successfully unsubscribed."}), 200

    return render_template(
        'newsletter_preferences.html',
        active_tab='newsletter',
        subscriber={"status": "unsubscribed"},
        unsubscribed_notice=True,
        purged_notice=False,
        token=token,
        appetites=APPETITE_CONFIG,
        valid_formats=VALID_FORMATS,
        valid_topics=VALID_TOPICS
    )


@newsletter_bp.route('/newsletter/r/<link_id>')
def newsletter_redirect_tracker(link_id: str):
    from notify_mod import decode_tracking_token, record_newsletter_click, touch_subscriber_activity
    decoded = decode_tracking_token(link_id)
    if not decoded:
        return redirect(url_for('newsletter.newsletter_index'), code=302)

    slot = decoded.get("s", "unknown")
    target_url = decoded.get("u", "/newsletter")
    sub_token = decoded.get("t")
    if sub_token:
        touch_subscriber_activity(sub_token)

    if not target_url.startswith("/") or target_url.startswith("//"):
        target_url = "/newsletter"

    record_newsletter_click(slot, target_url)
    return redirect(target_url, code=302)


@newsletter_bp.route('/api/newsletter/dispatch', methods=['POST'])
def api_newsletter_dispatch():
    from notify_mod import notify_newsletter
    is_admin = bool(session.get("admin") or session.get("is_admin"))
    cron_token = request.headers.get("X-Cron-Token") or request.args.get("cron_token")
    valid_cron = bool(cron_token and cron_token == getattr(config, "ADMIN_KEY", ""))

    if not is_admin and not valid_cron:
        return jsonify({"status": "error", "message": "Authentication required."}), 403

    base_url = request.host_url.rstrip("/")
    result = notify_newsletter(base_url=base_url)
    return jsonify({
        "status": "success",
        **result
    })


@newsletter_bp.route('/hub')
def legacy_hub_redirect():
    """Permanent 301 redirect for legacy /hub requests."""
    return redirect(url_for('newsletter.newsletter_index'), code=301)


@newsletter_bp.route('/hub/story/<story_id>')
def legacy_hub_story_redirect(story_id: str):
    """Permanent 301 redirect for legacy /hub/story/<story_id> requests."""
    return redirect(url_for('newsletter.newsletter_story', story_id=story_id), code=301)


@newsletter_bp.route('/api/hub/story/<story_id>')
def legacy_api_hub_story(story_id: str):
    return api_newsletter_story(story_id)


@newsletter_bp.route('/api/hub/new-digest', methods=['POST'])
def legacy_api_hub_new_digest():
    return api_new_digest()


@newsletter_bp.route('/api/hub/status')
def legacy_api_hub_status():
    return api_newsletter_status()
