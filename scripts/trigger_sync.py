import requests
import time

s = requests.Session()
url_login = 'https://mikeymike.pythonanywhere.com/login'
url_sync = 'https://mikeymike.pythonanywhere.com/api/projects/explorer_logic/git_sync'

# 1. Login
print("Logging in...")
resp = s.post(url_login, data={'token': 'Mike'})
print("Login status:", resp.status_code)

# 2. Sync 1
print("Sync 1...")
r1 = s.post(url_sync)
print(r1.text)

time.sleep(5)

# 3. Sync 2
print("Sync 2...")
r2 = s.post(url_sync)
print(r2.text)

