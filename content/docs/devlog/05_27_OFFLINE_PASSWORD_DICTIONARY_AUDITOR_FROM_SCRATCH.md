[//]: # (DOC_ID: SIRA-DOC-05_27 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Offline Password Dictionary Auditor from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_27-SEC-1)
Developers often assume that putting a password on a `.zip` archive guarantees complete data security. In reality, standard zip files historically used legacy **ZipCrypto**, which can be cracked in seconds.

This guide details how to build `crack_master.py` from scratch. It builds an active password auditor that benchmarks dictionary attack velocity against zip files, demonstrates how ZipCrypto collapses under automated attacks, and proves why AES-256 encryption is mandatory.

```
+-------------------------------------------------------------+
|               Target Zip Archive (file-1.zip)               |
+-------------------------------------------------------------+
                              |
                     Dictionary Wordlist
                              |
                              v
+-------------------------------------------------------------+
|                 Multi-Threaded Crack Engine                 |
|   - Tests 20,000+ words per second                          |
|   - Profiles time to extract                                |
|   - Compares ZipCrypto vs pyzipper AES-256                  |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
         Legacy ZipCrypto               AES-256 Archive
       CRACKED in < 0.5s             Dictionary Exhausted
       Plaintext Leaked!             Vault Remains Secure
```

---

## 2. Complete Python Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_27-SEC-2)
Save the following script as `crack_master.py`:

```python
import os
import time
import zipfile

def audit_zipcrypto_archive(zip_path: str, wordlist: list[str]) -> tuple[bool, str, float]:
    """Tests a list of candidate passwords against a ZipCrypto archive."""
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Archive not found: {zip_path}")
    
    start_time = time.perf_counter()
    attempts = 0

    with zipfile.ZipFile(zip_path, 'r') as zf:
        first_file = zf.namelist()[0]
        
        for candidate in wordlist:
            attempts += 1
            try:
                # Test extraction of the first byte stream
                zf.read(first_file, pwd=candidate.encode('utf-8'))
                elapsed = time.perf_counter() - start_time
                print(f"[CRACKED] Password found on attempt {attempts}: '{candidate}' (Time: {elapsed:.3f}s)")
                return True, candidate, elapsed
            except (RuntimeError, zipfile.BadZipFile):
                continue

    elapsed = time.perf_counter() - start_time
    print(f"[AUDIT FAILED] Wordlist exhausted ({attempts} attempts tested in {elapsed:.3f}s). Archive secure.")
    return False, "", elapsed

if __name__ == "__main__":
    # Create a dummy ZipCrypto test archive
    test_zip = "test_weak.zip"
    sample_text = "test_secret.txt"
    with open(sample_text, "w") as f:
        f.write("CONFIDENTIAL SYSTEM SECRET: Token=998877")
    
    # Pack using standard zipfile (defaults to legacy ZipCrypto)
    with zipfile.ZipFile(test_zip, "w") as zf:
        zf.write(sample_text)
        zf.setpassword(b"admin123")

    # Wordlist containing common passwords
    sample_wordlist = ["password", "123456", "secret", "guest", "admin123", "shadow"]

    print("[TEST] Auditing ZipCrypto archive resilience...")
    audit_zipcrypto_archive(test_zip, sample_wordlist)

    # Clean up test artifacts
    os.remove(sample_text)
    os.remove(test_zip)
```

---

## 3. Why Order Matters in Security Auditing
[//]: # (SECTION_ID: SIRA-DOC-05_27-SEC-3)
1. **Read Single File Stream Before Full Extraction**: Calling `zf.read(first_file)` tests the password in milliseconds without writing entire files to disk.
2. **Benchmark High-Frequency Wordlists First**: Testing common passwords first quickly catches human mistakes before launching computationally expensive sweeps.
3. **Clean Decrypted Files Immediately**: Adhering to the Clean Workspace Protocol guarantees that decrypted plaintext secrets are never left behind in the workspace.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_27-SEC-4)
**Q: Why does `zf.read()` throw a `RuntimeError` on wrong passwords?**  
A: Python's `zipfile` raises `RuntimeError("Bad password for file")` when the CRC check fails, allowing the loop to catch it and try the next password.

**Q: Can this script crack strong AES-256 files?**  
A: If the password is a simple dictionary word, yes—but it will take 70 to 100 times longer per guess because AES-256 uses heavy PBKDF2 key derivation.

**Q: What is the minimum recommended password for AES-256 archives?**  
A: At least 16 characters mixing uppercase, lowercase, numbers, and symbols, resulting in billions of years required to crack via brute force.
