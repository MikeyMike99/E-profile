import os
import json
from pathlib import Path
from flask import Blueprint, render_template, abort, request, jsonify, redirect, url_for, session
import markdown
from config import Config

config = Config()
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

DOCS_DIR = config.CONTENT_DIR / "docs"
CATALOG_PATH = DOCS_DIR / "docs_catalog.json"

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
    }
}

PROJECTS = {
    "all": {"title": "All Projects", "icon": "🌐"},
    "audio_suite": {"title": "JOSHY Audio Suite", "icon": "🎵"},
    "siraugga": {"title": "Siraugga / DevCore Core", "icon": "⚡"},
    "echoes": {"title": "Echoes of the World", "icon": "🎮"},
    "accessible_apps": {"title": "Accessible Tools Suite", "icon": "♿"},
    "eprofile": {"title": "E-Profile Portal", "icon": "💼"}
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

def load_catalog():
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

@docs_bp.route('/', strict_slashes=False)
@docs_bp.route('', strict_slashes=False)
def docs_index():
    catalog = load_catalog()
    
    # Selected filters from query string
    selected_project = request.args.get('project', 'all').lower()
    selected_topic = request.args.get('topic', 'all').lower()
    selected_collection = request.args.get('category', 'all').lower()
    selected_clearance = request.args.get('clearance', 'all').lower()
    sort_mode = request.args.get('sort', 'newest').lower()
    
    # Compute counts dynamically across all dimensions
    project_counts = {"all": len(catalog)}
    topic_counts = {"all": len(catalog)}
    collection_counts = {"all": len(catalog)}
    clearance_counts = {
        "all": len(catalog),
        "public": len([d for d in catalog if not d.get('is_proprietary', False)]),
        "proprietary": len([d for d in catalog if d.get('is_proprietary', False)])
    }
    
    for item in catalog:
        # Project counts
        p = item.get('project', 'siraugga')
        project_counts[p] = project_counts.get(p, 0) + 1
        
        # Collection counts
        c = item.get('category', 'devlog')
        collection_counts[c] = collection_counts.get(c, 0) + 1
        
        # Topic counts
        for t in item.get('topics', []):
            topic_counts[t] = topic_counts.get(t, 0) + 1

    # Filter items based on user selection
    filtered_docs = list(catalog)
    if selected_project != 'all':
        filtered_docs = [d for d in filtered_docs if d.get('project') == selected_project]
    if selected_topic != 'all':
        filtered_docs = [d for d in filtered_docs if selected_topic in d.get('topics', [])]
    if selected_collection != 'all':
        filtered_docs = [d for d in filtered_docs if d.get('category') == selected_collection]
    if selected_clearance == 'public':
        filtered_docs = [d for d in filtered_docs if not d.get('is_proprietary', False)]
    elif selected_clearance == 'proprietary':
        filtered_docs = [d for d in filtered_docs if d.get('is_proprietary', False)]
        
    # Sort mode: newest first (order_score desc) vs alphabetical
    if sort_mode == 'alpha':
        filtered_docs.sort(key=lambda x: x.get('title', '').lower())
    else:
        filtered_docs.sort(key=lambda x: x.get('order_score', 0), reverse=True)

    # Latest flagship update for the interactive top bar
    latest_doc = next((d for d in catalog if d.get('is_latest')), catalog[0] if catalog else None)

    return render_template(
        'docs.html',
        active_tab='docs',
        view_mode='index',
        categories=COLLECTIONS,
        projects=PROJECTS,
        topics=TOPICS,
        project_counts=project_counts,
        topic_counts=topic_counts,
        collection_counts=collection_counts,
        clearance_counts=clearance_counts,
        selected_project=selected_project,
        selected_topic=selected_topic,
        selected_collection=selected_collection,
        selected_clearance=selected_clearance,
        sort_mode=sort_mode,
        latest_doc=latest_doc,
        docs=filtered_docs,
        total_docs=len(catalog),
        filtered_count=len(filtered_docs)
    )

@docs_bp.route('/<category>')
def docs_category(category):
    if category not in COLLECTIONS:
        return redirect(url_for('docs.docs_index'))
    return redirect(url_for('docs.docs_index', category=category))

@docs_bp.route('/<category>/<doc_slug>')
def docs_reader(category, doc_slug):
    catalog = load_catalog()
    doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    
    # Check permissions & authorization
    is_authorized = session.get('admin', False) or session.get('is_employer', False) or ('view:proprietary_docs' in session.get('permissions', []))
    is_proprietary = doc_meta.get('is_proprietary', False) if doc_meta else False
    
    prev_doc, next_doc = get_prev_next(catalog, category, doc_slug)
    category_meta = COLLECTIONS.get(category, {"title": category.title(), "icon": "📄"})
    
    # CRITICAL SECURITY GATE: Block unauthenticated access to proprietary documents
    if is_proprietary and not is_authorized:
        return render_template(
            'docs.html',
            active_tab='docs',
            view_mode='locked',
            doc=doc_meta or {"title": doc_slug.replace('_', ' '), "slug": doc_slug, "category": category, "is_proprietary": True},
            category_key=category,
            category_meta=category_meta,
            prev_doc=prev_doc,
            next_doc=next_doc,
            categories=COLLECTIONS,
            projects=PROJECTS,
            topics=TOPICS
        )

    # Locate file
    file_path = None
    if doc_meta:
        file_path = DOCS_DIR / doc_meta.get('rel_path', '')
    if not file_path or not file_path.exists():
        candidate = DOCS_DIR / category / f"{doc_slug}.md"
        if candidate.exists():
            file_path = candidate
        else:
            abort(404)
            
    try:
        raw_text = file_path.read_text(encoding='utf-8', errors='replace')
        html_body = markdown.markdown(raw_text, extensions=['fenced_code', 'tables', 'nl2br'])
    except Exception as e:
        html_body = f"<p>Error rendering document: {e}</p>"
        
    return render_template(
        'docs.html',
        active_tab='docs',
        view_mode='reader',
        doc=doc_meta or {"title": doc_slug.replace('_', ' '), "slug": doc_slug, "category": category},
        doc_html=html_body,
        category_key=category,
        category_meta=category_meta,
        prev_doc=prev_doc,
        next_doc=next_doc,
        categories=COLLECTIONS,
        projects=PROJECTS,
        topics=TOPICS
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
