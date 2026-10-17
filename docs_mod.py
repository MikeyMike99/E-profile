import os
import json
from pathlib import Path
from flask import Blueprint, render_template, abort, request, jsonify, redirect, url_for, session
import markdown
from config import Config
from sensitivity_engine import filter_document_by_sensitivity, compute_document_sensitivity

config = Config()
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

DOCS_DIR = config.CONTENT_DIR / "docs"
CATALOG_PATH = DOCS_DIR / "docs_catalog.json"
CENTRAL_DOCS_DIR = getattr(config, 'CENTRAL_DOCS_DIR', Path("/mnt/c/Users/michael/Documents/Central_Docs"))
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

def get_prev_next(catalog, category, slug):
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
    """
    Cleans up raw path link text, normalizes markdown headers,
    and formats ugly relative paths into readable document labels.
    """
    text = raw_text
    import re
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

    # Check if document is purely classified (base_sensitivity == 5)
    base_sens = doc_meta.get('base_sensitivity', 1) if doc_meta else 1
    if base_sens >= 5 and viewer_tier < 5:
        return doc_meta, "__LOCKED__", prev_doc, next_doc

    file_path = None
    if CENTRAL_DOCS_DIR.exists():
        candidates = []
        if doc_meta.get('rel_path'):
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
                file_path = c
                break

    if not file_path or not file_path.exists():
        if doc_meta.get('rel_path'):
            file_path = DOCS_DIR / doc_meta.get('rel_path', '')
        if not file_path or not file_path.exists():
            candidate = DOCS_DIR / category / f"{doc_slug}.md"
            if candidate.exists():
                file_path = candidate
            else:
                return None, None, None, None

    try:
        raw_text = file_path.read_text(encoding='utf-8', errors='replace')
        cleaned_text = clean_markdown_text(raw_text)
        sanitized_text = filter_document_by_sensitivity(cleaned_text, viewer_tier=viewer_tier)
        html_body = markdown.markdown(sanitized_text, extensions=['fenced_code', 'tables', 'nl2br'])
    except Exception as e:
        html_body = f"<p>Error rendering document: {e}</p>"

    return doc_meta, html_body, prev_doc, next_doc

def build_grouped_tree(catalog):
    """
    Groups catalog into a hierarchical structure: Project -> Collection -> Documents.
    Guarantees that readers always see which project each document belongs to.
    """
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
    viewer_tier = 5 if session.get('admin') else (4 if session.get('is_employer') or ('view:proprietary_docs' in session.get('permissions', [])) else 1)
    doc_meta, html_body, prev_doc, next_doc = render_doc_content(category, doc_slug, viewer_tier)
    if not doc_meta or html_body is None:
        return jsonify({"status": "error", "message": "Chapter not found"}), 404
        
    c_info = COLLECTIONS.get(category, {})
    p_key = doc_meta.get('project', 'siraugga')
    p_info = PROJECTS.get(p_key, {})

    return jsonify({
        "status": "success",
        "slug": doc_meta.get('slug'),
        "category": doc_meta.get('category'),
        "title": doc_meta.get('title'),
        "project": p_key,
        "project_label": doc_meta.get('project_label', p_info.get('title', 'Siraugga Framework')),
        "project_icon": p_info.get('icon', '⚡'),
        "project_desc": p_info.get('desc', ''),
        "collection_title": c_info.get('title', category.title()),
        "collection_desc": c_info.get('desc', ''),
        "collection_icon": c_info.get('icon', '📄'),
        "hierarchy_path": f"{p_info.get('title', 'Siraugga Framework')} → {c_info.get('title', category.title())} → {doc_meta.get('title')}",
        "summary": doc_meta.get('summary', ''),
        "word_count": doc_meta.get('word_count', 0),
        "read_time": max(1, round(doc_meta.get('word_count', 0) / 180)),
        "base_sensitivity": doc_meta.get('base_sensitivity', 1),
        "max_sensitivity": doc_meta.get('max_sensitivity', 1),
        "is_proprietary": doc_meta.get('is_proprietary', False),
        "cross_references": doc_meta.get('cross_references', []),
        "html": html_body,
        "prev_doc": prev_doc,
        "next_doc": next_doc
    })

@docs_bp.route('/', strict_slashes=False)
@docs_bp.route('', strict_slashes=False)
def docs_index():
    catalog = load_catalog()
    if not catalog:
        return render_template('docs.html', active_tab='docs', all_docs=[], grouped_tree=[], total_docs=0)
        
    active_slug = request.args.get('slug')
    active_cat = request.args.get('category')
    
    active_doc = None
    if active_slug and active_cat:
        active_doc = next((d for d in catalog if d.get('slug') == active_slug and d.get('category') == active_cat), None)
    if not active_doc:
        active_doc = next((d for d in catalog if d.get('is_latest')), catalog[0])
        
    viewer_tier = 5 if session.get('admin') else (4 if session.get('is_employer') or ('view:proprietary_docs' in session.get('permissions', [])) else 1)
    doc_meta, html_body, prev_doc, next_doc = render_doc_content(active_doc.get('category'), active_doc.get('slug'), viewer_tier)
    grouped_tree = build_grouped_tree(catalog)

    return render_template(
        'docs.html',
        active_tab='docs',
        all_docs=catalog,
        grouped_tree=grouped_tree,
        active_doc=doc_meta or active_doc,
        doc_html=html_body,
        prev_doc=prev_doc,
        next_doc=next_doc,
        categories=COLLECTIONS,
        projects=PROJECTS,
        topics=TOPICS,
        total_docs=len(catalog)
    )

@docs_bp.route('/<category>')
def docs_category(category):
    if category not in COLLECTIONS:
        return redirect(url_for('docs.docs_index'))
    catalog = load_catalog()
    cat_docs = [d for d in catalog if d.get('category') == category]
    active_doc = cat_docs[0] if cat_docs else (catalog[0] if catalog else None)
    if not active_doc:
        return redirect(url_for('docs.docs_index'))
    return redirect(url_for('docs.docs_reader', category=active_doc.get('category'), doc_slug=active_doc.get('slug')))

@docs_bp.route('/<category>/<doc_slug>')
def docs_reader(category, doc_slug):
    catalog = load_catalog()
    doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    if not doc_meta:
        return redirect(url_for('docs.docs_index'))
        
    viewer_tier = 5 if session.get('admin') else (4 if session.get('is_employer') or ('view:proprietary_docs' in session.get('permissions', [])) else 1)
    doc_meta, html_body, prev_doc, next_doc = render_doc_content(category, doc_slug, viewer_tier)
    grouped_tree = build_grouped_tree(catalog)
    
    return render_template(
        'docs.html',
        active_tab='docs',
        all_docs=catalog,
        grouped_tree=grouped_tree,
        active_doc=doc_meta or {"title": doc_slug.replace('_', ' '), "slug": doc_slug, "category": category},
        doc_html=html_body,
        prev_doc=prev_doc,
        next_doc=next_doc,
        categories=COLLECTIONS,
        projects=PROJECTS,
        topics=TOPICS,
        total_docs=len(catalog)
    )


@docs_bp.route('/api/search')
def docs_search():
    query = request.args.get('q', '').strip().lower()
    project_filter = request.args.get('project', 'all').lower()
    topic_filter = request.args.get('topic', 'all').lower()
    
    if not query:
        return jsonify([])
        
    catalog = load_catalog()
    results = []
    
    for item in catalog:
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
