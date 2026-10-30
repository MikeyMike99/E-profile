#!/usr/bin/env python3
"""
doc_versioner.py - Canonical Documentation Tagging & Versioning Engine
========================================================================
Provides automated, consistent, and idempotent version control for technical
documentation across all DevCore, Siraugga, and E-Profile repositories.

Key Principles:
1. Invariant Identity: DOC_ID never changes, preserving cross-references forever.
2. Independent Versioning: VERSION increments (v1.0 -> v1.1) when content evolves.
3. Pure Markdown Comments: Tags use CommonMark link reference definitions
   [//]: # (DOC_ID: ... | VERSION: ... | SCOPE: ...) which are 100% invisible
   in rendered HTML and screen reader streams.
4. Deterministic Section Anchoring: Every H2/H3 gets a persistent SECTION_ID.
"""

import os
import sys
import re
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Project Code Registry
PROJECT_CODES = {
    "siraugga": "SIRA",
    "devcore": "SIRA",
    "siraugga_framework": "SIRA",
    "echoes": "ECHO",
    "echoes_of_the_world": "ECHO",
    "eprofile": "EPRF",
    "e_profile": "EPRF",
    "encrypt_me": "ENCR",
    "encryptme": "ENCR",
    "audio_suite": "JOSH",
    "audio_playback_suite": "JOSH",
    "audio_pllayback_suite": "JOSH",
    "accessible_apps": "ACCS",
}

# Collection Code Registry
COLLECTION_CODES = {
    "manifesto": "MAN",
    "devlog": "DEV",
    "textbook": "TXT",
    "manual": "OPS",
    "guides": "ARCH",
    "echoes": "CORE",
    "eprofile": "PORT",
    "encrypt_me": "VAULT",
    "story": "DEV",
    "audio_suite": "PLAY",
    "bashbootrc": "BASH",
    "bashrc": "BASH",
    "reference": "REF",
}

RE_DOC_HEADER = re.compile(
    r'^\s*\[//\]:\s*#\s*\(\s*DOC_ID:\s*([A-Z0-9_\-]+)\s*\|\s*VERSION:\s*(v?\d+\.\d+)(?:\s*\|\s*SCOPE:\s*([^)]+))?\s*\)',
    re.MULTILINE
)
RE_SECTION_TAG = re.compile(
    r'^\s*\[//\]:\s*#\s*\(\s*SECTION_ID:\s*([A-Z0-9_\-]+)\s*\)',
    re.MULTILINE
)
RE_HEADING = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)


def detect_project_and_collection(file_path: Path) -> Tuple[str, str]:
    """Infers project code and collection code based on path semantics."""
    path_str = str(file_path).replace("\\", "/")
    
    # Project inference
    proj_code = "SIRA"
    for key, code in PROJECT_CODES.items():
        if f"/{key}/" in path_str.lower() or f"/{key}" in path_str.lower():
            proj_code = code
            break

    # Specific file overrides
    filename = file_path.name.upper()
    if "ECHOES" in filename or "CLASS_WORLD" in filename or "MENU_CONFIG" in filename:
        proj_code = "ECHO"
    elif "ENCRYPT" in filename or "CRYPTOGRAPHIC" in filename:
        proj_code = "ENCR"
    elif "AUDIO" in filename or "JOSHY" in filename or "NVDA" in filename:
        proj_code = "JOSH"

    # Collection inference
    coll_code = "DEV"
    for key, code in COLLECTION_CODES.items():
        if f"/{key}/" in path_str.lower():
            coll_code = code
            break
            
    if "manifesto" in path_str.lower():
        coll_code = "MAN"
    elif "textbook" in path_str.lower():
        coll_code = "TXT"
    elif "manual" in path_str.lower():
        coll_code = "OPS"
    elif "guides" in path_str.lower():
        coll_code = "ARCH"

    return proj_code, coll_code


def compute_canonical_doc_id(file_path: Path) -> str:
    """Generates an invariant canonical DOC_ID for a file."""
    proj, coll = detect_project_and_collection(file_path)
    stem = file_path.stem.upper()
    
    # Sub-suite distinction (e.g. bashrc vs bashbootrc)
    sub = ""
    if "BASHBOOTRC" in str(file_path).upper():
        sub = "BOOT_"
    elif "BASHRC" in str(file_path).upper():
        sub = "ENV_"

    # Clean stem numbers
    m_num = re.match(r'^(\d+)_(\d+)', stem)
    if m_num:
        clean_slug = f"{sub}{m_num.group(1)}_{m_num.group(2)}"
    elif re.match(r'^CHAPTER_(\d+)', stem):
        clean_slug = f"CH_{re.match(r'^CHAPTER_(\d+)', stem).group(1)}"
    elif re.match(r'^MODULE_(\d+)', stem):
        mod_num = re.match(r'^MODULE_(\d+)', stem).group(1)
        if "CHECKPOINT" in stem:
            clean_slug = f"MOD_{mod_num}_CHK"
        elif "SUMMARY" in stem:
            clean_slug = f"MOD_{mod_num}_SUM"
        else:
            clean_slug = f"MOD_{mod_num}"
    elif stem.startswith("00A"):
        clean_slug = f"{sub}00A"
    elif stem.startswith("00B"):
        clean_slug = f"{sub}00B"
    elif stem.startswith("00_README"):
        clean_slug = f"{sub}INDEX"
    else:
        suffix = "_CLN" if "CLEAN" in stem else ""
        base = re.sub(r'[^A-Z0-9]+', '_', stem.replace("_CLEAN", ""))[:18].strip('_')
        clean_slug = f"{base}{suffix}"
        
    return f"{proj}-{coll}-{clean_slug}"


def parse_metadata(content: str) -> Optional[Dict[str, str]]:
    """Extracts existing DOC_ID, VERSION, and SCOPE from content."""
    m = RE_DOC_HEADER.search(content)
    if m:
        return {
            "doc_id": m.group(1),
            "version": m.group(2) if m.group(2).startswith('v') else f"v{m.group(2)}",
            "scope": (m.group(3) or "GENERAL").strip()
        }
    return None


def increment_version(version_str: str, bump_type: str = "minor") -> str:
    """Bumps version: minor (v1.0 -> v1.1) or major (v1.x -> v2.0)."""
    raw = version_str.lstrip("v")
    parts = raw.split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 1
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    
    if bump_type == "major":
        return f"v{major + 1}.0"
    return f"v{major}.{minor + 1}"


def update_file_metadata(file_path: Path, bump_type: Optional[str] = None, force_id: Optional[str] = None, recompute_id: bool = False) -> bool:
    """
    Ensures file has valid DOC_ID, updates VERSION if requested,
    and guarantees all H2/H3 headings have preceding SECTION_ID comments.
    """
    if not file_path.exists() or file_path.suffix.lower() != ".md":
        return False
        
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return False

    meta = parse_metadata(content)
    lines = content.splitlines()
    modified = False

    # 1. Establish or update header
    if meta and not recompute_id:
        doc_id = force_id or meta["doc_id"]
        version = meta["version"]
        scope = meta["scope"]
        
        if bump_type:
            version = increment_version(version, bump_type)
            modified = True
            
        header_line = f"[//]: # (DOC_ID: {doc_id} | VERSION: {version} | SCOPE: {scope})"
        # Replace first line if it's the header
        if lines and RE_DOC_HEADER.match(lines[0]):
            if lines[0] != header_line:
                lines[0] = header_line
                modified = True
        else:
            lines.insert(0, header_line)
            modified = True
    else:
        # Generate or recompute header
        doc_id = force_id or compute_canonical_doc_id(file_path)
        version = meta["version"] if meta else "v1.0"
        if bump_type and meta:
            version = increment_version(version, bump_type)
        _, coll = detect_project_and_collection(file_path)
        scope = coll
        header_line = f"[//]: # (DOC_ID: {doc_id} | VERSION: {version} | SCOPE: {scope})"
        if lines and RE_DOC_HEADER.match(lines[0]):
            if lines[0] != header_line:
                lines[0] = header_line
                modified = True
        else:
            lines.insert(0, header_line)
            modified = True

    # 2. Tag H2 and H3 Headings with SECTION_ID comments
    new_lines = []
    sec_idx = 1
    i = 0
    while i < len(lines):
        line = lines[i]
        h_match = re.match(r'^(#{2,3})\s+(.+)$', line)
        if h_match:
            heading_title = h_match.group(2).strip()
            # Try to derive section number from heading text (e.g. "1. Overview" -> "1", "1.2 Details" -> "1_2")
            num_m = re.match(r'^(\d+(?:\.\d+)*)\.?\s+(.+)$', heading_title)
            sec_num = num_m.group(1).replace('.', '_') if num_m else str(sec_idx)
            if not num_m:
                sec_idx += 1
                
            sec_id = f"{doc_id}-SEC-{sec_num}"
            expected_sec_comment = f"[//]: # (SECTION_ID: {sec_id})"
            
            # Check if previous non-blank line is already a SECTION_ID comment
            prev_idx = len(new_lines) - 1
            while prev_idx >= 0 and not new_lines[prev_idx].strip():
                prev_idx -= 1
                
            has_tag = False
            if prev_idx >= 0 and RE_SECTION_TAG.match(new_lines[prev_idx]):
                has_tag = True
                if new_lines[prev_idx] != expected_sec_comment:
                    new_lines[prev_idx] = expected_sec_comment
                    modified = True
                    
            if not has_tag:
                new_lines.append(expected_sec_comment)
                modified = True
                
        new_lines.append(line)
        i += 1

    if modified:
        new_content = "\n".join(new_lines).strip() + "\n"
        file_path.write_text(new_content, encoding="utf-8")
        print(f"[UPDATED] {file_path.name} -> {doc_id} ({version})")
        return True
    else:
        print(f"[UNTOUCHED] {file_path.name} (Already compliant)")
        return False


def check_directory(dir_path: Path) -> Dict[str, any]:
    """Audits directory of markdown files for tagging and versioning compliance."""
    stats = {
        "total_files": 0,
        "tagged_files": 0,
        "missing_header": [],
        "id_collisions": {},
        "ids_seen": {}
    }
    
    for p in dir_path.rglob("*.md"):
        if any(ignored in str(p) for ignored in [".git", "node_modules", "venv", ".system_generated", "scratch"]):
            continue
            
        stats["total_files"] += 1
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
            
        meta = parse_metadata(content)
        if meta:
            stats["tagged_files"] += 1
            doc_id = meta["doc_id"]
            if doc_id in stats["ids_seen"]:
                if doc_id not in stats["id_collisions"]:
                    stats["id_collisions"][doc_id] = [stats["ids_seen"][doc_id]]
                stats["id_collisions"][doc_id].append(str(p))
            else:
                stats["ids_seen"][doc_id] = str(p)
        else:
            stats["missing_header"].append(str(p))
            
    return stats


def get_git_changed_docs(repo_root: Path) -> List[Path]:
    """Finds all modified/added markdown files in git repository."""
    changed = []
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True, text=True, check=True
        )
        for line in res.stdout.splitlines():
            status = line[:2]
            filename = line[3:].strip()
            if filename.endswith(".md"):
                p = repo_root / filename
                if p.exists():
                    changed.append(p)
    except Exception as e:
        print(f"[WARN] Git status query failed on {repo_root}: {e}")
    return changed


def main():
    parser = argparse.ArgumentParser(description="Canonical Documentation Tagging & Versioning CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check
    check_p = subparsers.add_parser("check", help="Audit markdown files for metadata compliance")
    check_p.add_argument("path", type=str, nargs="?", default=".", help="Root folder to audit")

    # Bump single file or glob
    bump_p = subparsers.add_parser("bump", help="Bump version and ensure section tags for target files")
    bump_p.add_argument("path", type=str, help="Target markdown file or directory")
    bump_p.add_argument("--major", action="store_true", help="Bump major version (v1.x -> v2.0)")

    # Bump changed files via git
    bump_c = subparsers.add_parser("bump-changed", help="Automatically bump version for git-modified docs")
    bump_c.add_argument("repo", type=str, nargs="?", default=".", help="Git repository root")
    bump_c.add_argument("--major", action="store_true", help="Bump major version instead of minor")

    # Tag all
    tag_p = subparsers.add_parser("tag-all", help="Apply tags and section IDs across all files in directory")
    tag_p.add_argument("path", type=str, help="Root folder to tag")
    tag_p.add_argument("--recompute-id", action="store_true", help="Recompute canonical IDs to resolve collisions")

    args = parser.parse_args()

    if args.command == "check":
        p = Path(args.path).resolve()
        print(f"[*] Auditing documentation metadata in: {p}")
        stats = check_directory(p)
        print(f"Total Markdown Files : {stats['total_files']}")
        print(f"Tagged & Versioned   : {stats['tagged_files']}")
        print(f"Missing Metadata     : {len(stats['missing_header'])}")
        print(f"ID Collisions        : {len(stats['id_collisions'])}")
        if stats["id_collisions"]:
            print("\n[!] Collisions detected:")
            for cid, paths in stats["id_collisions"].items():
                print(f"  - {cid}:")
                for item in paths:
                    print(f"      {item}")
        if stats["missing_header"]:
            print("\n[!] Files missing metadata header:")
            for item in stats["missing_header"][:15]:
                print(f"  - {item}")
            if len(stats["missing_header"]) > 15:
                print(f"    ... and {len(stats['missing_header']) - 15} more.")

    elif args.command == "bump":
        target = Path(args.path).resolve()
        bump_type = "major" if args.major else "minor"
        if target.is_file():
            update_file_metadata(target, bump_type=bump_type)
        elif target.is_dir():
            for f in target.rglob("*.md"):
                update_file_metadata(f, bump_type=bump_type)

    elif args.command == "bump-changed":
        repo = Path(args.repo).resolve()
        changed = get_git_changed_docs(repo)
        bump_type = "major" if args.major else "minor"
        print(f"[*] Found {len(changed)} changed markdown files in git.")
        for f in changed:
            update_file_metadata(f, bump_type=bump_type)

    elif args.command == "tag-all":
        p = Path(args.path).resolve()
        count = 0
        for f in p.rglob("*.md"):
            if any(ignored in str(f) for ignored in [".git", "node_modules", "venv", ".system_generated", "scratch"]):
                continue
            if update_file_metadata(f, recompute_id=args.recompute_id):
                count += 1
        print(f"[+] Finished. Updated {count} files.")


if __name__ == "__main__":
    main()
