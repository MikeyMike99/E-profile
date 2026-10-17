# KMS Keychain & Cold Storage Source Evidence

## 1. Architectural Role & File Location
This document records source code evidence from `security/keychain.py` and `security/cold_storage.py`. It demonstrates how the system protects brain session transcripts using an enterprise Key Management Service (KMS) hierarchy and atomic cold-storage encryption.

---

## 2. KEK Derivation & Keychain Evidence
`security/keychain.py` derives a Key Encryption Key (KEK) using PBKDF2 with 100,000 iterations to protect an array of Data Encryption Keys (DEKs):

```python
# security/keychain.py: Lines 19-35
def _derive_kek(self):
    if not os.path.exists(self.master_key_path):
        raise FileNotFoundError("CRITICAL: .devcore_master.key missing. Cannot unlock keychain.")
    with open(self.master_key_path, "r", encoding="utf-8") as f:
        raw_master = f.read().strip().encode('utf-8')
        
    # Use PBKDF2 to derive a strong AES Key Encryption Key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'devcore_static_salt_for_kek', 
        iterations=100000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(raw_master)))

def get_all_ciphers(self) -> list[Fernet]:
    """Returns Fernet ciphers for all historical DEKs to enable backwards-compatible decryption."""
    ciphers = []
    for wrapped_key in self.keychain_data.get("keys", []):
        decrypted_key = self.kek.decrypt(wrapped_key.encode('utf-8'))
        ciphers.append(Fernet(decrypted_key))
    return ciphers
```

---

## 3. Atomic Cold Storage Locking Evidence
`security/cold_storage.py` searches brain transcripts, avoids double encryption, and atomically swaps ciphertext into place:

```python
# security/cold_storage.py: Lines 11-40
def lock_brain():
    """Encrypts all transcript files in the brain using the Active DEK."""
    brain_dir = get_brain_dir()
    km = KeychainManager()
    cipher = km.get_active_cipher()

    search_pattern = os.path.join(brain_dir, "**", "transcript*.jsonl")
    for file_path in glob.glob(search_pattern, recursive=True):
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Guard against double encryption
            if data.startswith(b'gAAAAA'): 
                continue
                
            encrypted = cipher.encrypt(data)
            
            # Atomic file swap via mkstemp + os.replace
            import tempfile
            fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), prefix=".secure_lock_")
            with os.fdopen(fd, 'wb') as f:
                f.write(encrypted)
            os.replace(tmp_path, file_path) # Atomic swap
            print(f"[Cold Storage] Locked: {file_path}")
        except Exception as e:
            print(f"[Cold Storage Error] Failed to lock {file_path}: {e}")
```

---

## 4. Multi-Key Decryption Evidence
When unlocking cold storage, the engine cycles through historical ciphers until a matching key decrypts the token:

```python
# security/cold_storage.py: Decrypting historical sessions
for cipher in ciphers:
    try:
        decrypted = cipher.decrypt(data)
        break
    except InvalidToken:
        continue
```

---

## 5. Why Order Matters in Cryptographic Locking
1. **Derive KEK Before Loading Keychain**: The master key must be verified and transformed via PBKDF2 before `keychain.json` can be parsed.
2. **Check Ciphertext Prefix Before Writing**: Verifying `b'gAAAAA'` prevents corrupted nested Fernet tokens.
3. **Write Complete Data Before `os.replace`**: Closing the temporary file handle before executing `os.replace` ensures Windows does not raise file lock errors (`PermissionError`).

---

## 6. Beginner Coder Q&A
**Q: What is `b'gAAAAA'`?**  
A: Every token encrypted with Python's `cryptography.fernet` begins with `gAAAAA` in base64, indicating version 0x80 and a valid timestamp header.

**Q: Why put the temporary file in the same directory (`os.path.dirname(file_path)`)?**  
A: `os.replace` is only atomic if the source and destination are on the exact same physical disk partition!

**Q: What happens if an old key was deleted from the keychain?**  
A: If a DEK is deleted, any transcript encrypted with that key becomes permanently undecryptable.
