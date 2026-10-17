import re
with open("content/projects/engines/antigravity_agent/agent_manager.py", "r") as f:
    code = f.read()

# Fix the syntax error I just made
code = code.replace('import shutil; shutil.which("agy") or "agy"', 'import shutil\n            agy_path = shutil.which("agy") or "agy"\n            cmd = [\n                agy_path')
# Replace the original if it wasn't replaced
code = code.replace('"/home/michael/.local/bin/agy"', 'import shutil\n            agy_path = shutil.which("agy") or "agy"\n            cmd = [\n                agy_path')

with open("content/projects/engines/antigravity_agent/agent_manager.py", "w") as f:
    f.write(code)
