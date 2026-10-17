import requests
s = requests.Session()
s.post('https://mikeymike.pythonanywhere.com/login', data={'token': 'Mike'})
r2 = s.get('https://mikeymike.pythonanywhere.com/api/projects/execute/pwned')
print(r2.status_code, r2.text)
