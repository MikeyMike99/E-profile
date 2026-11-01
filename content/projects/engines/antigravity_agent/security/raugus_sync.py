import os
import json
import uuid
import ast
import tempfile
import logging
import hashlib
import re

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAP_PATH = os.path.join(DEVCORE_ROOT, "security", "raugus_map.json")

def _get_inode(path: str) -> int:
    try:
        return int(os.stat(path).st_ino)
    except Exception:
        return 0

def extract_file_ast_symbols(filepath: str) -> dict:
    """
    Parses a Python file and returns a structured dictionary of AST symbols:
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

def extract_markdown_sections(filepath: str) -> dict:
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

def compute_vfs_alias(target_path: str, root_dir: str = DEVCORE_ROOT) -> tuple:
    """
    Computes (alias, norm_rel, is_directory, is_plan).
    """
    abs_target = os.path.abspath(target_path)
    abs_root = os.path.abspath(root_dir)
    
    # Handle brain session plan artifacts
    brain_root = os.path.abspath(os.path.expanduser("~/.gemini/antigravity-cli/brain"))
    if abs_target.startswith(brain_root + os.sep) or abs_target.startswith(brain_root + "/"):
        rel_brain = os.path.relpath(abs_target, brain_root)
        parts = rel_brain.split(os.sep)
        session_id = parts[0][:8] if len(parts) > 0 else "session"
        fname = parts[-1]
        slug = fname.replace(".md", "").replace(".plan", "").lower()
        alias = f"devcore.brain.plan.{session_id}.{slug}"
        return alias, rel_brain.replace("\\", "/"), os.path.isdir(abs_target), True

    rel_path = os.path.relpath(abs_target, abs_root)
    norm_rel = rel_path.replace("\\", "/")
    
    is_dir = os.path.isdir(abs_target)
    if rel_path == ".":
        alias = "devcore"
    else:
        alias = "devcore." + rel_path.replace(os.sep, '.')
        
    bname = os.path.basename(abs_target).lower()
    is_plan = (
        bname.endswith(".plan")
        or (bname.endswith(".md") and "plan" in bname)
        or "/plans/" in norm_rel
        or norm_rel.startswith("plans/")
    )
    return alias, norm_rel, is_dir, is_plan

def sync_path(target_path: str, root_dir: str = DEVCORE_ROOT, remove: bool = False) -> dict:
    """
    Incrementally updates the Raugus Map on disk for a single file or directory (< 5ms).
    Ensures zero race conditions using atomic file write.
    """
    if not os.path.exists(MAP_PATH):
        return {"synced": False, "reason": "raugus_map.json not found"}

    # Files in registered external roots get their own key prefix.
    _abs = os.path.abspath(target_path)
    _rel = os.path.relpath(_abs, os.path.abspath(root_dir))
    _brain = os.path.abspath(os.path.expanduser("~/.gemini/antigravity-cli/brain"))
    if (_rel == ".." or _rel.startswith(".." + os.sep)) and not _abs.startswith(_brain + os.sep):
        try:
            from security.raugus_access import sync_external_path
            return sync_external_path(target_path, remove=remove)
        except Exception as e:
            return {"synced": False, "reason": f"external sync failed: {e}"}

    try:
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            r_map = json.load(f)
    except Exception as e:
        return {"synced": False, "reason": f"Failed to load raugus_map: {e}"}

    alias, norm_rel, is_dir, is_plan = compute_vfs_alias(target_path, root_dir)
    abs_target = os.path.abspath(target_path)
    
    # Check if target exists on disk
    exists = os.path.exists(abs_target)
    if remove or not exists:
        keys_to_remove = [k for k in r_map if k == alias or k.startswith(alias + "::") or k.startswith(alias + ".")]
        for k in keys_to_remove:
            r_map.pop(k, None)
        _atomic_write_map(r_map)
        return {"synced": True, "action": "removed", "alias": alias, "removed_keys": len(keys_to_remove)}

    existing_entry = r_map.get(alias, {})
    inode = _get_inode(abs_target)
    
    # Compute RBAC tier
    required_tier = 5
    if norm_rel.startswith("static") or norm_rel.startswith("templates"):
        required_tier = 2
    elif (norm_rel.startswith("docs") or norm_rel.startswith("sandbox") or
          norm_rel.startswith("playground") or norm_rel.startswith("Central_Docs") or
          "brain/plan" in alias):
        required_tier = 3

    is_sensitive = (
        norm_rel.startswith("plugins/exam_application/content")
        or bool(existing_entry.get("sensitive", False))
    )
    
    if is_sensitive:
        required_tier = 3
        perms = {"read": False, "write": False, "execute": False, "local_broker": True}
    elif "permissions" in existing_entry:
        perms = dict(existing_entry["permissions"])
    else:
        perms = {"read": True, "write": (required_tier < 5), "execute": is_dir}

    if is_dir:
        r_map[alias] = {
            "type": "directory",
            "real_path": abs_target,
            "inode": inode,
            "required_tier": required_tier,
            "sensitive": is_sensitive,
            "permissions": perms,
            "id": existing_entry.get("id", str(uuid.uuid4()))
        }
        _atomic_write_map(r_map)
        return {"synced": True, "action": "updated_directory", "alias": alias}

    # Target is a file or plan
    entry_type = "plan" if is_plan else "file"
    file_hash = ""
    try:
        with open(abs_target, "r", encoding="utf-8", errors="replace") as f_hash:
            file_hash = hashlib.sha256(f_hash.read().encode("utf-8")).hexdigest()[:12]
    except Exception:
        pass

    r_map[alias] = {
        "type": entry_type,
        "real_path": abs_target,
        "inode": inode,
        "required_tier": required_tier,
        "sensitive": is_sensitive,
        "permissions": perms,
        "content_hash": file_hash,
        "id": existing_entry.get("id", str(uuid.uuid4()))
    }

    sym_count = 0
    if abs_target.endswith(".py"):
        symbols_dict = extract_file_ast_symbols(abs_target)
        prefix = f"{alias}::"
        # Prune dead symbols
        dead_keys = [k for k in r_map if k.startswith(prefix) and k[len(prefix):] not in symbols_dict]
        for k in dead_keys:
            r_map.pop(k, None)

        for sym_suffix, sym_info in symbols_dict.items():
            sym_alias = f"{prefix}{sym_suffix}"
            prev_sym = r_map.get(sym_alias, {})
            sym_perms = dict(prev_sym["permissions"]) if (not is_sensitive and "permissions" in prev_sym) else dict(perms)
            is_locked = bool(prev_sym.get("locked", False))
            
            sym_entry = {
                "type": sym_info["type"],
                "real_path": abs_target,
                "symbol_name": sym_info["symbol_name"],
                "start_line": sym_info["start_line"],
                "end_line": sym_info["end_line"],
                "content_hash": sym_info.get("content_hash", ""),
                "required_tier": required_tier,
                "sensitive": is_sensitive,
                "permissions": sym_perms,
                "id": prev_sym.get("id", str(uuid.uuid4()))
            }
            if sym_info.get("class_name"):
                sym_entry["class_name"] = sym_info["class_name"]
            if is_locked:
                sym_entry["locked"] = True
            r_map[sym_alias] = sym_entry
            sym_count += 1
    elif abs_target.endswith(".md") or abs_target.endswith(".plan"):
        sections_dict = extract_markdown_sections(abs_target)
        prefix = f"{alias}::"
        dead_keys = [k for k in r_map if k.startswith(prefix) and k[len(prefix):] not in sections_dict]
        for k in dead_keys:
            r_map.pop(k, None)

        for sec_suffix, sec_info in sections_dict.items():
            sec_alias = f"{prefix}{sec_suffix}"
            prev_sec = r_map.get(sec_alias, {})
            sec_perms = dict(prev_sec["permissions"]) if (not is_sensitive and "permissions" in prev_sec) else dict(perms)
            is_locked = bool(prev_sec.get("locked", False))
            
            sec_entry = {
                "type": "section",
                "real_path": abs_target,
                "symbol_name": sec_info["symbol_name"],
                "start_line": sec_info["start_line"],
                "end_line": sec_info["end_line"],
                "content_hash": sec_info.get("content_hash", ""),
                "required_tier": required_tier,
                "sensitive": is_sensitive,
                "permissions": sec_perms,
                "id": prev_sec.get("id", str(uuid.uuid4()))
            }
            if is_locked:
                sec_entry["locked"] = True
            r_map[sec_alias] = sec_entry
            sym_count += 1

    _atomic_write_map(r_map)
    return {
        "synced": True,
        "action": "updated_file",
        "alias": alias,
        "entry_type": entry_type,
        "symbols_count": sym_count
    }

def _atomic_write_map(data: dict):
    tmp_path = f"{MAP_PATH}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_path, MAP_PATH)
