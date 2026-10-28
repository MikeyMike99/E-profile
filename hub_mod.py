"""Shim for backwards compatibility with legacy hub references.
Redirects and aliases are managed in newsletter_mod.
"""
from newsletter_mod import (
    newsletter_bp,
    hub_bp,
    purge_temp_docs_cache,
    get_disk_cached_doc,
    save_disk_cached_doc,
    load_active_manifest,
    save_active_manifest,
)
