import requests

s = requests.Session()
url_login = 'https://mikeymike.pythonanywhere.com/login'
url_sync = 'https://mikeymike.pythonanywhere.com/api/projects/explorer_logic/git_sync'

resp = s.post(url_login, data={'token': 'Mike'})
print("Login status:", resp.status_code)
print("Cookie:", s.cookies.get_dict())

r1 = s.post(url_sync)
print("Sync 1:", r1.status_code)
print("Output:", r1.text)

