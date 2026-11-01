"""Resolver Access admin API: resolver roots + access grants.

Every endpoint needs an authenticated human admin. Mutations are refused while
an agent task is running (agents act only while running, so a change made
during a run could have come from one). Adding or removing a root also needs an
active Super Admin JIT elevation. The resolver exposes no tool for any of this.
"""
import asyncio
import os
import time

from quart import Blueprint, current_app, jsonify, request

from core.routes.auth import get_current_user

access_bp = Blueprint("access_bp", __name__)


def _actor(user: dict) -> str:
    return f"{user.get('username') or user.get('name') or 'admin'} ({user.get('key_id') or 'session'})"


def _admin_or_error():
    user = get_current_user()
    if not user or not current_app.security_mgr.is_admin_user(user):
        return None, (jsonify({"success": False, "error": "Admin access required."}), 403)
    return user, None


def _agent_busy() -> bool:
    mgr = getattr(current_app, "agent_mgr", None)
    try:
        return bool(mgr and mgr.is_running())
    except Exception:
        return False


def _mutation_guard(need_jit: bool = False):
    """Return (user, error_response)."""
    user, err = _admin_or_error()
    if err:
        return None, err
    if _agent_busy():
        return None, (jsonify({
            "success": False,
            "policy_violation": True,
            "error": "An agent task is running. Access changes are only accepted while no agent is active.",
            "solution": "Wait for the task to finish (or cancel it), then try again.",
        }), 409)
    if need_jit:
        try:
            from security.jit_elevation import verify_jit_elevation
            jit_ok = bool(verify_jit_elevation().get("valid"))
        except Exception:
            jit_ok = False
        if not jit_ok:
            return None, (jsonify({
                "success": False,
                "needs_jit": True,
                "error": "Adding or removing a resolver root needs an active Super Admin JIT elevation.",
                "solution": "Click 'Elevate JIT (5m)' in this panel, then retry.",
            }), 403)
    return user, None


def _fail(e: Exception, code: int = 400):
    return jsonify({"success": False, "error": str(e)}), code


@access_bp.route("/api/access/overview", methods=["GET"])
async def access_overview():
    user, err = _admin_or_error()
    if err:
        return err
    from security import raugus_access as ra
    from core.roles import GRANTABLE_ROLES
    try:
        from security.jit_elevation import get_jit_status
        jit = get_jit_status()
    except Exception:
        jit = {"active": False}
    roots = ra.list_roots()
    by_id = {r["id"]: r for r in roots}
    grants = []
    for g in ra.list_grants(include_expired=True):
        g["root_label"] = by_id.get(g["root_id"], {}).get("label", g["root_id"])
        grants.append(g)
    return jsonify({
        "success": True,
        "roots": roots,
        "grants": grants,
        "principals": current_app.security_mgr.list_principals(),
        "roles": list(GRANTABLE_ROLES),
        "permissions": list(ra.PERMISSIONS),
        "jit": jit,
        "agent_busy": _agent_busy(),
        "now": time.time(),
    })


@access_bp.route("/api/access/browse", methods=["GET"])
async def access_browse():
    """List sub-folders of a server path (for picking a root or a grant scope)."""
    user, err = _admin_or_error()
    if err:
        return err
    from security import raugus_access as ra
    raw = (request.args.get("path") or "").strip()
    root_id = request.args.get("root_id")
    if root_id:
        root = next((r for r in ra.list_roots() if r["id"] == root_id), None)
        if not root:
            return _fail(KeyError("Unknown root."), 404)
        base = root["path"]
        sub = raw.replace("\\", "/").strip("/")
        if ".." in sub.split("/"):
            return _fail(ValueError("Invalid sub-folder."))
        path = os.path.join(base, sub) if sub else base
    else:
        path = ra._norm(raw or os.path.dirname(ra.DEVCORE_ROOT))
    if not os.path.isdir(path):
        return _fail(ValueError("Folder not found."), 404)
    dirs = []
    try:
        for name in sorted(os.listdir(path), key=str.lower):
            full = os.path.join(path, name)
            if os.path.isdir(full) and not name.startswith(".") and not ra.is_secret_path(full) \
                    and name not in ra.IGNORE_DIR_NAMES:
                dirs.append(name)
    except Exception as e:
        return _fail(e)
    return jsonify({"success": True, "path": path, "parent": os.path.dirname(path.rstrip("/")),
                    "dirs": dirs[:500], "addable_reason": ra._forbidden_root_reason(path)})


@access_bp.route("/api/access/roots", methods=["POST"])
async def access_add_root():
    user, err = _mutation_guard(need_jit=True)
    if err:
        return err
    from security import raugus_access as ra
    data = await request.get_json(silent=True) or {}
    try:
        root = ra.add_root(data.get("path", ""), _actor(user), label=(data.get("label") or None))
    except (ValueError, PermissionError, KeyError) as e:
        return _fail(e)
    # Index in the background; the UI polls /api/access/overview for status.
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, ra.reindex_root, root["id"], _actor(user))
    return jsonify({"success": True, "root": root})


@access_bp.route("/api/access/roots/<root_id>", methods=["DELETE"])
async def access_remove_root(root_id):
    user, err = _mutation_guard(need_jit=True)
    if err:
        return err
    from security import raugus_access as ra
    try:
        res = ra.remove_root(root_id, _actor(user))
    except (ValueError, PermissionError, KeyError) as e:
        return _fail(e)
    return jsonify({"success": True, **res})


@access_bp.route("/api/access/roots/<root_id>/reindex", methods=["POST"])
async def access_reindex_root(root_id):
    user, err = _mutation_guard()
    if err:
        return err
    from security import raugus_access as ra
    if root_id == ra.BUILTIN_ROOT_ID:
        return _fail(ValueError("DevCore is re-indexed by the resolver's refresh; nothing to do here."))
    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(None, ra.reindex_root, root_id, _actor(user))
    except KeyError as e:
        return _fail(e, 404)
    return jsonify({"success": True, **res})


@access_bp.route("/api/access/grants", methods=["POST"])
async def access_add_grant():
    user, err = _mutation_guard()
    if err:
        return err
    from security import raugus_access as ra
    data = await request.get_json(silent=True) or {}
    expires_at = data.get("expires_at")
    hours = data.get("expires_in_hours")
    try:
        if hours not in (None, "", 0, "0"):
            expires_at = time.time() + float(hours) * 3600
        elif expires_at in ("", None):
            expires_at = None
        if data.get("grantee_type") == "key":
            known = {p["key_id"] for p in current_app.security_mgr.list_principals()}
            if data.get("grantee") not in known:
                raise ValueError("Unknown access key.")
        g = ra.add_grant(
            root_id=data.get("root_id", ""),
            grantee_type=data.get("grantee_type", ""),
            grantee=data.get("grantee", ""),
            permissions=data.get("permissions") or {},
            actor=_actor(user),
            subpath=data.get("subpath", ""),
            expires_at=expires_at,
            note=data.get("note", ""),
        )
    except (ValueError, PermissionError, KeyError, TypeError) as e:
        return _fail(e)
    return jsonify({"success": True, "grant": g})


@access_bp.route("/api/access/grants/<grant_id>", methods=["DELETE"])
async def access_revoke_grant(grant_id):
    # Revoking only ever removes access, so it is allowed even while an agent runs.
    user, err = _admin_or_error()
    if err:
        return err
    from security import raugus_access as ra
    try:
        res = ra.revoke_grant(grant_id, _actor(user))
    except KeyError as e:
        return _fail(e, 404)
    return jsonify({"success": True, **res})


@access_bp.route("/api/access/grants/purge-expired", methods=["POST"])
async def access_purge_expired():
    user, err = _admin_or_error()
    if err:
        return err
    from security import raugus_access as ra
    return jsonify({"success": True, "purged": ra.purge_expired(_actor(user))})


@access_bp.route("/api/access/audit", methods=["GET"])
async def access_audit():
    user, err = _admin_or_error()
    if err:
        return err
    from security import raugus_access as ra
    return jsonify({"success": True, "events": ra.read_audit(int(request.args.get("limit", 200)))})
