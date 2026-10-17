import os
import json
from pathlib import Path
from flask import Blueprint, render_template, abort, request, jsonify, redirect, url_for
import markdown
from config import Config

config = Config()
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

DOCS_DIR = config.CONTENT_DIR / "docs"
CATALOG_PATH = DOCS_DIR / "docs_catalog.json"

CATEGORIES = {
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
    "guides": {
        "title": "Architecture & System Guides",
        "badge": "Specifications",
        "icon": "📐",
        "desc": "Core system specifications, security policies, hot-patch architecture, and MCP protocol documentation."
    }
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

@docs_bp.route('/')
def docs_index():
    catalog = load_catalog()
    
    # Calculate category counts
    counts = {}
    for item in catalog:
        cat = item.get('category')
        counts[cat] = counts.get(cat, 0) + 1
        
    return render_template(
        'docs.html',
        active_tab='docs',
        view_mode='index',
        categories=CATEGORIES,
        counts=counts,
        total_docs=len(catalog),
        recent_docs=catalog[:10],
        catalog=catalog
    )

@docs_bp.route('/<category>')
def docs_category(category):
    if category not in CATEGORIES:
        return redirect(url_for('docs.docs_index'))
        
    catalog = load_catalog()
    cat_docs = [d for d in catalog if d.get('category') == category]
    
    return render_template(
        'docs.html',
        active_tab='docs',
        view_mode='category',
        category_key=category,
        category_meta=CATEGORIES[category],
        docs=cat_docs,
        categories=CATEGORIES,
        catalog=catalog
    )

@docs_bp.route('/<category>/<doc_slug>')
def docs_reader(category, doc_slug):
    catalog = load_catalog()
    doc_meta = next((d for d in catalog if d.get('category') == category and d.get('slug') == doc_slug), None)
    
    # Locate file
    file_path = None
    if doc_meta:
        file_path = DOCS_DIR / doc_meta.get('rel_path', '')
    if not file_path or not file_path.exists():
        # Fallback search
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
        
    prev_doc, next_doc = get_prev_next(catalog, category, doc_slug)
    category_meta = CATEGORIES.get(category, {"title": category.title(), "icon": "📄"})
    
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
        categories=CATEGORIES,
        catalog=catalog
    )

@docs_bp.route('/api/search')
def docs_search():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
        
    catalog = load_catalog()
    results = []
    
    for item in catalog:
        title = item.get('title', '').lower()
        slug = item.get('slug', '').lower()
        summary = item.get('summary', '').lower()
        cat = item.get('category', '').lower()
        
        score = 0
        if query in title:
            score += 10
        if query in slug:
            score += 5
        if query in summary:
            score += 2
        if query in cat:
            score += 1
            
        if score > 0:
            results.append({
                "title": item.get('title'),
                "category": item.get('category'),
                "url": f"/docs/{item.get('category')}/{item.get('slug')}",
                "summary": item.get('summary'),
                "words": item.get('word_count'),
                "score": score
            })
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(results[:25])
