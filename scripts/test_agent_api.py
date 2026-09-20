import requests
import time

s = requests.Session()
# Don't strictly need to login if we just hit /api/chat as a guest, but let's login to be safe
print("Logging in...")
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})

print("Sending /api/chat...")
r = s.post('https://mikeymike.pythonanywhere.com/api/chat', json={"prompt": "boot"})
print("Chat status:", r.status_code)
print("Chat response:", r.text)

print("Polling /api/stream 3 times...")
for i in range(3):
    time.sleep(2)
    r2 = s.get('https://mikeymike.pythonanywhere.com/api/stream')
    print(f"Stream {i} status:", r2.status_code)
    print(f"Stream {i} response:", r2.text)

