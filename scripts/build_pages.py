"""Build the static half of e-profile for Cloudflare Pages.

Renders every public page as an anonymous visitor through Flask's test client,
following internal links, and writes ONLY rendered HTML + static/ + robots.txt
into cloudflare_pages/public/. Nothing else from this directory (.env, .ssh,
tokens, profiles.json, ...) can end up in the upload.

Everything that needs a session or server logic (login, admin, api, gated tabs,
downloads) is routed by cloudflare_pages/public/_routes.json to the Pages
Function in cloudflare_pages/functions/, which proxies it to the local server.

Usage:  python scripts/build_pages.py
Deploy: cd cloudflare_pages && npx wrangler pages deploy public --project-name eprofile
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cloudflare_pages" / "public"

# Public pages that render the same for every anonymous visitor.
SEEDS = ["/", "/bio", "/docs", "/newsletter", "/downloads", "/usage", "/terms", "/echos-calibrator/"]
STATIC_PAGE = re.compile(
    r"^/(bio|docs|newsletter|downloads|usage|terms)?$"
    r"|^/docs/(?!api/)[^/]+/[^/]+$"
    r"|^/newsletter/story/[^/]+$"
    r"|^/echos-calibrator/$"
)
# Prefixes always handled by the local server (Pages Function proxy).
DYNAMIC = [
    "/login", "/logout", "/admin", "/admin/*", "/admin_impersonate/*", "/access/*",
    "/api/*", "/ai_agent/*", "/docs/api/*", "/downloads/get/*",
    "/newsletter/preferences", "/newsletter/preferences/*", "/newsletter/download/*",
    "/newsletter/unsubscribe*", "/newsletter/r/*", "/subscribe", "/blog", "/blog/*",
    # Fresh-first: live from DevCore when up, static snapshot otherwise.
    "/newsletter", "/newsletter/story/*", "/projects", "/projects/*",
    "/certifications", "/certifications/*", "/quarantine/*", "/delete_profile",
    "/edit_profile", "/reset_pin", "/change_password", "/hub", "/hub/*",
    "/echos/*", "/vault/*", "/notify/*", "/diagnostics/*", "/sync/*",
]
LINK_RE = re.compile(r"""(?:href|src|action)=["'](/[^"'#?]*)""")


def out_path(url_path: str) -> Path:
    if url_path == "/":
        return OUT / "index.html"
    # bio.html is served at /bio by Pages, matching the Flask URLs exactly.
    return OUT / f"{url_path.strip('/')}.html"


def main() -> int:
    os.environ.setdefault("SECRET_KEY", "static-build-only")
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from server import app  # noqa: E402

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    client = app.test_client()
    queue, seen, failed = list(SEEDS), set(), []
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        resp = client.get(path)
        if resp.status_code != 200 or not resp.mimetype.startswith("text/html"):
            failed.append((path, resp.status_code))
            continue
        html = resp.get_data(as_text=True)
        # Absolute links to the build host would break on Pages.
        html = re.sub(r"https?://localhost(:\d+)?", "", html)
        dest = out_path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        for link in LINK_RE.findall(html):
            link = urlparse(link).path.rstrip("/") or "/"
            if STATIC_PAGE.match(link) and link not in seen:
                queue.append(link)

    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / "robots.txt").write_text(client.get("/robots.txt").get_data(as_text=True))
    (OUT / "_redirects").write_text("/home / 301\n")
    # Hand-written page (private Mesh access: install the client / open Siraugga).
    shutil.copyfile(ROOT / "cloudflare_pages" / "mesh.html", OUT / "mesh.html")
    # A 404.html stops Pages' SPA fallback (serving home for every unknown path).
    (OUT / "404.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Page not found</title><body style="font-family:system-ui;'
        'max-width:36rem;margin:15vh auto;padding:0 16px"><h1>Page not found</h1>'
        '<p><a href="/">Back to home</a></p></body></html>', encoding="utf-8")
    # The Pages Function sees every request except static assets; it serves the snapshot
    # itself when it can (see cloudflare_pages/functions/[[path]].js). DYNAMIC documents
    # which paths are always live.
    (OUT / "_routes.json").write_text(json.dumps(
        {"version": 1, "include": ["/*"], "exclude": ["/static/*", "/robots.txt"]}, indent=2))

    pages = sorted(seen - {p for p, _ in failed})
    print(f"rendered {len(pages)} pages -> {OUT}")
    for p, code in failed:
        print(f"  skipped {p} ({code})")
    leaked = [f for f in OUT.rglob("*") if f.name.startswith(".") or f.suffix in {".py", ".env", ".json"} and f.name != "_routes.json"]
    if leaked:
        print("ABORT: unexpected files in output:", leaked)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
