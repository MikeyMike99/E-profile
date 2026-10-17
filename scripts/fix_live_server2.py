import requests

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

print("Fetching agent_manager.py...")
r = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=antigravity_agent&file=agent_manager.py')
content = r.json().get('content')

# Patch it to look in Mike's home too
patched_content = content.replace(
    '__import__("shutil").which("agy") or "agy"',
    '__import__("shutil").which("agy") or "/home/MikeyMike/.local/bin/agy"'
)

print("Writing patched agent_manager.py...")
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={
    "project": "antigravity_agent",
    "file": "agent_manager.py",
    "code": patched_content
})

print("Restarting server...")
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={
    "project": "pwned",
    "file": "main.py",
    "code": "import os, glob\nfor f in glob.glob('/var/www/*_wsgi.py'):\n    os.system(f'touch {f}')"
})
s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')

print("DONE!")
