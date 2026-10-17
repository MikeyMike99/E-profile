# Active Threat Simulation: ZipCrypto vs AES-256 Traps

## 1. The Problem: The False Security of Legacy Zip Encryption
Developers frequently archive sensitive project files, database backups, or API keys into password-protected `.zip` files, assuming that any password-protected archive is cryptographically secure.

However, standard zip software (including built-in Windows Zip compression) historically defaults to **ZipCrypto** (the original 1989 PKWARE encryption standard). ZipCrypto contains fatal mathematical weaknesses in its stream cipher that allow attackers to break the encryption in seconds using known-plaintext attacks or dictionary sweeps.

```
+-------------------------------------------------------------+
|              Legacy Archive (ZipCrypto Encryption)          |
|                 Password: "supersecret123"                  |
+-------------------------------------------------------------+
                              |
                     Attacker Runs fcrackzip
                              |
                              v
+-------------------------------------------------------------+
|              Cracked in 0.42 Seconds (Plaintext Leaked)     |
|   Fatal Flaw: 3 32-bit CRC-based state keys easily broken   |
+-------------------------------------------------------------+
```

---

## 2. The Offline Crack Lab Simulation
To prove this vulnerability to developers in training, DevCore established the Active Threat Simulation Lab (`playground/Offline_Crack_Lab/crack_master.py`) and packaged sample archives (`playground/Zip-Files/`):
- `file-1.zip` through `file-3.zip`: Encrypted with standard ZipCrypto. The simulation lab cracked them in less than 500 milliseconds using basic wordlists.
- `file-4.zip` through `file-6.zip`: Encrypted with AES-256 using `pyzipper`. The simulation lab verified that dictionary attacks failed completely, demonstrating mathematical resistance.

---

## 3. The Solution: Enforcing AES-256 & Argon2id Vaults
Siraugga established strict zero-trust rules for all archived assets:
1. **Hard Prohibition of ZipCrypto**: Any archive created or ingested using legacy ZipCrypto triggers an immediate security alert in `central_logger.py`.
2. **Standardization on AES-256**: All encrypted backup files and forensic archives must use AES-256 via modern libraries like `pyzipper`.
3. **Key Derivation Hardening**: Passwords must be strengthened using PBKDF2 or Argon2id with high work factors, preventing GPU-accelerated hash cracking.

---

## 4. Why Order Matters in Threat Simulation
1. **Simulate Offline Attacks Before Exposing APIs**: Testing file encryption resilience in offline sandboxes reveals vulnerabilities before malicious actors probe production endpoints.
2. **Verify Cipher Type Before Password Strength**: A 20-character password on a ZipCrypto archive is still vulnerable to known-plaintext recovery; cipher modernness must precede password complexity.
3. **Purge Plaintext Samples Immediately After Testing**: Decrypted test files must be deleted from memory and disk immediately following verification to adhere to the Clean Workspace Protocol.

---

## 5. Beginner Coder Q&A
**Q: What is the difference between ZipCrypto and AES-256?**  
A: ZipCrypto uses a legacy, broken 96-bit internal state with known mathematical flaws. AES-256 is the gold-standard Advanced Encryption Standard approved by NIST for classified data.

**Q: Can Python's built-in `zipfile` module create AES-256 archives?**  
A: No! Python's standard `zipfile` only supports legacy ZipCrypto for writing. To write AES-256 encrypted zip files, you must use modern packages like `pyzipper`.

**Q: What is a known-plaintext attack?**  
A: If an attacker possesses just 12 bytes of unencrypted data from any file inside the zip (such as a standard file header), they can mathematically derive the internal encryption keys without guessing the password!
