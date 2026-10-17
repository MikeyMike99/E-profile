with open("content/projects/engines/antigravity_agent/ai_plugin.py", "r") as f:
    content = f.read()

replacement = """    if agent_mgr.is_running():
        # Instead of rejecting, send it as stdin input to the running agent setup
        asyncio.run_coroutine_threadsafe(
            agent_mgr.send_input(prompt), 
            ai_loop
        )
        return jsonify({"success": True, "message": "Input sent to agent"})"""

content = content.replace("    if agent_mgr.is_running():\n        return jsonify({\"success\": False, \"error\": \"Agent is currently busy.\"})", replacement)

with open("content/projects/engines/antigravity_agent/ai_plugin.py", "w") as f:
    f.write(content)
