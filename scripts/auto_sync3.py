import subprocess
import time
import requests

print("Waiting for tmux push to finish...")
while True:
    res = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    if "git_push_10" not in res.stdout:
        break
    time.sleep(5)

print("Push finished! Triggering sync...")
s = requests.Session()
url_login = 'https://mikeymike.pythonanywhere.com/login'
url_sync = 'https://mikeymike.pythonanywhere.com/api/projects/explorer_logic/git_sync'

s.post(url_login, data={'token': 'Mike'})
print("Sync 1...")
r1 = s.post(url_sync)
print(r1.text)
time.sleep(10)
print("Sync 2...")
r2 = s.post(url_sync)
print(r2.text)
print("ALL DONE!")
