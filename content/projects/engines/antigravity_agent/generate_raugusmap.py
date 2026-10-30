import os
import json
import uuid
import ast
import hashlib
import re

def extract_file_ast_symbols(filepath):
    """
    Parses Python file and returns a structured dictionary of symbols:
    {
        symbol_key_suffix: {
            "type": "function" | "async_function" | "class" | "method" | "async_method" | "variable",
            "symbol_name": str,
            "class_name": str | None,
            "start_line": int,
            "end_line": int,
            "content_hash": str
        }
    }
    """
    results = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        source = "".join(lines)
        tree = ast.parse(source)

        def _hash(s_line, e_line):
            snip = "".join(lines[max(0, s_line - 1): e_line])
            return hashlib.sha256(snip.encode('utf-8')).hexdigest()[:12]

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                e_line = getattr(node, 'end_lineno', node.lineno)
                results[node.name] = {
                    "type": "function",
                    "symbol_name": node.name,
                    "class_name": None,
                    "start_line": node.lineno,
                    "end_line": e_line,
                    "content_hash": _hash(node.lineno, e_line)
                }
            elif isinstance(node, ast.AsyncFunctionDef):
                e_line = getattr(node, 'end_lineno', node.lineno)
                results[node.name] = {
                    "type": "async_function",
                    "symbol_name": node.name,
                    "class_name": None,
                    "start_line": node.lineno,
                    "end_line": e_line,
                    "content_hash": _hash(node.lineno, e_line)
                }
            elif isinstance(node, ast.ClassDef):
                e_line = getattr(node, 'end_lineno', node.lineno)
                results[node.name] = {
                    "type": "class",
                    "symbol_name": node.name,
                    "class_name": None,
                    "start_line": node.lineno,
                    "end_line": e_line,
                    "content_hash": _hash(node.lineno, e_line)
                }
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        m_key = f"{node.name}::{child.name}"
                        ce_line = getattr(child, 'end_lineno', child.lineno)
                        results[m_key] = {
                            "type": "method",
                            "symbol_name": child.name,
                            "class_name": node.name,
                            "start_line": child.lineno,
                            "end_line": ce_line,
                            "content_hash": _hash(child.lineno, ce_line)
                        }
                    elif isinstance(child, ast.AsyncFunctionDef):
                        m_key = f"{node.name}::{child.name}"
                        ce_line = getattr(child, 'end_lineno', child.lineno)
                        results[m_key] = {
                            "type": "async_method",
                            "symbol_name": child.name,
                            "class_name": node.name,
                            "start_line": child.lineno,
                            "end_line": ce_line,
                            "content_hash": _hash(child.lineno, ce_line)
                        }
                    elif isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Name):
                                v_key = f"{node.name}::{target.id}"
                                ce_line = getattr(child, 'end_lineno', child.lineno)
                                results[v_key] = {
                                    "type": "variable",
                                    "symbol_name": target.id,
                                    "class_name": node.name,
                                    "start_line": child.lineno,
                                    "end_line": ce_line,
                                    "content_hash": _hash(child.lineno, ce_line)
                                }
                    elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        v_key = f"{node.name}::{child.target.id}"
                        ce_line = getattr(child, 'end_lineno', child.lineno)
                        results[v_key] = {
                            "type": "variable",
                            "symbol_name": child.target.id,
                            "class_name": node.name,
                            "start_line": child.lineno,
                            "end_line": ce_line,
                            "content_hash": _hash(child.lineno, ce_line)
                        }
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        e_line = getattr(node, 'end_lineno', node.lineno)
                        results[target.id] = {
                            "type": "variable",
                            "symbol_name": target.id,
                            "class_name": None,
                            "start_line": node.lineno,
                            "end_line": e_line,
                            "content_hash": _hash(node.lineno, e_line)
                        }
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                e_line = getattr(node, 'end_lineno', node.lineno)
                results[node.target.id] = {
                    "type": "variable",
                    "symbol_name": node.target.id,
                    "class_name": None,
                    "start_line": node.lineno,
                    "end_line": e_line,
                    "content_hash": _hash(node.lineno, e_line)
                }
    except Exception:
        pass
    return results

def extract_markdown_sections(filepath):
    """
    Parses a Markdown file for `[//]: # (SECTION_ID: ...)` or `DOC_ID:` tags or `##`/`###` headings,
    yielding a structured dict of sections with line spans and content hashes.
    """
    sections = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        current_sec = None
        for idx, line in enumerate(lines, 1):
            m_tag = re.search(r'\[//\]:\s*#\s*\((?:SECTION_ID|DOC_ID):\s*([a-zA-Z0-9_\-\.]+)', line)
            m_head = re.match(r'^(#{2,3})\s+(.+)$', line)
            if m_tag or m_head:
                if current_sec:
                    sec_lines = lines[current_sec["start"] - 1 : idx - 1]
                    sections[current_sec["key"]] = {
                        "type": "section",
                        "symbol_name": current_sec["name"],
                        "start_line": current_sec["start"],
                        "end_line": idx - 1,
                        "content_hash": hashlib.sha256("".join(sec_lines).encode('utf-8')).hexdigest()[:12]
                    }
                sec_name = m_tag.group(1) if m_tag else re.sub(r'[^a-zA-Z0-9_]+', '_', m_head.group(2).lower()).strip('_')
                current_sec = {"key": sec_name, "name": sec_name, "start": idx}
        if current_sec:
            sec_lines = lines[current_sec["start"] - 1 :]
            sections[current_sec["key"]] = {
                "type": "section",
                "symbol_name": current_sec["name"],
                "start_line": current_sec["start"],
                "end_line": len(lines),
                "content_hash": hashlib.sha256("".join(sec_lines).encode('utf-8')).hexdigest()[:12]
            }
    except Exception:
        pass
    return sections

def parse_ast_for_file(filepath):
    symbols = extract_file_ast_symbols(filepath)
    return [info["symbol_name"] for info in symbols.values() if info.get("class_name") is None]

def generate_raugusmap(root_dir, existing_map=None):
    raugus_map = {}
    existing_map = existing_map or {}
    
    ignore_dirs = {
        '.git', '__pycache__', 'venv', 'node_modules', '.venv',
        'scratch', '.pytest_cache', 'desktop_app.dist', 'build', 'dist'
    }
    ignore_files = {'.DS_Store', 'raugus_map.json'}

    def _get_inode(p):
        try:
            return int(os.stat(p).st_ino)
        except Exception:
            return 0

    exam_content_dir = os.path.join(root_dir, "plugins", "exam_application", "content")
    exam_content_alias = "devcore.plugins.exam_application.content"
    raugus_map[exam_content_alias] = {
        "type": "directory",
        "real_path": exam_content_dir,
        "inode": _get_inode(exam_content_dir),
        "required_tier": 3,
        "sensitive": True,
        "permissions": {"read": False, "write": False, "execute": False, "local_broker": True},
        "id": existing_map.get(exam_content_alias, {}).get("id", str(uuid.uuid4()))
    }

    try:
        import sys
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from security.raugus_resolver import discover_onedrive_roots
        for od_root in discover_onedrive_roots():
            slug = re.sub(r"[^a-z0-9]+", "_", os.path.basename(od_root).lower()).strip("_") or "root"
            od_alias = f"external.onedrive.{slug}"
            raugus_map[od_alias] = {
                "type": "directory",
                "real_path": od_root,
                "inode": _get_inode(od_root),
                "required_tier": 3,
                "sensitive": True,
                "permissions": {"read": False, "write": False, "execute": False, "local_broker": True},
                "id": existing_map.get(od_alias, {}).get("id", str(uuid.uuid4()))
            }
    except Exception:
        pass

    # Discover implementation plans in ~/.gemini/antigravity-cli/brain/
    brain_root = os.path.expanduser("~/.gemini/antigravity-cli/brain")
    if os.path.isdir(brain_root):
        try:
            for s_id in os.listdir(brain_root):
                s_dir = os.path.join(brain_root, s_id)
                if not os.path.isdir(s_dir) or s_id.startswith('.'):
                    continue
                for fname in os.listdir(s_dir):
                    if (fname.endswith(".md") and "plan" in fname.lower()) or fname.endswith(".plan"):
                        plan_path = os.path.join(s_dir, fname)
                        if os.path.isfile(plan_path):
                            plan_slug = fname.replace(".md", "").replace(".plan", "").lower()
                            plan_alias = f"devcore.brain.plan.{s_id[:8]}.{plan_slug}"
                            p_hash = ""
                            try:
                                with open(plan_path, "r", encoding="utf-8", errors="replace") as pf_h:
                                    p_hash = hashlib.sha256(pf_h.read().encode("utf-8")).hexdigest()[:12]
                            except Exception:
                                pass
                            raugus_map[plan_alias] = {
                                "type": "plan",
                                "real_path": plan_path,
                                "inode": _get_inode(plan_path),
                                "required_tier": 3,
                                "sensitive": False,
                                "permissions": {"read": True, "write": True, "execute": False},
                                "content_hash": p_hash,
                                "id": existing_map.get(plan_alias, {}).get("id", str(uuid.uuid4()))
                            }
                            sec_dict = extract_markdown_sections(plan_path)
                            for sec_suffix, sec_info in sec_dict.items():
                                sec_alias = f"{plan_alias}::{sec_suffix}"
                                raugus_map[sec_alias] = {
                                    "type": "section",
                                    "real_path": plan_path,
                                    "symbol_name": sec_info["symbol_name"],
                                    "start_line": sec_info["start_line"],
                                    "end_line": sec_info["end_line"],
                                    "content_hash": sec_info.get("content_hash", ""),
                                    "required_tier": 3,
                                    "sensitive": False,
                                    "permissions": {"read": True, "write": True, "execute": False},
                                    "id": existing_map.get(sec_alias, {}).get("id", str(uuid.uuid4()))
                                }
        except Exception:
            pass
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        
        dir_rel = os.path.relpath(dirpath, root_dir)
        norm_dir_rel = dir_rel.replace("\\", "/")
        if dir_rel == ".":
            dir_alias = "devcore"
        else:
            dir_alias = "devcore." + dir_rel.replace(os.sep, '.')
        
        if dir_alias not in raugus_map:
            dir_tier = 5
            if dir_rel == "." or norm_dir_rel.startswith("static") or norm_dir_rel.startswith("templates"):
                dir_tier = 2
            elif (norm_dir_rel.startswith("docs") or norm_dir_rel.startswith("sandbox") or
                  norm_dir_rel.startswith("playground") or norm_dir_rel.startswith("Central_Docs")):
                dir_tier = 3
            
            dir_sensitive = (
                norm_dir_rel.startswith("plugins/exam_application/content")
                or bool(existing_map.get(dir_alias, {}).get("sensitive", False))
            )
            if dir_sensitive:
                dir_tier = 3
                dir_perms = {"read": False, "write": False, "execute": False, "local_broker": True}
            else:
                dir_perms = {"read": True, "write": (dir_tier < 5), "execute": True}
            
            raugus_map[dir_alias] = {
                "type": "directory",
                "real_path": dirpath,
                "inode": _get_inode(dirpath),
                "required_tier": dir_tier,
                "sensitive": dir_sensitive,
                "permissions": dir_perms,
                "id": existing_map.get(dir_alias, {}).get("id", str(uuid.uuid4()))
            }

        for filename in filenames:
            if filename in ignore_files:
                continue
                
            real_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(real_path, root_dir)
            norm_rel = rel_path.replace("\\", "/")
            alias = "devcore." + rel_path.replace(os.sep, '.')
            
            required_tier = 5
            if rel_path.startswith("static") or rel_path.startswith("templates"):
                required_tier = 2
            elif (rel_path.startswith("docs") or rel_path.startswith("sandbox") or
                  rel_path.startswith("playground") or rel_path.startswith("Central_Docs")):
                required_tier = 3
                
            perms = {"read": True, "write": True, "execute": True}
            if required_tier >= 5:
                perms = {"read": True, "write": False, "execute": False}
            elif required_tier in (2, 3):
                perms = {"read": True, "write": True, "execute": False}

            is_sensitive = (
                norm_rel.startswith("plugins/exam_application/content/")
                or bool(existing_map.get(alias, {}).get("sensitive", False))
            )
            if is_sensitive:
                required_tier = 3
                perms = {"read": False, "write": False, "execute": False, "local_broker": True}
            elif alias in existing_map and "permissions" in existing_map[alias]:
                perms = dict(existing_map[alias]["permissions"])
                
            is_plan = (
                filename.endswith(".plan")
                or (filename.endswith(".md") and "plan" in filename.lower())
                or "/plans/" in norm_rel
                or norm_rel.startswith("plans/")
            )
            file_type = "plan" if is_plan else "file"

            file_hash = ""
            try:
                with open(real_path, "r", encoding="utf-8", errors="replace") as f_hash:
                    file_hash = hashlib.sha256(f_hash.read().encode("utf-8")).hexdigest()[:12]
            except Exception:
                pass

            raugus_map[alias] = {
                "type": file_type,
                "real_path": real_path,
                "inode": _get_inode(real_path),
                "required_tier": required_tier,
                "sensitive": is_sensitive,
                "permissions": perms,
                "content_hash": file_hash,
                "id": existing_map.get(alias, {}).get("id", str(uuid.uuid4()))
            }
            
            if filename.endswith(".py"):
                symbols_dict = extract_file_ast_symbols(real_path)
                for sym_suffix, sym_info in symbols_dict.items():
                    sym_alias = f"{alias}::{sym_suffix}"
                    sym_perms = dict(existing_map[sym_alias]["permissions"]) if (not is_sensitive and sym_alias in existing_map and "permissions" in existing_map[sym_alias]) else dict(perms)
                    is_locked = bool(existing_map.get(sym_alias, {}).get("locked", False))
                    sym_entry = {
                        "type": sym_info["type"],
                        "real_path": real_path,
                        "symbol_name": sym_info["symbol_name"],
                        "start_line": sym_info["start_line"],
                        "end_line": sym_info["end_line"],
                        "content_hash": sym_info.get("content_hash", ""),
                        "required_tier": required_tier,
                        "sensitive": is_sensitive,
                        "permissions": sym_perms,
                        "id": existing_map.get(sym_alias, {}).get("id", str(uuid.uuid4()))
                    }
                    if sym_info.get("class_name"):
                        sym_entry["class_name"] = sym_info["class_name"]
                    if is_locked:
                        sym_entry["locked"] = True
                    raugus_map[sym_alias] = sym_entry
            elif filename.endswith(".md") or filename.endswith(".plan"):
                sections_dict = extract_markdown_sections(real_path)
                for sec_suffix, sec_info in sections_dict.items():
                    sec_alias = f"{alias}::{sec_suffix}"
                    sec_perms = dict(existing_map[sec_alias]["permissions"]) if (not is_sensitive and sec_alias in existing_map and "permissions" in existing_map[sec_alias]) else dict(perms)
                    is_locked = bool(existing_map.get(sec_alias, {}).get("locked", False))
                    sec_entry = {
                        "type": "section",
                        "real_path": real_path,
                        "symbol_name": sec_info["symbol_name"],
                        "start_line": sec_info["start_line"],
                        "end_line": sec_info["end_line"],
                        "content_hash": sec_info.get("content_hash", ""),
                        "required_tier": required_tier,
                        "sensitive": is_sensitive,
                        "permissions": sec_perms,
                        "id": existing_map.get(sec_alias, {}).get("id", str(uuid.uuid4()))
                    }
                    if is_locked:
                        sec_entry["locked"] = True
                    raugus_map[sec_alias] = sec_entry
                    
    return raugus_map

if __name__ == "__main__":
    root_directory = "/mnt/c/Users/michael/Documents/DevCore"
    output_file = "/mnt/c/Users/michael/Documents/DevCore/security/raugus_map.json"
    if not os.path.exists(os.path.dirname(output_file)):
        output_file = "/mnt/c/Users/michael/Documents/devcore/security/raugus_map.json"
    
    prev_map = {}
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as pf:
                prev_map = json.load(pf)
        except Exception:
            prev_map = {}

    s_map = generate_raugusmap(root_directory, existing_map=prev_map)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(s_map, f, indent=4)
        
    print(f"Raugus Map successfully generated at {output_file} with {len(s_map)} aliases (Directories + Files + Deep AST Symbols + Markdown Sections).")
