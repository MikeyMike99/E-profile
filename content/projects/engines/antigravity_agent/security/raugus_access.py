"""
Raugus access registry: extra resolver roots + time-boxed access grants.

* Roots   – directories outside DevCore that the Raugus Resolver indexes under
            their own key prefix (e.g. `rauguscore.`). Adding a root indexes it;
            removing one purges every key under its prefix and revokes every
            grant on it. DevCore itself is the built-in, non-removable root
            `devcore`.
* Grants  – hand a root (or a sub-directory of it) to an access key or a role,
            with explicit permissions (read / write / create / delete) and an
            optional expiry.

Only Siraugga's admin HTTP routes call the mutating functions here, on behalf
of an authenticated human admin. The resolver MCP only *reads* the registry:
no agent tool can add roots or grants. The registry file is HMAC-signed with a
server-held key; if it is edited by hand the signature fails and it is treated
as empty (fail closed).
"""
import fnmatch
import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time
import uuid

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

REGISTRY_FILE = os.path.join(DEVCORE_ROOT, "security", "raugus_access.json")
MAP_FILE = os.path.join(DEVCORE_ROOT, "security", "raugus_map.json")
AUDIT_FILE = os.path.join(DEVCORE_ROOT, "logs", "raugus_access_audit.jsonl")

BUILTIN_ROOT_ID = "devcore"
PERMISSIONS = ("read", "write", "create", "delete")
MAX_FILES_PER_ROOT = int(os.environ.get("DEVCORE_ROOT_MAX_FILES", "25000"))
MAX_HASH_BYTES = 2 * 1024 * 1024
RESERVED_PREFIXES = {"devcore", "external"}

# Never indexed, never readable/writable through the resolver, whoever asks.
SECRET_DIR_NAMES = {".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".claude",
                    ".gemini", ".config", ".git", ".password-store"}
SECRET_FILE_GLOBS = (
    "*token*", "*secret*", "*password*", "*passwd*", "*credential*", "*.key", "*.pem",
    "*.pfx", "*.p12", "*.kdbx", ".env", ".env.*", "*.env", "id_rsa*", "id_ed25519*",
    "id_ecdsa*", "keys.json", "sessions.json", "keychain.json", ".devcore_master.key",
    ".agent_identity.key", ".jit_elevation_lease.json", "raugus_access.json",
    ".netrc", ".npmrc", ".pypirc",
)
IGNORE_DIR_NAMES = {"__pycache__", "venv", ".venv", "node_modules", ".pytest_cache",
                    "site-packages", "desktop_app.dist", "desktop_app.build",
                    "desktop_app.onefile-build", ".mypy_cache", ".tox"}
TEXT_SYMBOL_EXTS = (".py", ".md", ".plan")

_LOCK = threading.RLock()


# --------------------------------------------------------------------------- utils

def _norm(path: str) -> str:
    try:
        from security.raugus_resolver import normalize_cross_platform_path
        return normalize_cross_platform_path(path)
    except Exception:
        return os.path.abspath(path)


def is_secret_name(name: str) -> bool:
    n = (name or "").lower()
    return any(fnmatch.fnmatch(n, g) for g in SECRET_FILE_GLOBS)


def is_secret_path(path: str) -> bool:
    """True if any component of `path` is a secret dir or the leaf is a secret file."""
    parts = [p for p in re.split(r"[\\/]+", path or "") if p]
    if not parts:
        return False
    if any(p.lower() in SECRET_DIR_NAMES for p in parts[:-1]):
        return True
    leaf = parts[-1]
    return leaf.lower() in SECRET_DIR_NAMES or is_secret_name(leaf)


def _within(path: str, root: str) -> bool:
    path, root = path.rstrip("/"), root.rstrip("/")
    return path == root or path.startswith(root + "/") or path.startswith(root + os.sep)


def _forbidden_root_reason(path: str) -> str:
    """Why `path` may not become a resolver root ('' if allowed)."""
    p = path.rstrip("/") or "/"
    home = os.path.expanduser("~").rstrip("/")
    exact = {"/", "/mnt", "/home", "/root", "/etc", "/proc", "/sys", "/dev", "/boot", "/usr",
             "/bin", "/sbin", "/lib", "/var", "/tmp", "/mnt/c", "/mnt/c/Users", "/mnt/d"}
    if p in exact or re.fullmatch(r"/mnt/[a-z]", p) or re.fullmatch(r"[A-Za-z]:\\?", p):
        return "a drive or system root cannot be added; pick a project or documents folder"
    for sysdir in ("/etc", "/proc", "/sys", "/dev", "/boot", "/usr", "/bin", "/sbin", "/lib",
                   "/root", "/var", "/mnt/c/Windows", "/mnt/c/Program Files",
                   "/mnt/c/Program Files (x86)", "/mnt/c/ProgramData"):
        if _within(p, sysdir):
            return f"system location ({sysdir}) cannot be added"
    for part in p.split("/"):
        if part.lower() in SECRET_DIR_NAMES or part == "AppData":
            return f"'{part}' holds credentials or app data and cannot be added"
    if p in (home, "/mnt/c/Users/" + os.path.basename(home)):
        return "the whole home folder holds credentials; add Documents or a project folder instead"
    return ""


def _sign(data: dict) -> str:
    from security.agent_identity import derive_key
    body = json.dumps({k: data.get(k) for k in ("roots", "grants", "updated_at")},
                      sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(derive_key("raugus_access_registry_v1"), body, hashlib.sha256).hexdigest()


def audit(event: str, actor: str, **fields):
    rec = {"ts": round(time.time(), 3), "event": event, "actor": actor, **fields}
    try:
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
    try:
        from security.central_logger import log_siem_event
        log_siem_event(level="WARNING",
                       message=f"[SECURITY_AUDIT] [RAUGUS_ACCESS] {event} by {actor}: {fields}",
                       module_name="raugus_access", logger_name="security.raugus_access")
    except Exception:
        pass


def read_audit(limit: int = 200) -> list:
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-max(1, int(limit)):]
        return [json.loads(l) for l in reversed(lines) if l.strip()]
    except Exception:
        return []


# ------------------------------------------------------------------ registry I/O

def _empty() -> dict:
    return {"roots": [], "grants": [], "updated_at": 0}


def load_registry() -> dict:
    with _LOCK:
        if not os.path.exists(REGISTRY_FILE):
            return _empty()
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return _empty()
        if not hmac.compare_digest(str(data.get("signature", "")), _sign(data)):
            audit("registry_signature_invalid", "system", note="registry ignored (fail closed)")
            return _empty()
        data.setdefault("roots", [])
        data.setdefault("grants", [])
        return data


def _save_registry(data: dict):
    data["updated_at"] = round(time.time(), 3)
    data["signature"] = _sign(data)
    tmp = f"{REGISTRY_FILE}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, REGISTRY_FILE)


def builtin_root() -> dict:
    return {"id": BUILTIN_ROOT_ID, "label": "DevCore", "prefix": "devcore", "path": DEVCORE_ROOT,
            "builtin": True, "default_tier": 5, "status": "ready"}


def list_roots(include_builtin: bool = True) -> list:
    roots = list(load_registry()["roots"])
    return ([builtin_root()] if include_builtin else []) + roots


def _active(grant: dict, now: float = None) -> bool:
    exp = grant.get("expires_at")
    return not grant.get("revoked") and (exp is None or float(exp) > (now or time.time()))


def list_grants(include_expired: bool = False) -> list:
    now = time.time()
    out = []
    for g in load_registry()["grants"]:
        g = dict(g)
        g["active"] = _active(g, now)
        if include_expired or g["active"]:
            out.append(g)
    return out


# ------------------------------------------------------------------ map indexing

def _map_load() -> dict:
    try:
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _map_save(m: dict):
    tmp = f"{MAP_FILE}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=4)
    os.replace(tmp, MAP_FILE)


def _keys_for_prefix(m: dict, prefix: str) -> list:
    return [k for k in m if k == prefix or k.startswith(prefix + ".") or k.startswith(prefix + "::")]


def _alias(prefix: str, rel: str) -> str:
    rel = rel.replace("\\", "/").strip("/")
    return prefix if rel in ("", ".") else prefix + "." + rel.replace("/", ".")


def _file_entries(prefix: str, root: dict, real_path: str, rel: str, existing: dict) -> dict:
    """Map entries (file + symbols/sections) for one file of an external root."""
    from generate_raugusmap import extract_file_ast_symbols, extract_markdown_sections
    alias = _alias(prefix, rel)
    tier = int(root.get("default_tier", 5))
    perms = {"read": True, "write": True, "execute": False}
    out = {}
    try:
        st = os.stat(real_path)
        ino, size = int(st.st_ino), st.st_size
    except Exception:
        ino, size = 0, 0
    h = ""
    if size <= MAX_HASH_BYTES:
        try:
            with open(real_path, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()[:12]
        except Exception:
            pass
    out[alias] = {"type": "file", "real_path": real_path, "inode": ino, "required_tier": tier,
                  "sensitive": False, "permissions": dict(perms), "content_hash": h,
                  "root_id": root["id"], "id": existing.get(alias, {}).get("id", str(uuid.uuid4()))}
    if size <= MAX_HASH_BYTES and real_path.endswith(TEXT_SYMBOL_EXTS):
        syms = extract_file_ast_symbols(real_path) if real_path.endswith(".py") else extract_markdown_sections(real_path)
        for suffix, info in syms.items():
            sk = f"{alias}::{suffix}"
            e = {"type": info["type"], "real_path": real_path, "symbol_name": info["symbol_name"],
                 "start_line": info["start_line"], "end_line": info["end_line"],
                 "content_hash": info.get("content_hash", ""), "required_tier": tier,
                 "sensitive": False, "permissions": dict(perms), "root_id": root["id"],
                 "id": existing.get(sk, {}).get("id", str(uuid.uuid4()))}
            if info.get("class_name"):
                e["class_name"] = info["class_name"]
            out[sk] = e
    return out


def index_root(root: dict, existing: dict = None) -> tuple:
    """Walk an external root and build its map entries.
    Returns (entries, file_count, truncated)."""
    existing = existing or {}
    base = root["path"].rstrip("/")
    prefix = root["prefix"]
    tier = int(root.get("default_tier", 5))
    # Nested resolver roots (incl. DevCore) keep their own keys; skip them here.
    nested = [r["path"].rstrip("/") for r in list_roots() if r["id"] != root["id"]
              and _within(r["path"], base) and r["path"].rstrip("/") != base]
    entries, files, truncated = {}, 0, False
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORE_DIR_NAMES and d.lower() not in SECRET_DIR_NAMES
            and not d.endswith((".dist-info", ".egg-info"))
            and not any(_within(os.path.join(dirpath, d), n) for n in nested)
        )
        rel_dir = os.path.relpath(dirpath, base)
        dkey = _alias(prefix, rel_dir)
        try:
            ino = int(os.stat(dirpath).st_ino)
        except Exception:
            ino = 0
        entries[dkey] = {"type": "directory", "real_path": dirpath, "inode": ino,
                         "required_tier": tier, "sensitive": False,
                         "permissions": {"read": True, "write": True, "execute": False},
                         "root_id": root["id"], "id": existing.get(dkey, {}).get("id", str(uuid.uuid4()))}
        for fn in sorted(filenames):
            if is_secret_name(fn) or fn in (".DS_Store", "desktop.ini") or fn.startswith("~$"):
                continue
            if files >= MAX_FILES_PER_ROOT:
                truncated = True
                break
            rp = os.path.join(dirpath, fn)
            if os.path.islink(rp):
                continue
            entries.update(_file_entries(prefix, root, rp, os.path.relpath(rp, base), existing))
            files += 1
        if truncated:
            break
    return entries, files, truncated


def _reload_resolvers():
    try:
        from security.raugus_resolver import resolver
        resolver._load_phonebook()
    except Exception:
        pass


def reindex_root(root_id: str, actor: str = "system") -> dict:
    """(Re)build the map keys of one external root; replaces its old keys."""
    with _LOCK:
        reg = load_registry()
        root = next((r for r in reg["roots"] if r["id"] == root_id), None)
        if not root:
            raise KeyError(f"Unknown root '{root_id}'.")
        m = _map_load()
        old = {k: m[k] for k in _keys_for_prefix(m, root["prefix"])}
    try:
        if not os.path.isdir(root["path"]):
            raise FileNotFoundError("folder no longer exists")
        entries, files, truncated = index_root(root, old)
        status, error = ("truncated" if truncated else "ready"), ""
    except Exception as e:
        entries, files, truncated, status, error = {}, 0, False, "error", str(e)
    with _LOCK:
        m = _map_load()
        for k in _keys_for_prefix(m, root["prefix"]):
            del m[k]
        m.update(entries)
        _map_save(m)
        reg = load_registry()
        for r in reg["roots"]:
            if r["id"] == root_id:
                r.update({"status": status, "error": error, "file_count": files,
                          "key_count": len(entries), "last_indexed_at": round(time.time(), 3)})
        _save_registry(reg)
    _reload_resolvers()
    audit("root_indexed", actor, root_id=root_id, status=status, files=files, keys=len(entries))
    return {"root_id": root_id, "status": status, "error": error, "file_count": files,
            "key_count": len(entries), "truncated": truncated}


def preserve_external_keys(new_map: dict, old_map: dict) -> dict:
    """After a DevCore-only map rebuild, carry over the keys of registered roots."""
    for r in list_roots(include_builtin=False):
        for k in _keys_for_prefix(old_map, r["prefix"]):
            new_map.setdefault(k, old_map[k])
    return new_map


# ------------------------------------------------------------------ mutations

def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")
    return s or "root"


def add_root(path: str, actor: str, label: str = None, default_tier: int = 5) -> dict:
    p = _norm(path).rstrip("/")
    if not os.path.isdir(p):
        raise ValueError(f"Folder not found: {path}")
    real = os.path.realpath(p)
    reason = _forbidden_root_reason(real) or _forbidden_root_reason(p)
    if reason:
        raise PermissionError(reason)
    if is_secret_path(real):
        raise PermissionError("That folder looks like it holds secrets and cannot be added.")
    with _LOCK:
        reg = load_registry()
        for r in [builtin_root()] + reg["roots"]:
            rp = r["path"].rstrip("/")
            if rp == real:
                raise ValueError(f"Already registered as '{r['label']}'.")
            if _within(real, rp):
                raise ValueError(f"Inside the existing root '{r['label']}' — grant a sub-folder of it instead.")
        prefix = base = _slug(label or os.path.basename(real))
        taken = {r["prefix"] for r in reg["roots"]} | RESERVED_PREFIXES
        n = 2
        while prefix in taken or prefix.startswith("devcore"):
            prefix = f"{base}_{n}"
            n += 1
        root = {"id": "root-" + uuid.uuid4().hex[:10], "label": label or os.path.basename(real),
                "prefix": prefix, "path": real, "builtin": False,
                "default_tier": max(1, min(int(default_tier or 5), 5)),
                "added_by": actor, "added_at": round(time.time(), 3), "status": "indexing"}
        reg["roots"].append(root)
        _save_registry(reg)
    audit("root_added", actor, root_id=root["id"], label=root["label"], prefix=prefix)
    return root


def remove_root(root_id: str, actor: str) -> dict:
    """Remove a root completely: its map keys, its grants, and the registration."""
    if root_id == BUILTIN_ROOT_ID:
        raise PermissionError("The built-in DevCore root cannot be removed.")
    with _LOCK:
        reg = load_registry()
        root = next((r for r in reg["roots"] if r["id"] == root_id), None)
        if not root:
            raise KeyError(f"Unknown root '{root_id}'.")
        m = _map_load()
        purged = _keys_for_prefix(m, root["prefix"])
        purged += [k for k, v in m.items() if v.get("root_id") == root_id and k not in purged]
        for k in purged:
            m.pop(k, None)
        _map_save(m)
        revoked = [g["id"] for g in reg["grants"] if g.get("root_id") == root_id]
        reg["grants"] = [g for g in reg["grants"] if g.get("root_id") != root_id]
        reg["roots"] = [r for r in reg["roots"] if r["id"] != root_id]
        _save_registry(reg)
    _reload_resolvers()
    audit("root_removed", actor, root_id=root_id, label=root["label"], keys_purged=len(purged),
          grants_revoked=len(revoked))
    return {"root_id": root_id, "keys_purged": len(purged), "grants_revoked": revoked}


def add_grant(root_id: str, grantee_type: str, grantee: str, permissions: dict, actor: str,
              subpath: str = "", expires_at: float = None, note: str = "") -> dict:
    from core.roles import GRANTABLE_ROLES, is_admin_role
    if grantee_type not in ("key", "role"):
        raise ValueError("grantee_type must be 'key' or 'role'.")
    if not grantee:
        raise ValueError("A grantee is required.")
    if grantee_type == "role" and (is_admin_role(grantee) or grantee not in GRANTABLE_ROLES):
        raise ValueError(f"Role must be one of {', '.join(GRANTABLE_ROLES)} (admins already have full access).")
    perms = {p: bool((permissions or {}).get(p)) for p in PERMISSIONS}
    if not any(perms.values()):
        raise ValueError("Pick at least one permission.")
    if perms["write"] or perms["create"] or perms["delete"]:
        perms["read"] = True
    if expires_at is not None:
        expires_at = float(expires_at)
        if expires_at <= time.time():
            raise ValueError("Expiry must be in the future.")
    root = next((r for r in list_roots() if r["id"] == root_id), None)
    if not root:
        raise KeyError(f"Unknown root '{root_id}'.")
    sub = (subpath or "").replace("\\", "/").strip("/")
    if ".." in sub.split("/"):
        raise ValueError("Sub-folder may not contain '..'.")
    target = os.path.join(root["path"], sub) if sub else root["path"]
    if not os.path.isdir(target):
        raise ValueError(f"Sub-folder '{sub}' does not exist in {root['label']}.")
    if is_secret_path(target):
        raise PermissionError("That folder holds secrets and cannot be granted.")
    g = {"id": "grant-" + uuid.uuid4().hex[:10], "root_id": root_id, "subpath": sub,
         "grantee_type": grantee_type, "grantee": grantee, "permissions": perms,
         "expires_at": expires_at, "granted_by": actor, "granted_at": round(time.time(), 3),
         "note": (note or "")[:200], "revoked": False}
    with _LOCK:
        reg = load_registry()
        reg["grants"].append(g)
        _save_registry(reg)
    audit("grant_added", actor, grant_id=g["id"], root_id=root_id, subpath=sub,
          grantee=f"{grantee_type}:{grantee}", permissions=perms, expires_at=expires_at)
    return g


def revoke_grant(grant_id: str, actor: str) -> dict:
    with _LOCK:
        reg = load_registry()
        g = next((x for x in reg["grants"] if x["id"] == grant_id), None)
        if not g:
            raise KeyError(f"Unknown grant '{grant_id}'.")
        reg["grants"] = [x for x in reg["grants"] if x["id"] != grant_id]
        _save_registry(reg)
    audit("grant_revoked", actor, grant_id=grant_id, grantee=f"{g['grantee_type']}:{g['grantee']}")
    return {"grant_id": grant_id, "revoked": True}


def purge_expired(actor: str = "system") -> int:
    with _LOCK:
        reg = load_registry()
        now = time.time()
        keep = [g for g in reg["grants"] if _active(g, now)]
        n = len(reg["grants"]) - len(keep)
        if n:
            reg["grants"] = keep
            _save_registry(reg)
    if n:
        audit("grants_expired_purged", actor, count=n)
    return n


# ------------------------------------------------------------------ authorization

def root_for_path(path: str):
    p = _norm(path)
    best = None
    for r in list_roots():
        if _within(p, r["path"]) and (best is None or len(r["path"]) > len(best["path"])):
            best = r
    return best


def grant_scopes_for(identity: dict) -> list:
    """[(absolute_scope_dir, permissions)] for every active grant held by
    `identity` (its access key or its role). Load once per request."""
    if not identity:
        return []
    principal, role = identity.get("principal"), str(identity.get("role", "")).lower()
    reg = load_registry()
    roots = {r["id"]: r for r in [builtin_root()] + reg["roots"]}
    now = time.time()
    out = []
    for g in reg["grants"]:
        r = roots.get(g.get("root_id"))
        if not r or not _active(g, now):
            continue
        if (g["grantee_type"] == "key" and g["grantee"] == principal) or \
           (g["grantee_type"] == "role" and g["grantee"].lower() == role):
            scope = os.path.join(r["path"], g["subpath"]) if g.get("subpath") else r["path"]
            out.append((_norm(scope), dict(g["permissions"])))
    return out


def perms_from_scopes(scopes: list, path: str) -> dict:
    perms = {p: False for p in PERMISSIONS}
    if not scopes or not path:
        return perms
    p = _norm(path)
    for scope, gp in scopes:
        if _within(p, scope):
            for k in PERMISSIONS:
                perms[k] = perms[k] or bool(gp.get(k))
    return perms


def grant_permissions_for(identity: dict, path: str) -> dict:
    """Union of the permissions that active grants give `identity` on `path`."""
    return perms_from_scopes(grant_scopes_for(identity), path)


def readable_paths_for(identity: dict) -> list:
    """Directories `identity` may read with raw file tools (for the CLI brain's
    Read allow-list): everything registered for admins, else granted scopes."""
    if not identity:
        return []
    if int(identity.get("tier", 0)) >= 5:
        return [r["path"] for r in list_roots()]
    out = []
    principal, role = identity.get("principal"), str(identity.get("role", "")).lower()
    roots = {r["id"]: r for r in list_roots()}
    for g in list_grants():
        if not g["permissions"].get("read"):
            continue
        if (g["grantee_type"] == "key" and g["grantee"] == principal) or \
           (g["grantee_type"] == "role" and g["grantee"].lower() == role):
            r = roots.get(g["root_id"])
            if r:
                out.append(os.path.join(r["path"], g["subpath"]) if g["subpath"] else r["path"])
    return sorted(set(out))


def sync_external_path(path: str, remove: bool = False) -> dict:
    """Incremental map update for a single file inside a registered external root."""
    root = root_for_path(path)
    if not root or root.get("builtin"):
        return {"synced": False, "reason": "not inside a registered external root"}
    rel = os.path.relpath(_norm(path), root["path"])
    alias = _alias(root["prefix"], rel)
    with _LOCK:
        m = _map_load()
        for k in [k for k in m if k == alias or k.startswith(alias + "::")]:
            m.pop(k, None)
        if not remove and os.path.isfile(path) and not is_secret_path(path):
            m.update(_file_entries(root["prefix"], root, _norm(path), rel, {}))
        _map_save(m)
    return {"synced": True, "alias": alias}
