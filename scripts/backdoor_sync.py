import requests

s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})
r = s.post('https://mikeymike.pythonanywhere.com/api/projects/explorer_logic/terminal', json={"command": "setup -get new MikeyMike99/E-profile"})
print("Status:", r.status_code)
print("Output:", r.text)
