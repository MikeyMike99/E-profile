import requests

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})
r = s.post('https://mikeymike.pythonanywhere.com/ai_agent/api/chat', json={"prompt": "boot"})
print("Status:", r.status_code)
print("Response:", r.text)
