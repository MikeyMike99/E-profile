import asyncio
import importlib
from core.routes.auth import get_current_user
from quart import Blueprint, request, jsonify, current_app, Response
import os, json
from core import session_manager as sm
from core import project_manager as pm
from agents import agent_manager as am
from security import security_manager as sec_m
from core.audit_registry import get_audit_registry

system_bp = Blueprint('system_bp', __name__)

IMMUTABLE_JIT_BASENAMES = {
    ".jit_elevation_lease.json",
    ".devcore_master.key",
}

PROTECTED_FIREWALL_BASENAMES = {
    "jit_elevation.py",
    "raugus_hook.py",
    "hooks.json",
    "local_brain_broker.py",
    "raugus_resolver.py",
    "raugus_map.json",
    "generate_raugusmap.py",
    "tool_security_auditor.py",
}

def _is_jit_active() -> bool:
    try:
        from security.jit_elevation import verify_jit_elevation
        ver = verify_jit_elevation()
        return bool(ver.get("valid") is True)
    except Exception:
        return False

async def execute_hot_patch_sequence(app_obj=None, manual_trigger=False, fast_countdown=False):
    """Safe zero-downtime hot-patching sequence with syntax validation (py_compile), backup, and automated rollback."""
    global sm, pm, am, sec_m
    import shutil
    import py_compile
    import traceback

    target_app = app_obj
    if target_app is None:
        try:
            target_app = current_app._get_current_object()
        except Exception:
            import sys
            main_mod = sys.modules.get("__main__") or sys.modules.get("core.server")
            target_app = getattr(main_mod, "app", None) if main_mod else None

    if target_app is None or not hasattr(target_app, "agent_mgr"):
        return {"success": False, "error": "Target app or agent_mgr unavailable"}

    agent_mgr = target_app.agent_mgr
    core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(core_dir)
    patch_dir = os.path.join(core_dir, "patches")
    backup_dir = os.path.join(core_dir, "backups")
    os.makedirs(patch_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    patches_found = [f for f in os.listdir(patch_dir) if f.endswith(".py")]

    if not patches_found and not manual_trigger:
        return {"success": True, "message": "No staged patches found.", "patches_applied": 0}

    def _resolve_target_path(filename: str) -> str:
        candidates = [
            os.path.join(core_dir, filename),
            os.path.join(core_dir, "routes", filename),
            os.path.join(repo_root, "agents", filename),
            os.path.join(repo_root, "agents", "mixins", filename),
            os.path.join(repo_root, "security", filename),
            os.path.join(repo_root, ".agents", filename),
            os.path.join(repo_root, filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return os.path.join(core_dir, filename)

    jit_active = _is_jit_active()

    if patches_found:
        for patch in patches_found:
            if patch in IMMUTABLE_JIT_BASENAMES:
                try:
                    os.remove(os.path.join(patch_dir, patch))
                except Exception:
                    pass
                await agent_mgr.broadcast({
                    "type": "system",
                    "level": "error",
                    "message": f"❌ PATCH BLOCKED: '{patch}' is an immutable Human-in-the-Loop JIT authority file."
                })
                return {"success": False, "error": f"Patch target '{patch}' is an immutable JIT authority file."}

            if patch in PROTECTED_FIREWALL_BASENAMES and not jit_active:
                try:
                    os.remove(os.path.join(patch_dir, patch))
                except Exception:
                    pass
                await agent_mgr.broadcast({
                    "type": "system",
                    "level": "error",
                    "message": f"❌ PATCH BLOCKED: '{patch}' is a locked Raugus Firewall guard file. Elevate Super Admin JIT (5m) first."
                })
                return {"success": False, "error": f"Patch target '{patch}' is locked by Raugus Self-Protection."}

        await agent_mgr.broadcast({
            "type": "system",
            "level": "warning",
            "message": f"🚨 EXPLOIT / PATCH DETECTED: Initiating safe zero-downtime hot-patching sequence for {', '.join(patches_found)}..."
        })

        for patch in patches_found:
            try:
                py_compile.compile(os.path.join(patch_dir, patch), doraise=True)
            except py_compile.PyCompileError as ce:
                await agent_mgr.broadcast({
                    "type": "system",
                    "level": "error",
                    "message": f"❌ PATCH ABORTED: Syntax error detected in {patch}. Server protection engaged."
                })
                return {"success": False, "error": f"Syntax error in {patch}: {ce}"}

        if fast_countdown:
            await agent_mgr.broadcast({
                "type": "system",
                "level": "info",
                "message": "Validating and applying staged hot-patch..."
            })
            await asyncio.sleep(0.15)
        else:
            for i in range(3, 0, -1):
                await agent_mgr.broadcast({
                    "type": "system",
                    "level": "info",
                    "message": f"Validating and applying hot-patch in {i}s..."
                })
                await asyncio.sleep(1)

        applied_targets = []
        for patch in patches_found:
            target_file = _resolve_target_path(patch)
            backup_file = os.path.join(backup_dir, patch)
            if os.path.exists(target_file):
                shutil.copy2(target_file, backup_file)
            shutil.copy2(os.path.join(patch_dir, patch), target_file)
            applied_targets.append((patch, target_file, backup_file))
    else:
        await agent_mgr.broadcast({
            "type": "system",
            "level": "warning",
            "message": "🛡️ AUTO-PATCH ENGINE: Manual hot-patch sequence initiated (0 external files in core/patches/). Validating core engine modules..."
        })
        try:
            from core.bootstrap_gateway import get_engine_files
            rel_list = get_engine_files(repo_root)
            core_targets = [(os.path.basename(r), os.path.join(repo_root, r)) for r in rel_list]
        except Exception:
            core_targets = [
                ("server.py", os.path.join(core_dir, "server.py")),
                ("session_manager.py", os.path.join(core_dir, "session_manager.py")),
                ("project_manager.py", os.path.join(core_dir, "project_manager.py")),
                ("bootstrap_gateway.py", os.path.join(core_dir, "bootstrap_gateway.py")),
                ("agent_manager.py", os.path.join(repo_root, "agents", "agent_manager.py")),
                ("security_manager.py", os.path.join(repo_root, "security", "security_manager.py")),
            ]
        for label, fpath in core_targets:
            if os.path.exists(fpath):
                try:
                    py_compile.compile(fpath, doraise=True)
                    if label not in PROTECTED_FIREWALL_BASENAMES:
                        shutil.copy2(fpath, os.path.join(backup_dir, label))
                except py_compile.PyCompileError as ce:
                    await agent_mgr.broadcast({
                        "type": "system",
                        "level": "error",
                        "message": f"❌ VALIDATION ABORTED: Syntax error detected in {label}. Server protection engaged."
                    })
                    return {"success": False, "error": f"Syntax error in {label}: {ce}"}
        await asyncio.sleep(0.2 if fast_countdown else 0.6)
        applied_targets = []

    await agent_mgr.broadcast({
        "type": "system",
        "level": "info",
        "message": "Syntax verified & backups snapshotted. Re-compiling backend modules in-memory..."
    })

    active_clients = dict(agent_mgr.connected_clients)
    is_busy = agent_mgr.is_running()
    old_proc = getattr(agent_mgr, "active_proc", None)
    old_task = getattr(agent_mgr, "active_task", None)
    old_start = getattr(agent_mgr, "task_start_time", getattr(agent_mgr, "start_time", None))
    old_actions = getattr(agent_mgr, "actions", [])
    old_active_proj = getattr(getattr(target_app, "project_mgr", None), "active_project", None)

    try:
        importlib.reload(sm)
        importlib.reload(pm)
        importlib.reload(am)
        importlib.reload(sec_m)
        try:
            import core.routes.auth as auth_mod
            importlib.reload(auth_mod)
        except Exception:
            auth_mod = None
        try:
            import core.token_telemetry as tt
            importlib.reload(tt)
            tt._ENGINE_INSTANCE = None
        except Exception:
            pass

        if hasattr(sm, "_sync_live_blueprint_routes"):
            sm._sync_live_blueprint_routes()

        target_app.project_mgr = pm.ProjectManager()
        target_app.project_mgr.active_project = old_active_proj
        target_app.project_mgr.reinit()
        target_app.session_mgr = sm.SessionManager()
        target_app.security_mgr = sec_m.SecurityManager()

        target_app.agent_mgr = am.AgentTaskManager(project_manager=target_app.project_mgr)
        target_app.agent_mgr.connected_clients = active_clients
        if is_busy:
            target_app.agent_mgr.active_proc = old_proc
            target_app.agent_mgr.active_task = old_task
            target_app.agent_mgr.task_start_time = old_start
            target_app.agent_mgr.actions = old_actions

        import sys
        main_mod = sys.modules.get("__main__") or sys.modules.get("core.server")
        if main_mod:
            main_mod.project_mgr = target_app.project_mgr
            main_mod.session_mgr = target_app.session_mgr
            main_mod.security_mgr = target_app.security_mgr
            main_mod.agent_mgr = target_app.agent_mgr

        try:
            dynamic_endpoints = [
                ('/telemetry', 'system_bp.telemetry_page', telemetry_page, ['GET']),
                ('/plugin/telemetry', 'system_bp.telemetry_page_plugin', telemetry_page, ['GET']),
                ('/api/telemetry/tokens', 'system_bp.api_token_telemetry', api_token_telemetry, ['GET']),
                ('/audits', 'system_bp.audits_page', audits_page, ['GET']),
                ('/plugin/audits', 'system_bp.audits_page_plugin', audits_page, ['GET']),
                ('/api/audits', 'system_bp.api_get_audits', api_get_audits, ['GET']),
                ('/api/audits/run', 'system_bp.api_run_audit', api_run_audit, ['POST']),
                ('/api/audits/refresh', 'system_bp.api_refresh_audits', api_refresh_audits, ['POST']),
                ('/api/audits/results/<audit_id>', 'system_bp.api_audit_result', api_audit_result, ['GET']),
            ]
            if auth_mod:
                sub_set_fn = getattr(auth_mod, 'set_user_subscription_route', None)
                sub_status_fn = getattr(auth_mod, 'get_user_subscription_status', None)
                sub_del_fn = getattr(auth_mod, 'delete_user_subscription_route', None)
                if sub_set_fn:
                    dynamic_endpoints.append(('/api/user/subscription/set', 'auth_bp.set_user_subscription_route', sub_set_fn, ['POST']))
                if sub_status_fn:
                    dynamic_endpoints.append(('/api/user/subscription/status', 'auth_bp.get_user_subscription_status', sub_status_fn, ['GET']))
                if sub_del_fn:
                    dynamic_endpoints.append(('/api/user/subscription', 'auth_bp.delete_user_subscription_route', sub_del_fn, ['DELETE']))

            existing_rules = {r.rule: r.endpoint for r in target_app.url_map.iter_rules()}
            for rule, ep, view, methods in dynamic_endpoints:
                if rule not in existing_rules:
                    target_app.add_url_rule(rule, endpoint=ep, view_func=view, methods=methods)
                else:
                    matched_ep = existing_rules[rule]
                    target_app.view_functions[matched_ep] = view
                    target_app.view_functions[ep] = view
        except Exception:
            pass

        for patch, _, _ in applied_targets:
            staged_path = os.path.join(patch_dir, patch)
            if os.path.exists(staged_path):
                try:
                    os.remove(staged_path)
                except Exception:
                    pass

        msg = (
            f"✅ Server successfully hot-patched ({len(applied_targets)} patch(es) applied) and secured with zero downtime."
            if applied_targets
            else "✅ Auto-Patch verification complete: Syntax validated (py_compile), backups saved (core/backups/), and engine hot-swapped in memory."
        )
        await target_app.agent_mgr.broadcast({
            "type": "system",
            "level": "success",
            "message": msg
        })
        return {"success": True, "message": msg, "patches_applied": len(applied_targets)}
    except Exception as e:
        await agent_mgr.broadcast({
            "type": "system",
            "level": "error",
            "message": f"⚠️ CRITICAL: Patch crashed the server engine ({e})! Initiating emergency rollback..."
        })
        for patch, target_file, backup_file in applied_targets:
            if os.path.exists(backup_file):
                shutil.copy2(backup_file, target_file)

        importlib.reload(sm)
        importlib.reload(pm)
        importlib.reload(am)
        importlib.reload(sec_m)
        target_app.project_mgr = pm.ProjectManager()
        target_app.project_mgr.active_project = old_active_proj
        target_app.project_mgr.reinit()
        target_app.session_mgr = sm.SessionManager()
        target_app.security_mgr = sec_m.SecurityManager()
        if not is_busy:
            target_app.agent_mgr = am.AgentTaskManager(project_manager=target_app.project_mgr)
            target_app.agent_mgr.connected_clients = active_clients

        await target_app.agent_mgr.broadcast({
            "type": "system",
            "level": "warning",
            "message": "🔄 Rollback complete. Previous stable state restored from core/backups/."
        })
        return {"success": False, "error": f"Patch failed and rolled back: {e}"}

@system_bp.route('/api/reload', methods=['POST'])
async def reload_system():
    try:
        app_obj = current_app._get_current_object()
        res = await execute_hot_patch_sequence(app_obj=app_obj, manual_trigger=True, fast_countdown=True)
        if isinstance(res, dict) and not res.get("success", True):
            return jsonify(res), 500
        return jsonify({
            "success": True,
            "message": "Backend hot-patched and reloaded!",
            "details": res.get("message") if isinstance(res, dict) else "OK",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@system_bp.route('/api/simulate-patch', methods=['POST'])
async def trigger_hot_patch():
    app_obj = current_app._get_current_object()
    asyncio.create_task(execute_hot_patch_sequence(app_obj=app_obj, manual_trigger=True, fast_countdown=False))
    return jsonify({"success": True, "message": "Hot-patch verification & reload sequence initiated."})

@system_bp.route('/api/bootstrap/preflight', methods=['GET', 'POST'])
async def api_bootstrap_preflight():
    try:
        from core.bootstrap_gateway import run_preflight_checks
        report = run_preflight_checks(spawn_agent=False, exit_on_failure=False, quiet=True)
        status_code = 200 if report.get("success") else 500
        return jsonify(report), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@system_bp.route('/api/security/csp-report', methods=['POST'])
async def csp_report():
    import json
    from datetime import datetime
    try:
        report = await request.get_json(force=True)
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "report": report.get("csp-report", report)
        }
        with open("csp_violations.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        print("[Security] CSP Violation Logged")
    except Exception as e:
        print(f"[Security] Failed to log CSP violation: {e}")
    return jsonify({"success": True}), 204

@system_bp.route('/api/security/red-team-strike', methods=['POST'])
async def api_trigger_red_team():
    user = get_current_user()
    if not user or user.get("role") not in ["super_admin", "Tier5_SysAdmin"]:
        return jsonify({"error": "Access Denied: Red Team strikes require Tier 5 Admin authorization."}), 403
        
    asyncio.create_task(trigger_dast_scan_internal())
    return jsonify({"success": True, "message": "Red Team strike initiated."})

@system_bp.route('/api/security/jit-status', methods=['GET'])
async def api_jit_status():
    try:
        from security.jit_elevation import get_jit_status
        return jsonify({"success": True, **get_jit_status()})
    except Exception as e:
        return jsonify({"success": False, "active": False, "error": str(e)}), 500

@system_bp.route('/api/security/jit-elevate', methods=['POST'])
async def api_jit_elevate():
    user = get_current_user()
    has_master_sig = current_app.security_mgr.check_master_signature()
    if not has_master_sig or (user and user.get("role") not in ["super_admin", "admin", "Tier5_SysAdmin"]):
        return jsonify({"success": False, "error": "Access Denied: Super Admin hardware signature & authorization required."}), 403

    try:
        is_busy = False
        if hasattr(current_app, "agent_mgr") and current_app.agent_mgr:
            is_busy = current_app.agent_mgr.is_running()

        if is_busy:
            msg = "Policy Violation: JIT Elevation request ignored because an agent is currently busy executing an active task."
            solution = "Wait for the active agent to complete its execution or cancel the running task before requesting JIT Elevation."
            if hasattr(current_app, "agent_mgr"):
                await current_app.agent_mgr.broadcast({
                    "type": "system",
                    "level": "error",
                    "message": f"⚠️ {msg} Solution: {solution}"
                })
            return jsonify({
                "success": False,
                "error": msg,
                "solution": solution,
                "policy_violation": True
            }), 409

        data = await request.get_json(silent=True) or {}
        ttl_seconds = int(data.get("ttl_seconds", 300))

        bound_agent_id = (
            data.get("agent_id")
            or data.get("conversation_id")
            or getattr(getattr(current_app, "agent_mgr", None), "current_conversation_id", None)
            or "1b00c340-8c19-4a13-a7b9-d85a0799fc83"
        )

        import inspect
        from security.jit_elevation import mint_jit_token
        sig_params = inspect.signature(mint_jit_token).parameters
        mint_kwargs = {
            "ttl_seconds": ttl_seconds,
            "issued_by": "web_ui",
            "active_session_lift": True,
        }
        if "agent_id" in sig_params:
            mint_kwargs["agent_id"] = bound_agent_id
        if "conversation_id" in sig_params:
            mint_kwargs["conversation_id"] = bound_agent_id

        res = mint_jit_token(**mint_kwargs)
        res["bound_agent_id"] = bound_agent_id
        if hasattr(current_app, "agent_mgr"):
            await current_app.agent_mgr.broadcast({
                "type": "system",
                "level": "warning",
                "message": f"🔓 SUPER ADMIN JIT ELEVATION ACTIVE ({res['ttl_seconds']}s): Bound to Agent '{bound_agent_id}'. Core security guard files are temporarily unlocked for patching."
            })
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@system_bp.route('/api/security/jit-revoke', methods=['POST'])
async def api_jit_revoke():
    user = get_current_user()
    has_master_sig = current_app.security_mgr.check_master_signature()
    if not has_master_sig or (user and user.get("role") not in ["super_admin", "admin", "Tier5_SysAdmin"]):
        return jsonify({"success": False, "error": "Access Denied: Super Admin authorization required."}), 403

    try:
        from security.jit_elevation import revoke_jit_token
        res = revoke_jit_token(revoked_by="web_ui")
        if hasattr(current_app, "agent_mgr"):
            await current_app.agent_mgr.broadcast({
                "type": "system",
                "level": "info",
                "message": "🔒 SUPER ADMIN JIT ELEVATION REVOKED: Core security guard files are now re-locked."
            })
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@system_bp.route('/telemetry', methods=['GET'])
@system_bp.route('/plugin/telemetry', methods=['GET'])
async def telemetry_page():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(repo_root, "sandbox", "templates", "telemetry.html"),
        os.path.join(repo_root, "templates", "telemetry.html"),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            return content, 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Telemetry template not found", 404

@system_bp.route('/api/telemetry/tokens', methods=['GET'])
async def api_token_telemetry():
    try:
        import core.token_telemetry as tt
        engine = tt.get_telemetry_engine()
        tf = request.args.get("timeframe", "all")
        force = request.args.get("force", "false").lower() == "true"
        data = await asyncio.to_thread(engine.get_telemetry_data, requested_timeframe=tf, force_refresh=force)
        return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@system_bp.route('/audits', methods=['GET'])
async def audits_page():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(repo_root, "sandbox", "templates", "audits.html"),
        os.path.join(repo_root, "templates", "audits.html"),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            return content, 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Audits template not found", 404


@system_bp.route('/api/audits', methods=['GET'])
async def api_get_audits():
    try:
        registry = get_audit_registry()
        catalog = registry.get_catalog()
        return jsonify({"success": True, "audits": catalog})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@system_bp.route('/api/audits/results/<audit_id>', methods=['GET'])
async def api_audit_result(audit_id):
    try:
        registry = get_audit_registry()
        data = registry.get_audit(audit_id)
        if not data:
            return jsonify({"success": False, "error": f"Audit '{audit_id}' not found"}), 404
        return jsonify({"success": True, "audit": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@system_bp.route('/api/audits/run', methods=['POST'])
async def api_run_audit():
    try:
        data = await request.get_json(silent=True) or {}
        audit_id = data.get("audit_id", "all")
        registry = get_audit_registry()
        if audit_id == "all":
            results = await registry.run_all_audits()
            return jsonify({"success": True, "results": results})
        else:
            res = await registry.run_audit(audit_id)
            status_code = 200 if res.get("success") else 500
            return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@system_bp.route('/api/audits/refresh', methods=['POST'])
async def api_refresh_audits():
    try:
        registry = get_audit_registry()
        registry.discover_audits()
        catalog = registry.get_catalog()
        return jsonify({"success": True, "audits": catalog, "message": "Audits re-scanned successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
