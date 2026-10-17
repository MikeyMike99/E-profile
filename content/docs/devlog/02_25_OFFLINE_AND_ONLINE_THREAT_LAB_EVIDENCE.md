[//]: # (DOC_ID: SIRA-DOC-02_25 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Active Threat Lab (Offline Crack & Online Brute) Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_25-SEC-1)
This document records source code evidence from the active penetration testing laboratories located in `playground/Offline_Crack_Lab/crack_master.py` and `playground/Online_Brute_Lab/brute_api.py`. These scripts validate password hashing resilience, zip archive encryption resistance, and API rate-limiting thresholds.

---

## 2. Offline Dictionary Cracking Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_25-SEC-2)
`crack_master.py` tests password cracking velocity against ZipCrypto vs AES-256 encrypted archives:

```python
# playground/Offline_Crack_Lab/crack_master.py: Benchmark engine
import time
import zipfile
import pyzipper
from concurrent.futures import ThreadPoolExecutor

def test_zipcrypto_crack(zip_path: str, wordlist: list[str]) -> tuple[bool, str, float]:
    """Attempts dictionary attack against legacy ZipCrypto."""
    start_time = time.perf_counter()
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for word in wordlist:
            try:
                zf.extractall(pwd=word.encode('utf-8'))
                elapsed = time.perf_counter() - start_time
                return True, word, elapsed
            except (RuntimeError, zipfile.BadZipFile):
                continue
    return False, "", time.perf_counter() - start_time

def test_aes256_crack(zip_path: str, wordlist: list[str]) -> tuple[bool, str, float]:
    """Attempts dictionary attack against modern AES-256 zip."""
    start_time = time.perf_counter()
    with pyzipper.AESZipFile(zip_path, 'r') as zf:
        for word in wordlist:
            try:
                zf.extractall(pwd=word.encode('utf-8'))
                elapsed = time.perf_counter() - start_time
                return True, word, elapsed
            except Exception:
                continue
    return False, "", time.perf_counter() - start_time
```

---

## 3. Online API Brute-Force Simulation Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_25-SEC-3)
`brute_api.py` verifies that the authentication gateway actively blocks rapid dictionary guessing:

```python
# playground/Online_Brute_Lab/brute_api.py: Rate limit verifier
import urllib.request
import json
import time

TARGET_URL = "http://127.0.0.1:5000/api/auth/login"

def simulate_brute_force_attack(attempts: int = 10):
    """Verifies that API drops connections after 5 consecutive bad tokens."""
    print(f"[TEST] Launching {attempts} rapid authentication guesses...")
    for i in range(attempts):
        guess_token = f"AGY-DEPLOY-FAKE{i:04d}"
        payload = json.dumps({"token": guess_token}).encode('utf-8')
        req = urllib.request.Request(TARGET_URL, data=payload, headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f"Attempt {i+1}: HTTP {resp.status} - {data.get('message')}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"Attempt {i+1}: HTTP 429 TOO MANY REQUESTS! Rate limiter successfully engaged.")
                return True
            print(f"Attempt {i+1}: HTTP {e.code}")
    return False
```

---

## 4. Why Order Matters in Threat Simulation
[//]: # (SECTION_ID: SIRA-DOC-02_25-SEC-4)
1. **Test Offline Resilience Before Network Exposure**: Confirming that sensitive backups use AES-256 ensures an attacker who steals an archive cannot read it offline.
2. **Handle Exceptions Gracefully During Wordlist Sweeps**: Catching `RuntimeError` and `BadZipFile` without terminating the process allows testing thousands of passwords per second.
3. **Trigger Rate Limiting Before Resource Exhaustion**: The API gateway must return HTTP 429 before CPU-heavy PBKDF2 hashing routines exhaust server thread pools.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_25-SEC-5)
**Q: Why does ZipCrypto crack so much faster than AES-256?**  
A: ZipCrypto uses a lightweight CRC32-based stream cipher designed in 1989 for slow 386 computers. Modern CPUs can test millions of ZipCrypto keys per second.

**Q: What is `time.perf_counter()`?**  
A: A high-resolution Python timer that measures elapsed time with nanosecond accuracy, perfect for benchmarking cryptography.

**Q: How does `pyzipper` handle AES encryption?**  
A: It integrates standard AES-128 and AES-256 with PBKDF2-HMAC-SHA1 key derivation, mathematically protecting archive contents.
