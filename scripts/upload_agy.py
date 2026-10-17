import requests
import base64
import os

print("Authenticating...")
s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

print("Deploying receiver script...")
receiver_code = """
import os, sys, base64
chunk = sys.stdin.read().strip()
if chunk == "RESET":
    if os.path.exists("/home/MikeyMike/.local/bin/agy"):
        os.remove("/home/MikeyMike/.local/bin/agy")
    print("Reset complete")
elif chunk == "FINISH":
    os.system("chmod +x /home/MikeyMike/.local/bin/agy")
    print("Finished!")
else:
    os.makedirs("/home/MikeyMike/.local/bin", exist_ok=True)
    with open("/home/MikeyMike/.local/bin/agy", "ab") as f:
        f.write(base64.b64decode(chunk))
    print("Appended chunk")
"""
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={
    "project": "pwned",
    "file": "server.py", # Using server.py so it's persistent
    "code": receiver_code
})

print("Wait, execute_project runs python without stdin? We need to use apply_patch!")
