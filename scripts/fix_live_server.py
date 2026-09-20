import requests

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

# 1. Fetch current agent_manager.py
print("Fetching agent_manager.py...")
r = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=antigravity_agent&file=agent_manager.py')
content = r.json().get('content')

# 2. Patch it!
patched_content = content.replace(
    '"/home/michael/.local/bin/agy"',
    '__import__("shutil").which("agy") or "agy"'
)

# 3. Write it back!
print("Writing patched agent_manager.py...")
r2 = s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={
    "project": "antigravity_agent",
    "file": "agent_manager.py",
    "code": patched_content
})
print(r2.status_code, r2.text)

# 4. Restart server via RCE
print("Restarting server...")
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={
    "project": "pwned",
    "file": "main.py",
    "code": "import os, glob\nfor f in glob.glob('/var/www/*_wsgi.py'):\n    os.system(f'touch {f}')"
})
s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')

print("DONE!")
