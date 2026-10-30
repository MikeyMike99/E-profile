import asyncio
from core.routes.auth import get_current_user
from quart import Blueprint, request, jsonify, current_app, Response
import os, json

files_bp = Blueprint('files_bp', __name__)

@files_bp.route('/api/files', methods=['GET'])
async def list_files():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    workspace = current_app.project_mgr.get_active_workspace_path()
    if not current_app.security_mgr.can_access_project(user, current_app.project_mgr.active_project):
        return jsonify({"error": "Access Denied: You do not have permission for this workspace"}), 403
    files = await asyncio.to_thread(current_app.security_mgr.list_files, workspace, user=user)
    return jsonify({"workspace": workspace, "files": files, "user": user})



@files_bp.route('/api/files/content', methods=['GET'])
async def get_file_content():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    path = request.args.get('path', '')
    workspace = current_app.project_mgr.get_active_workspace_path()
    if not current_app.security_mgr.can_access_project(user, current_app.project_mgr.active_project):
        return jsonify({"error": "Access Denied: You do not have permission for this workspace"}), 403
    try:
        data = await asyncio.to_thread(current_app.security_mgr.read_file_content, workspace, path, user=user)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 403



@files_bp.route('/api/files/content', methods=['POST'])
async def save_file_content():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = await request.get_json() or {}
    path = data.get('path')
    content = data.get('content', '')
    workspace = current_app.project_mgr.get_active_workspace_path()
    if not current_app.security_mgr.can_access_project(user, current_app.project_mgr.active_project):
        return jsonify({"error": "Access Denied: You do not have permission for this workspace"}), 403
    try:
        result = await asyncio.to_thread(current_app.security_mgr.write_file_content, workspace, path, content, user=user)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 403



@files_bp.route('/api/logs', methods=['GET'])
async def list_logs():
    user = get_current_user()
    if not user or not current_app.security_mgr.can_view_logs(user):
        return jsonify({"error": "Access Denied: Admin role required to view system logs"}), 403
    try:
        logs = await asyncio.to_thread(current_app.security_mgr.list_logs, user=user)
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 400



@files_bp.route('/api/logs/<log_name>', methods=['GET'])
async def get_log_content(log_name):
    user = get_current_user()
    if not user or not current_app.security_mgr.can_view_logs(user):
        return jsonify({"error": "Access Denied: Admin role required to view system logs"}), 403
    try:
        data = await asyncio.to_thread(current_app.security_mgr.read_file_content, current_app.security_mgr.base_dir, log_name, user=user)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 403


