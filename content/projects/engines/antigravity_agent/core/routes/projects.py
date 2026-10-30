import asyncio
from core.routes.auth import get_current_user
from quart import Blueprint, request, jsonify, current_app, Response
import os, json, asyncio

projects_bp = Blueprint('projects_bp', __name__)

@projects_bp.route('/api/projects', methods=['GET'])
async def list_projects():
    user = get_current_user()
    current_app.project_mgr.get_active_workspace_path()
    projects = current_app.project_mgr.list_projects(user=user)
    active = current_app.project_mgr.active_project
    root_name = "Workspaces"
    return jsonify({"projects": projects, "active": active, "root_name": root_name})

@projects_bp.route('/api/projects', methods=['POST'])
async def create_project():
    user = get_current_user()
    if user and user.get("role") == "modder":
        return jsonify({"error": "Access Denied: Modder role has read-only permissions"}), 403
    data = await request.get_json() or {}
    name = (data.get('name') or '').strip()
    try:
        current_app.project_mgr.create_project(name)
        return jsonify({"success": True, "project": name})
    except (ValueError, FileExistsError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400

@projects_bp.route('/api/projects/active', methods=['POST'])
async def set_active_project():
    user = get_current_user()
    data = await request.get_json() or {}
    name = data.get('name')
    if name:
        name = name.strip()
    if user and name and not current_app.security_mgr.can_access_project(user, name):
        return jsonify({"error": "Access Denied: You do not have permission for this project"}), 403
    try:
        p = current_app.project_mgr.set_active_project(name)
        return jsonify({"success": True, "active": current_app.project_mgr.active_project, "path": p})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@projects_bp.route('/api/conversations', methods=['GET'])
async def list_conversations():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    limit = request.args.get('limit', default=10, type=int)
    current_app.project_mgr.get_active_workspace_path()
    convos, has_more = await asyncio.to_thread(
        current_app.session_mgr.list_conversations,
        current_app.project_mgr.active_project,
        user,
        limit
    )
    return jsonify({"conversations": convos, "has_more": has_more})

@projects_bp.route('/api/conversations/<conv_id>', methods=['GET'])
async def get_conversation(conv_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    rename_to = request.args.get('rename')
    if rename_to is not None:
        ok = await asyncio.to_thread(current_app.session_mgr.rename_session, conv_id, rename_to, user)
        if not ok:
            return jsonify({"error": "Failed to rename session"}), 400
        return jsonify({"success": True, "title": rename_to.strip()})
    try:
        items = await asyncio.to_thread(current_app.session_mgr.get_conversation_transcript, conv_id, user)
        rollover = await asyncio.to_thread(current_app.session_mgr.get_rollover_info, conv_id, user)
        return jsonify({"items": items, "rollover": rollover})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@projects_bp.route('/api/conversations/<conv_id>/rename', methods=['POST'])
async def rename_conversation(conv_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = await request.get_json() or {}
    new_title = (data.get('title') or data.get('name') or '').strip()
    if not new_title:
        return jsonify({"error": "Title is required"}), 400
    try:
        ok = await asyncio.to_thread(current_app.session_mgr.rename_session, conv_id, new_title, user)
        if ok:
            return jsonify({"success": True, "title": new_title})
        return jsonify({"error": "Access Denied or invalid session"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@projects_bp.route('/api/conversations/<conv_id>', methods=['DELETE'])
async def delete_conversation(conv_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        success = await asyncio.to_thread(current_app.session_mgr.delete_session, conv_id, user)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to delete"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@projects_bp.route('/api/projects/active/conversations', methods=['DELETE'])
async def clear_project_sessions():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    current_app.project_mgr.get_active_workspace_path()
    active_proj = current_app.project_mgr.active_project

    try:
        await asyncio.to_thread(current_app.session_mgr.delete_project_sessions, active_proj, user)
        return jsonify({"success": True, "project": active_proj})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

