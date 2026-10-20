import os
import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, abort, request, jsonify, redirect, url_for, session
import markdown
from config import Config
from sensitivity_engine import filter_document_by_sensitivity, compute_document_sensitivity

config = Config()
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

DOCS_DIR = config.CONTENT_DIR / "docs"
CATALOG_PATH = DOCS_DIR / "docs_catalog.json"
RELEASE_SCHEDULE_PATH = DOCS_DIR / "release_schedule.json"
CENTRAL_DOCS_DIR = getattr(config, 'CENTRAL_DOCS_DIR', Path("/mnt/c/Users/michael/Documents/Central_Docs"))
CENTRAL_RELEASE_SCHEDULE_PATH = CENTRAL_DOCS_DIR / "release_schedule.json"
DEVCORE_DOCS_DIR = getattr(config, 'DEVCORE_DOCS_DIR', Path("/mnt/c/Users/michael/Documents/DevCore/docs"))
AUDIO_DOCS_DIR = getattr(config, 'AUDIO_DOCS_DIR', Path("/mnt/c/Users/michael/Documents/Audio_pllayback_suite/docs"))

COLLECTIONS = {
    "devlog": {
        "title": "5-Pillar Architecture Devlog Suite",
        "badge": "199 Chapters",
        "icon": "⚡",
        "desc": "Modular technical reference spanning problems encountered, source evidence, diagnostic benchmarks, architecture, and step-by-step guides."
    },
    "textbook": {
        "title": "Zero-Trust Cybersecurity Textbook",
        "badge": "50 Chapters",
        "icon": "🛡️",
        "desc": "Comprehensive curriculum covering asset defense, AAA access control, ACLs, zone-based sandboxes, bulkheads, and agentic firewalls."
    },
    "manual": {
        "title": "Siraugga Master Manual",
        "badge": "7 Modules",
        "icon": "📖",
        "desc": "Operational security modules governing telemetry, sandboxing, central SIEM logging, cryptography, and obfuscation."
    },
    "manifesto": {
        "title": "The Developer Manifesto",
        "badge": "Origin Story",
        "icon": "🌌",
        "desc": "Forensic timeline, quantitative evolution, and the origin story of the Siraugga framework."
    },
    "story": {
        "title": "The Antigravity Development Story",
        "badge": "73 Chapters",
        "icon": "📜",
        "desc": "Personal engineering narrative documenting the journey from terminal tearing and dropouts to clean-room enterprise sovereignty."
    },
    "audio_suite": {
        "title": "JOSHY Audio Suite Guides",
        "badge": "7 Chapters",
        "icon": "🎵",
        "desc": "Technical documentation for the standalone JOSHY Audio Playback Suite, Nuitka packaging, Inno Setup, and accessible_output2 speech drivers."
    },
    "guides": {
        "title": "Architecture & System Guides",
        "badge": "Specifications",
        "icon": "📐",
        "desc": "Core system specifications, security policies, hot-patch architecture, and MCP protocol documentation."
    },
    "eprofile": {
        "title": "E-Profile Architecture & Devlog",
        "badge": "Portfolio Core",
        "icon": "💼",
        "desc": "Forensic devlog, zero-trust RBAC, schema evolution, and accessibility physical access point."
    },
    "echoes": {
        "title": "Echoes of the World Architecture",
        "badge": "Audio Game Core",
        "icon": "🎮",
        "desc": "Procedural spatial audio world engine, state management, 8-way compass, and menu architecture."
    },
    "encrypt_me": {
        "title": "EncryptMe Multi-User Vault",
        "badge": "Cryptographic Tool",
        "icon": "🔐",
        "desc": "Industrial-grade PBKDF2 symmetric cryptography, split-key entropy recovery, and memory zeroization."
    }
}

PROJECTS = {
    "all": {"title": "All Projects", "icon": "🌐", "desc": "Unified cross-project documentation vault"},
    "siraugga": {"title": "Siraugga / DevCore Framework", "icon": "⚡", "desc": "Core agentic execution engine, zero-restart WebSocket streaming, Zero-Trust Textbook, Master Manual, and 5-Pillar Devlogs"},
    "eprofile": {"title": "E-Profile Portal", "icon": "💼", "desc": "Public portfolio portal, self-mutating LibCST AST code surgery, and zero-trust RBAC architecture"},
    "encrypt_me": {"title": "EncryptMe Multi-User Vault", "icon": "🔐", "desc": "Industrial-grade PBKDF2 symmetric cryptography, split-key recovery (IGAR), and memory zeroization"},
    "echoes": {"title": "Echoes of the World (Audio Game)", "icon": "🎮", "desc": "Procedural spatial audio world engine, 8-way compass, audio trigonometry, and tabbed menu state machine"},
    "audio_suite": {"title": "JOSHY Audio Suite", "icon": "🎵", "desc": "Standalone audio playback suite, accessible_output2 speech drivers, Tolk DLL bridging, and Nuitka binary packaging"},
    "accessible_apps": {"title": "Accessible Applications", "icon": "♿", "desc": "Screen-reader optimized developer tooling, Exam Generator, and accessible media player"}
}

TOPICS = {
    "all": {"title": "All Topics", "icon": "🔍"},
    "security": {"title": "Security & Zero-Trust", "icon": "🛡️"},
    "infrastructure": {"title": "Infrastructure & Systems", "icon": "🖥️"},
    "accessibility_ui": {"title": "UI & Accessibility (WCAG)", "icon": "♿"},
    "workflow": {"title": "Workflow & Automation", "icon": "⚙️"},
    "limitations": {"title": "Limitations & Traps", "icon": "⚠️"},
    "origin_story": {"title": "The Story & Manifesto", "icon": "🌌"},
    "changelog": {"title": "Devlog & Changelog", "icon": "📜"}
}

FOUNDATIONAL_PUBLISHED_KEYS = set()

_last_sync_check = 0

def auto_sync_if_needed():
    """
    Zero-touch automatic documentation synchronization:
    Detects if Central_Docs or workspace sources are newer than docs_catalog.json,
    and automatically rebuilds the catalog and cache.
    """
    global _last_sync_check
    import time
    now = time.time()
    if now - _last_sync_check < 3:
        return
    _last_sync_check = now

    try:
        needs_sync = False
        if not CATALOG_PATH.exists():
            needs_sync = True
        else:
            cat_mtime = CATALOG_PATH.stat().st_mtime
            if CENTRAL_DOCS_DIR.exists():
                projects_dir = CENTRAL_DOCS_DIR / "projects"
                if projects_dir.exists() and projects_dir.stat().st_mtime > cat_mtime:
                    needs_sync = True
                git_log = CENTRAL_DOCS_DIR / ".git" / "logs" / "HEAD"
                if git_log.exists() and git_log.stat().st_mtime > cat_mtime:
                    needs_sync = True

        if needs_sync and CENTRAL_DOCS_DIR.exists():
            sync_script = CENTRAL_DOCS_DIR / "scripts" / "sync_to_eprofile.py"
            if sync_script.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("central_sync", str(sync_script))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, 'sync'):
                    mod.sync()
    except Exception as e:
        print(f"[DocsMod] Auto-sync encountered: {e}")

def load_catalog():
    auto_sync_if_needed()
    if not CATALOG_PATH.exists():
        return []
    try:
        with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def load_release_schedule():
    if not RELEASE_SCHEDULE_PATH.exists():
        if CENTRAL_RELEASE_SCHEDULE_PATH.exists():
            try:
                data = json.loads(CENTRAL_RELEASE_SCHEDULE_PATH.read_text(encoding='utf-8'))
                save_release_schedule(data)
                return data
            except Exception:
                pass
        initial_entries = {}
        for s in FOUNDATIONAL_PUBLISHED_KEYS:
            initial_entries[s] = {
                "status": "published",
                "release_date": None,
                "updated_at": datetime.now().isoformat()
            }
        data = {
            "version": "1.0",
            "default_policy": "draft",
            "entries": initial_entries
        }
        save_release_schedule(data)
        return data
    try:
        with open(RELEASE_SCHEDULE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"version": "1.0", "default_policy": "draft", "entries": {}}

def save_release_schedule(schedule_data):
    try:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        with open(RELEASE_SCHEDULE_PATH, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, indent=2)
        if CENTRAL_DOCS_DIR.exists():
            try:
                with open(CENTRAL_RELEASE_SCHEDULE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(schedule_data, f, indent=2)
            except Exception:
                pass
    except Exception as e:
        print(f"[DocsMod] Failed to save release schedule: {e}")

def get_user_catalog(catalog, is_admin=False):
    schedule = load_release_schedule()
    entries = schedule.get("entries", {})
    now_iso = datetime.now().isoformat()
    
    result = []
    for d in catalog:
        c = d.get('category', '')
        s = d.get('slug', '')
        key = f"{c}/{s}"
        entry = entries.get(key) or entries.get(s)
        
        status = d.get('publish_status')
        release_date = d.get('release_date')
        if entry:
            status = entry.get('status', status or 'draft')
            release_date = entry.get('release_date', release_date)
            
        if not status:
            if key in FOUNDATIONAL_PUBLISHED_KEYS or s in FOUNDATIONAL_PUBLISHED_KEYS:
                status = 'published'
            else:
                status = 'draft'
                
        is_released = False
        if status == 'published':
            is_released = True
        elif status == 'scheduled' and release_date:
            is_released = (now_iso >= release_date)
            
        d_copy = dict(d)
        d_copy['publish_status'] = status
        d_copy['release_date'] = release_date
        d_copy['is_released'] = is_released
        
        if is_admin:
            result.append(d_copy)
        else:
            if is_released:
                result.append(d_copy)
                
    return result

CURATED_NARRATIVE_FLOW = [
    ('devlog', '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD'),
    ('manifesto', '01_Echoes_in_the_Void'),
    ('manifesto', '02_The_Echoes_Architecture'),
    ('manifesto', '03_The_Forge_of_Sovereignty'),
    ('manifesto', '04_The_24_Hour_Crucible'),
    ('eprofile', 'DEVLOG'),
    ('manifesto', '05_The_Quantitative_Era')
]

def get_prev_next(catalog, category, slug):
    flow_idx = -1
    for i, (f_cat, f_slug) in enumerate(CURATED_NARRATIVE_FLOW):
        if f_slug == slug and (f_cat == category or not category):
            flow_idx = i
            break

    if flow_idx != -1:
        prev_doc = None
        next_doc = None
        if flow_idx > 0:
            p_cat, p_slug = CURATED_NARRATIVE_FLOW[flow_idx - 1]
            prev_doc = next((d for d in catalog if d.get('category') == p_cat and d.get('slug') == p_slug), None)
            if not prev_doc:
                prev_doc = next((d for d in catalog if d.get('slug') == p_slug), None)
        if flow_idx < len(CURATED_NARRATIVE_FLOW) - 1:
            n_cat, n_slug = CURATED_NARRATIVE_FLOW[flow_idx + 1]
            next_doc = next((d for d in catalog if d.get('category') == n_cat and d.get('slug') == n_slug), None)
            if not next_doc:
                next_doc = next((d for d in catalog if d.get('slug') == n_slug), None)
        return prev_doc, next_doc

    cat_items = [d for d in catalog if d.get('category') == category]
    idx = -1
    for i, item in enumerate(cat_items):
        if item.get('slug') == slug:
            idx = i
            break
    prev_doc = cat_items[idx - 1] if idx > 0 else None
    next_doc = cat_items[idx + 1] if idx != -1 and idx < len(cat_items) - 1 else None
    return prev_doc, next_doc

def clean_markdown_text(raw_text: str) -> str:
    text = raw_text
    def fix_link_label(match):
        label = match.group(1).strip()
        url = match.group(2)
        if '.md' in label or '../' in label or './' in label:
            cleaned = label.replace('../', '').replace('./', '')
            if '/' in cleaned:
                cleaned = cleaned.split('/')[-1]
            if cleaned.endswith('.md'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.replace('_', ' ')
            if '00 README INDEX' in cleaned.upper():
                cleaned = '📖 Master Index'
            elif '00A' in cleaned.upper() or '00B' in cleaned.upper():
                cleaned = f'🚀 Primer: {cleaned}'
            elif re.match(r'0\d \d\d', cleaned):
                cleaned = f'⚡ Chapter: {cleaned}'
            return f'[{cleaned}]({url})'
        return match.group(0)

    text = re.sub(r'\[([^\]]+)\]\((/docs/[^)]+)\)', fix_link_label, text)
    return text

def resolve_physical_file(category, doc_slug, doc_meta=None):
    if not doc_meta:
        catalog = load_catalog()
        doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
        
    paths = []
    if CENTRAL_DOCS_DIR.exists():
        candidates = []
        if doc_meta and doc_meta.get('rel_path'):
            rel = doc_meta.get('rel_path')
            candidates.append(CENTRAL_DOCS_DIR / "projects" / "siraugga_framework" / rel)
            candidates.append(CENTRAL_DOCS_DIR / "projects" / "audio_suite" / rel)
            candidates.append(CENTRAL_DOCS_DIR / "projects" / rel)
        candidates.extend([
            CENTRAL_DOCS_DIR / "projects" / "eprofile" / f"{doc_slug}.md",
            CENTRAL_DOCS_DIR / "projects" / "eprofile" / category / f"{doc_slug}.md",
            CENTRAL_DOCS_DIR / "projects" / "siraugga_framework" / category / f"{doc_slug}.md",
            CENTRAL_DOCS_DIR / "projects" / "siraugga_framework" / f"{doc_slug}.md",
            CENTRAL_DOCS_DIR / "projects" / "audio_suite" / f"{doc_slug}.md",
            CENTRAL_DOCS_DIR / "projects" / "encrypt_me" / f"{doc_slug}.md",
            CENTRAL_DOCS_DIR / "projects" / "echoes_of_the_world" / f"{doc_slug}.md",
        ])
        for c in candidates:
            if c.exists() and c.is_file():
                paths.append(c)
                break
                
    docs_candidate = None
    if doc_meta and doc_meta.get('rel_path'):
        p = DOCS_DIR / doc_meta.get('rel_path', '')
        if p.exists() and p.is_file():
            docs_candidate = p
    if not docs_candidate:
        p = DOCS_DIR / category / f"{doc_slug}.md"
        if p.exists() and p.is_file():
            docs_candidate = p
            
    if docs_candidate and docs_candidate not in paths:
        paths.append(docs_candidate)
        
    return paths

def render_unreleased_notice(title, status, release_date):
    date_str = f"on <strong>{release_date}</strong>" if release_date else "soon in our scheduled rollout"
    return f"""
    <div class="unreleased-holding-box" role="region" aria-label="Scheduled Release Notice" style="padding: 45px 30px; text-align: center; background: rgba(12, 16, 24, 0.95); border: 1px solid rgba(255, 170, 0, 0.4); border-radius: 12px; margin: 30px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        <div style="font-size: 2.8rem; margin-bottom: 12px;">🕒</div>
        <h2 style="font-family: monospace; color: #ffaa00; font-size: 1.5rem; margin-bottom: 10px;">Chapter Scheduled for Release</h2>
        <h3 style="font-family: monospace; color: #fff; font-size: 1.2rem; margin-bottom: 16px;">{title}</h3>
        <p style="color: var(--text-bright); font-size: 0.98rem; line-height: 1.6; max-width: 620px; margin: 0 auto 24px auto;">
            This chapter is part of the curated publication sequence and will be publicly released {date_str}.
            To ensure visitors are not overwhelmed with 300+ technical blueprints at once, chapters are released on an engineering schedule.
        </p>
        <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
            <button type="button" class="ctrl-btn portal-crumb-btn" onclick="showLandingView()" style="padding: 8px 18px; font-weight: bold; border-color: var(--accent); color: var(--accent); background: rgba(0,243,255,0.1);">
                🏛️ Return to Documentation Vault
            </button>
            <button type="button" class="ctrl-btn" onclick="openNavigatorAndSearch()" style="padding: 8px 18px;">
                📑 Explore Available Chapters
            </button>
        </div>
    </div>
    """

def render_doc_content(category, doc_slug, viewer_tier=1):
    catalog = load_catalog()
    doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    if not doc_meta:
        doc_meta = {
            "title": doc_slug.replace('_', ' '),
            "slug": doc_slug,
            "category": category,
            "project": "siraugga",
            "project_label": "Siraugga Framework",
            "word_count": 0,
            "max_sensitivity": 1,
            "base_sensitivity": 1,
            "summary": "Technical documentation."
        }

    prev_doc, next_doc = get_prev_next(catalog, category, doc_slug)

    base_sens = doc_meta.get('base_sensitivity', 1) if doc_meta else 1
    if base_sens >= 5 and viewer_tier < 5:
        return doc_meta, "__LOCKED__", prev_doc, next_doc

    paths = resolve_physical_file(category, doc_slug, doc_meta)
    if not paths:
        return None, None, None, None

    file_path = paths[0]
    try:
        raw_text = file_path.read_text(encoding='utf-8', errors='replace')
        cleaned_text = clean_markdown_text(raw_text)
        sanitized_text = filter_document_by_sensitivity(cleaned_text, viewer_tier=viewer_tier)
        html_body = markdown.markdown(sanitized_text, extensions=['fenced_code', 'tables', 'nl2br'])
        doc_id = doc_meta.get('doc_id')
        if doc_id:
            sec_idx = 1
            def _attach_h_id(match):
                nonlocal sec_idx
                tag = match.group(1)
                attrs = match.group(2)
                inner = match.group(3)
                clean = re.sub(r'<[^>]+>', '', inner).strip()
                num_m = re.match(r'^\s*(\d+(?:\.\d+)*)\.?\s+(.+)$', clean)
                sec_num = num_m.group(1).replace('.', '_') if num_m else str(sec_idx)
                if not num_m:
                    sec_idx += 1
                sec_id = f"{doc_id}-SEC-{sec_num}"
                if 'id=' not in attrs:
                    return f'<{tag} id="{sec_id}"{attrs}>{inner}</{tag}>'
                return match.group(0)
            html_body = re.sub(r'<(h[23])([^>]*)>(.*?)</\1>', _attach_h_id, html_body, flags=re.DOTALL)
            
        doc_meta['raw_markdown'] = raw_text
    except Exception as e:
        html_body = f"<p>Error rendering document: {e}</p>"

    return doc_meta, html_body, prev_doc, next_doc

def build_grouped_tree(catalog):
    project_order = ["eprofile", "encrypt_me", "echoes", "audio_suite", "siraugga", "accessible_apps"]
    by_proj = {}
    tree = []
    
    for p_key in project_order:
        p_info = PROJECTS.get(p_key, {"title": p_key.title(), "icon": "📁", "desc": ""})
        p_node = {
            "key": p_key,
            "title": p_info.get("title", p_key),
            "icon": p_info.get("icon", "📁"),
            "desc": p_info.get("desc", ""),
            "collections": {},
            "total_docs": 0
        }
        by_proj[p_key] = p_node
        tree.append(p_node)
        
    for doc in catalog:
        p_key = doc.get("project", "siraugga")
        if p_key not in by_proj:
            p_info = PROJECTS.get(p_key, {"title": doc.get("project_label", p_key.title()), "icon": "📁", "desc": ""})
            p_node = {
                "key": p_key,
                "title": p_info.get("title", doc.get("project_label", p_key.title())),
                "icon": p_info.get("icon", "📁"),
                "desc": p_info.get("desc", ""),
                "collections": {},
                "total_docs": 0
            }
            by_proj[p_key] = p_node
            tree.append(p_node)
            
        c_key = doc.get("category", "guides")
        p_node = by_proj[p_key]
        p_node["total_docs"] += 1
        
        if c_key not in p_node["collections"]:
            c_info = COLLECTIONS.get(c_key, {"title": c_key.replace('_', ' ').title(), "icon": "📄", "desc": ""})
            p_node["collections"][c_key] = {
                "key": c_key,
                "title": c_info.get("title", c_key.title()),
                "icon": c_info.get("icon", "📄"),
                "desc": c_info.get("desc", ""),
                "docs": []
            }
            
        p_node["collections"][c_key]["docs"].append(doc)
        
    return [p for p in tree if p["total_docs"] > 0]

@docs_bp.route('/api/chapter/<category>/<doc_slug>')
def docs_api_chapter(category, doc_slug):
    is_admin = session.get('admin', False) or session.get('is_admin', False)
    catalog = load_catalog()
    user_catalog = get_user_catalog(catalog, is_admin=is_admin)
    
    doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    if not doc_meta:
        return jsonify({"status": "error", "message": "Chapter not found"}), 404
        
    doc_user_meta = next((d for d in user_catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    if not doc_user_meta and not is_admin:
        schedule = load_release_schedule()
        entry = schedule.get("entries", {}).get(f"{category}/{doc_slug}") or schedule.get("entries", {}).get(doc_slug, {})
        c_info = COLLECTIONS.get(category, {})
        p_key = doc_meta.get('project', 'siraugga')
        p_info = PROJECTS.get(p_key, {})
        return jsonify({
            "status": "unreleased",
            "slug": doc_slug,
            "category": category,
            "title": doc_meta.get('title'),
            "project": p_key,
            "project_label": doc_meta.get('project_label', p_info.get('title', 'Siraugga Framework')),
            "project_icon": p_info.get('icon', '⚡'),
            "project_desc": p_info.get('desc', ''),
            "collection_title": c_info.get('title', category.title()),
            "collection_desc": c_info.get('desc', ''),
            "collection_icon": c_info.get('icon', '📄'),
            "word_count": doc_meta.get('word_count', 0),
            "read_time": max(1, round(doc_meta.get('word_count', 0) / 180)),
            "max_sensitivity": doc_meta.get('max_sensitivity', 1),
            "publish_status": entry.get('status', 'draft'),
            "release_date": entry.get('release_date'),
            "html": render_unreleased_notice(doc_meta.get('title'), entry.get('status', 'draft'), entry.get('release_date'))
        })
        
    viewer_tier = 5 if is_admin else (4 if session.get('is_employer') or ('view:proprietary_docs' in session.get('permissions', [])) else 1)
    rendered_meta, html_body, prev_doc, next_doc = render_doc_content(category, doc_slug, viewer_tier)
    if not rendered_meta or html_body is None:
        return jsonify({"status": "error", "message": "Chapter not found"}), 404
        
    c_info = COLLECTIONS.get(category, {})
    p_key = rendered_meta.get('project', 'siraugga')
    p_info = PROJECTS.get(p_key, {})

    publish_status = doc_user_meta.get('publish_status', 'published') if doc_user_meta else 'draft'
    release_date = doc_user_meta.get('release_date') if doc_user_meta else None
    
    return jsonify({
        "status": "success",
        "slug": rendered_meta.get('slug'),
        "category": rendered_meta.get('category'),
        "title": rendered_meta.get('title'),
        "project": p_key,
        "project_label": rendered_meta.get('project_label', p_info.get('title', 'Siraugga Framework')),
        "project_icon": p_info.get('icon', '⚡'),
        "project_desc": p_info.get('desc', ''),
        "collection_title": c_info.get('title', category.title()),
        "collection_desc": c_info.get('desc', ''),
        "collection_icon": c_info.get('icon', '📄'),
        "hierarchy_path": f"{p_info.get('title', 'Siraugga Framework')} → {c_info.get('title', category.title())} → {rendered_meta.get('title')}",
        "summary": rendered_meta.get('summary', ''),
        "word_count": rendered_meta.get('word_count', 0),
        "read_time": max(1, round(rendered_meta.get('word_count', 0) / 180)),
        "base_sensitivity": rendered_meta.get('base_sensitivity', 1),
        "max_sensitivity": rendered_meta.get('max_sensitivity', 1),
        "is_proprietary": rendered_meta.get('is_proprietary', False),
        "cross_references": rendered_meta.get('cross_references', []),
        "html": html_body,
        "prev_doc": prev_doc,
        "next_doc": next_doc,
        "is_admin": is_admin,
        "publish_status": publish_status,
        "release_date": release_date,
        "raw_markdown": rendered_meta.get('raw_markdown', '') if is_admin else ''
    })

@docs_bp.route('/', strict_slashes=False)
@docs_bp.route('', strict_slashes=False)
def docs_index():
    catalog = load_catalog()
    is_admin = session.get('admin', False) or session.get('is_admin', False)
    user_catalog = get_user_catalog(catalog, is_admin=is_admin)

    pub_count = sum(1 for d in catalog if d.get('publish_status') == 'published')
    draft_count = sum(1 for d in catalog if d.get('publish_status') == 'draft')
    sched_count = sum(1 for d in catalog if d.get('publish_status') == 'scheduled')
    
    if not user_catalog:
        return render_template(
            'docs.html', 
            active_tab='docs', 
            all_docs=[], 
            grouped_tree=[], 
            total_docs=0, 
            is_landing=True, 
            latest_updates=[], 
            origin_doc=None, 
            is_admin=is_admin,
            categories=COLLECTIONS,
            projects=PROJECTS,
            topics=TOPICS,
            pub_count=pub_count,
            draft_count=draft_count,
            sched_count=sched_count
        )
        
    active_slug = request.args.get('slug')
    active_cat = request.args.get('category')
    
    is_landing = False
    active_doc = None
    if active_slug and active_cat:
        active_doc = next((d for d in user_catalog if d.get('slug') == active_slug and d.get('category') == active_cat), None)
    
    if not active_doc:
        is_landing = True
        active_doc = user_catalog[0]
        
    viewer_tier = 5 if is_admin else (4 if session.get('is_employer') or ('view:proprietary_docs' in session.get('permissions', [])) else 1)
    doc_meta, html_body, prev_doc, next_doc = render_doc_content(active_doc.get('category'), active_doc.get('slug'), viewer_tier)
    if doc_meta:
        doc_meta['publish_status'] = active_doc.get('publish_status', 'published')
        doc_meta['release_date'] = active_doc.get('release_date')
        doc_meta['is_released'] = active_doc.get('is_released', True)
        
    grouped_tree = build_grouped_tree(user_catalog)
    origin_doc = next((d for d in user_catalog if d.get('slug') == '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD'), user_catalog[0])
    
    latest_updates = [d for d in user_catalog if d.get('slug') != '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD' and (d.get('is_latest') or d.get('order_score', 0) >= 13000)][:8]

    return render_template(
        'docs.html',
        active_tab='docs',
        all_docs=user_catalog,
        grouped_tree=grouped_tree,
        active_doc=doc_meta or active_doc,
        doc_html=html_body,
        prev_doc=prev_doc,
        next_doc=next_doc,
        categories=COLLECTIONS,
        projects=PROJECTS,
        topics=TOPICS,
        total_docs=len(user_catalog),
        is_landing=is_landing,
        latest_updates=latest_updates,
        origin_doc=origin_doc,
        is_admin=is_admin,
        pub_count=pub_count,
        draft_count=draft_count,
        sched_count=sched_count
    )

@docs_bp.route('/<category>')
def docs_category(category):
    if category not in COLLECTIONS:
        return redirect(url_for('docs.docs_index'))
    catalog = load_catalog()
    is_admin = session.get('admin', False) or session.get('is_admin', False)
    user_catalog = get_user_catalog(catalog, is_admin=is_admin)
    cat_docs = [d for d in user_catalog if d.get('category') == category]
    active_doc = cat_docs[0] if cat_docs else (user_catalog[0] if user_catalog else None)
    if not active_doc:
        return redirect(url_for('docs.docs_index'))
    return redirect(url_for('docs.docs_reader', category=active_doc.get('category'), doc_slug=active_doc.get('slug')))

@docs_bp.route('/<category>/<doc_slug>')
def docs_reader(category, doc_slug):
    catalog = load_catalog()
    is_admin = session.get('admin', False) or session.get('is_admin', False)
    user_catalog = get_user_catalog(catalog, is_admin=is_admin)

    pub_count = sum(1 for d in catalog if d.get('publish_status') == 'published')
    draft_count = sum(1 for d in catalog if d.get('publish_status') == 'draft')
    sched_count = sum(1 for d in catalog if d.get('publish_status') == 'scheduled')
    
    doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    if not doc_meta:
        return redirect(url_for('docs.docs_index'))
        
    doc_user_meta = next((d for d in user_catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    if not doc_user_meta and not is_admin:
        schedule = load_release_schedule()
        entry = schedule.get("entries", {}).get(f"{category}/{doc_slug}") or schedule.get("entries", {}).get(doc_slug, {})
        rel_date = entry.get('release_date')
        status = entry.get('status', 'draft')
        return render_template(
            'docs.html',
            active_tab='docs',
            all_docs=user_catalog,
            grouped_tree=build_grouped_tree(user_catalog),
            active_doc=doc_meta,
            doc_html=render_unreleased_notice(doc_meta.get('title'), status, rel_date),
            prev_doc=None,
            next_doc=None,
            categories=COLLECTIONS,
            projects=PROJECTS,
            topics=TOPICS,
            total_docs=len(user_catalog),
            is_landing=False,
            latest_updates=[d for d in user_catalog if d.get('slug') != '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD' and (d.get('is_latest') or d.get('order_score', 0) >= 13000)][:8],
            origin_doc=next((d for d in user_catalog if d.get('slug') == '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD'), user_catalog[0] if user_catalog else None),
            is_admin=is_admin,
            pub_count=pub_count,
            draft_count=draft_count,
            sched_count=sched_count
        )
        
    viewer_tier = 5 if is_admin else (4 if session.get('is_employer') or ('view:proprietary_docs' in session.get('permissions', [])) else 1)
    rendered_meta, html_body, prev_doc, next_doc = render_doc_content(category, doc_slug, viewer_tier)
    if rendered_meta and doc_user_meta:
        rendered_meta['publish_status'] = doc_user_meta.get('publish_status', 'published')
        rendered_meta['release_date'] = doc_user_meta.get('release_date')
        rendered_meta['is_released'] = doc_user_meta.get('is_released', True)
        
    grouped_tree = build_grouped_tree(user_catalog)
    origin_doc = next((d for d in user_catalog if d.get('slug') == '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD'), user_catalog[0] if user_catalog else None)
    latest_updates = [d for d in user_catalog if d.get('slug') != '04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD' and (d.get('is_latest') or d.get('order_score', 0) >= 13000)][:8]
    
    return render_template(
        'docs.html',
        active_tab='docs',
        all_docs=user_catalog,
        grouped_tree=grouped_tree,
        active_doc=rendered_meta or doc_meta,
        doc_html=html_body,
        prev_doc=prev_doc,
        next_doc=next_doc,
        categories=COLLECTIONS,
        projects=PROJECTS,
        topics=TOPICS,
        total_docs=len(user_catalog),
        is_landing=False,
        latest_updates=latest_updates,
        origin_doc=origin_doc,
        is_admin=is_admin,
        pub_count=pub_count,
        draft_count=draft_count,
        sched_count=sched_count
    )

# ==================== ADMIN EDITING & RELEASE CONTROLS ====================

@docs_bp.route('/api/admin/release_overview')
def docs_api_admin_release_overview():
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"status": "error", "message": "Admin authorization required."}), 403
    catalog = load_catalog()
    schedule = load_release_schedule()
    entries = schedule.get("entries", {})
    
    items = []
    pub_count = 0
    draft_count = 0
    sched_count = 0
    
    for d in catalog:
        c = d.get('category', '')
        s = d.get('slug', '')
        key = f"{c}/{s}"
        entry = entries.get(key) or entries.get(s, {})
        status = entry.get('status', d.get('publish_status', 'draft'))
        rel_date = entry.get('release_date', d.get('release_date'))
        
        if status == 'published':
            pub_count += 1
        elif status == 'scheduled':
            sched_count += 1
        else:
            draft_count += 1
            
        items.append({
            "key": key,
            "category": c,
            "slug": s,
            "title": d.get('title', s),
            "project": d.get('project', 'siraugga'),
            "project_label": d.get('project_label', 'Siraugga'),
            "collection_title": COLLECTIONS.get(c, {}).get('title', c.title()),
            "status": status,
            "release_date": rel_date,
            "word_count": d.get('word_count', 0)
        })
        
    return jsonify({
        "status": "success",
        "total": len(items),
        "pub_count": pub_count,
        "draft_count": draft_count,
        "sched_count": sched_count,
        "items": items
    })

@docs_bp.route('/api/admin/schedule', methods=['POST'])
def docs_api_admin_schedule():
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"status": "error", "message": "Admin authorization required."}), 403
    data = request.get_json() or {}
    category = data.get('category')
    slug = data.get('slug')
    status = data.get('status', 'draft')
    release_date = data.get('release_date')
    
    if not slug:
        return jsonify({"status": "error", "message": "Document slug required."}), 400
        
    schedule = load_release_schedule()
    entries = schedule.setdefault("entries", {})
    key = f"{category}/{slug}" if category else slug
    entries[key] = {
        "status": status,
        "release_date": release_date if status == "scheduled" else None,
        "updated_at": datetime.now().isoformat()
    }
    entries[slug] = entries[key]
    save_release_schedule(schedule)
    
    catalog = load_catalog()
    for d in catalog:
        if (category and d.get('category') == category and d.get('slug') == slug) or d.get('slug') == slug:
            d['publish_status'] = status
            d['release_date'] = release_date if status == "scheduled" else None
            d['is_released'] = (status == 'published')
    try:
        with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2)
    except Exception:
        pass

    pub_count = sum(1 for d in catalog if d.get('publish_status') == 'published')
    draft_count = sum(1 for d in catalog if d.get('publish_status') == 'draft')
    sched_count = sum(1 for d in catalog if d.get('publish_status') == 'scheduled')
    
    return jsonify({
        "status": "success",
        "message": f"Release status updated to {status.upper()}" + (f" for {release_date}" if status == "scheduled" else ""),
        "publish_status": status,
        "release_date": release_date,
        "published_count": pub_count,
        "draft_count": draft_count,
        "scheduled_count": sched_count
    })

@docs_bp.route('/api/admin/batch_release', methods=['POST'])
def docs_api_admin_batch_release():
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"status": "error", "message": "Admin authorization required."}), 403
    data = request.get_json() or {}
    slugs = data.get('slugs', [])
    status = data.get('status', 'published')
    category_filter = data.get('category')
    project_filter = data.get('project')
    apply_all = data.get('all', False)
    
    catalog = load_catalog()
    schedule = load_release_schedule()
    entries = schedule.setdefault("entries", {})
    now_iso = datetime.now().isoformat()
    
    updated_count = 0
    for doc in catalog:
        c = doc.get('category', '')
        s = doc.get('slug', '')
        key = f"{c}/{s}"
        
        match = False
        if slugs and (key in slugs or s in slugs):
            match = True
        elif category_filter and c == category_filter:
            match = True
        elif project_filter and doc.get('project') == project_filter:
            match = True
        elif apply_all:
            match = True
            
        if match:
            entries[key] = {
                "status": status,
                "release_date": None,
                "updated_at": now_iso
            }
            entries[s] = entries[key]
            doc['publish_status'] = status
            doc['release_date'] = None
            doc['is_released'] = (status == 'published')
            updated_count += 1
            
    save_release_schedule(schedule)
    try:
        with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2)
    except Exception:
        pass
        
    pub_count = sum(1 for d in catalog if d.get('publish_status') == 'published')
    draft_count = sum(1 for d in catalog if d.get('publish_status') == 'draft')
    sched_count = sum(1 for d in catalog if d.get('publish_status') == 'scheduled')
    
    return jsonify({
        "status": "success",
        "message": f"Updated {updated_count} chapters to {status.upper()}.",
        "updated_count": updated_count,
        "published_count": pub_count,
        "draft_count": draft_count,
        "scheduled_count": sched_count
    })

@docs_bp.route('/api/admin/save', methods=['POST'])
def docs_api_admin_save():
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"status": "error", "message": "Admin authorization required."}), 403
    data = request.get_json() or {}
    category = data.get('category')
    slug = data.get('slug')
    content = data.get('content')
    
    if not slug or content is None:
        return jsonify({"status": "error", "message": "Slug and content are required."}), 400
        
    paths = resolve_physical_file(category, slug)
    if not paths:
        target_dir = DOCS_DIR / (category or "guides")
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = [target_dir / f"{slug}.md"]
        
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        
    cleaned_text = clean_markdown_text(content)
    sanitized_text = filter_document_by_sensitivity(cleaned_text, viewer_tier=5)
    html_body = markdown.markdown(sanitized_text, extensions=['fenced_code', 'tables', 'nl2br'])
    word_count = len(content.split())
    
    return jsonify({
        "status": "success",
        "message": f"Chapter saved in-place to {len(paths)} location(s).",
        "html": html_body,
        "word_count": word_count,
        "read_time": max(1, round(word_count / 180))
    })

@docs_bp.route('/api/admin/create', methods=['POST'])
def docs_api_admin_create():
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"status": "error", "message": "Admin authorization required."}), 403
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    category = (data.get('category') or 'devlog').strip()
    project = (data.get('project') or 'siraugga').strip()
    raw_slug = (data.get('slug') or '').strip()
    content = data.get('content') or f"# {title}\n\nChapter documentation."
    status = data.get('status', 'draft')
    release_date = data.get('release_date')
    
    if not title:
        return jsonify({"status": "error", "message": "Title is required."}), 400
        
    slug = raw_slug if raw_slug else re.sub(r'[^a-zA-Z0-9_-]', '_', title).strip('_')
    if not slug:
        slug = f"chapter_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
    dest_dir = DOCS_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / f"{slug}.md"
    file_path.write_text(content, encoding='utf-8')
    
    if CENTRAL_DOCS_DIR.exists():
        proj_dir = CENTRAL_DOCS_DIR / "projects" / ("siraugga_framework" if project == "siraugga" else project)
        if proj_dir.exists():
            c_dir = proj_dir / category if (proj_dir / category).exists() else proj_dir
            try:
                (c_dir / f"{slug}.md").write_text(content, encoding='utf-8')
            except Exception:
                pass
                
    schedule = load_release_schedule()
    entries = schedule.setdefault("entries", {})
    key = f"{category}/{slug}"
    entries[key] = {
        "status": status,
        "release_date": release_date if status == "scheduled" else None,
        "updated_at": datetime.now().isoformat()
    }
    entries[slug] = entries[key]
    save_release_schedule(schedule)
    
    auto_sync_if_needed()
    
    return jsonify({
        "status": "success",
        "message": f"Chapter '{title}' created successfully.",
        "category": category,
        "slug": slug,
        "title": title
    })

@docs_bp.route('/api/admin/delete', methods=['POST'])
def docs_api_admin_delete():
    if not (session.get('admin', False) or session.get('is_admin', False)):
        return jsonify({"status": "error", "message": "Admin authorization required."}), 403
    data = request.get_json() or {}
    category = data.get('category')
    slug = data.get('slug')
    
    if not slug:
        return jsonify({"status": "error", "message": "Slug is required."}), 400
        
    paths = resolve_physical_file(category, slug)
    archive_dir = DOCS_DIR / ".archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for p in paths:
        try:
            arch_target = archive_dir / f"{p.stem}_{timestamp}{p.suffix}"
            p.rename(arch_target)
        except Exception as e:
            print(f"[DocsMod] Error archiving {p}: {e}")
            
    schedule = load_release_schedule()
    entries = schedule.get("entries", {})
    entries.pop(f"{category}/{slug}", None)
    entries.pop(slug, None)
    save_release_schedule(schedule)
    
    auto_sync_if_needed()
    
    return jsonify({
        "status": "success",
        "message": f"Chapter '{slug}' archived successfully."
    })

@docs_bp.route('/api/search')
def docs_search():
    query = request.args.get('q', '').strip().lower()
    project_filter = request.args.get('project', 'all').lower()
    topic_filter = request.args.get('topic', 'all').lower()
    
    if not query:
        return jsonify([])
        
    is_admin = session.get('admin', False) or session.get('is_admin', False)
    catalog = load_catalog()
    user_catalog = get_user_catalog(catalog, is_admin=is_admin)
    results = []
    
    for item in user_catalog:
        if project_filter != 'all' and item.get('project') != project_filter:
            continue
        if topic_filter != 'all' and topic_filter not in item.get('topics', []):
            continue
            
        title = item.get('title', '').lower()
        slug = item.get('slug', '').lower()
        summary = item.get('summary', '').lower()
        cat = item.get('category', '').lower()
        p_label = item.get('project_label', '').lower()
        
        score = 0
        if query in title:
            score += 15
        if query in slug:
            score += 8
        if query in summary:
            score += 4
        if query in cat:
            score += 2
        if query in p_label:
            score += 3
            
        if score > 0:
            results.append({
                "title": item.get('title'),
                "category": item.get('category'),
                "project": item.get('project_label', 'Siraugga Core'),
                "url": f"/docs/{item.get('category')}/{item.get('slug')}",
                "summary": item.get('summary'),
                "words": item.get('word_count'),
                "score": score + (item.get('order_score', 0) / 1000)
            })
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(results[:30])
