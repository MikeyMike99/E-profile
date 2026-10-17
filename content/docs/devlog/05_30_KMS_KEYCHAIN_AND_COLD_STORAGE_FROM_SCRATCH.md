[//]: # (DOC_ID: SIRA-DOC-05_30 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# KMS Keychain & Cold Storage from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_30-SEC-1)
Relying on a single static encryption key creates total vulnerability if the key is exposed, while rotating keys naively causes historical files to become unreadable.

This guide details how to build `keychain_storage.py` from scratch. It implements an enterprise two-tier Key Management Service (KMS) that derives a Key Encryption Key (KEK) using PBKDF2HMAC, wraps multiple Data Encryption Keys (DEKs) in a JSON keychain, and executes atomic cold-storage encryption across files.

```
+-------------------------------------------------------------+
|               Master Key File (.master.key)                 |
+-------------------------------------------------------------+
                              |
                     PBKDF2HMAC (100,000 rounds)
                              |
                              v
+-------------------------------------------------------------+
|               Key Encryption Key (KEK / Fernet)             |
+-------------------------------------------------------------+
                              |
                     Unwraps Key Array
                              |
                              v
+-------------------------------------------------------------+
|               keychain.json (Historical DEK Array)          |
|   [Wrapped DEK-1], [Wrapped DEK-2], [Active DEK]            |
+-------------------------------------------------------------+
                              |
                     Cold Storage Operations
                              |
               +--------------+--------------+
               |                             |
          lock_files()                 unlock_files()
       Atomic swap via               Iterates cipher ring
      mkstemp + os.replace           until match is found
```

---

## 2. Complete Python Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_30-SEC-2)
Save the following script as `keychain_storage.py`:

```python
import os
import json
import base64
import tempfile
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MASTER_KEY_FILE = ".master.key"
KEYCHAIN_FILE = "keychain.json"

class KeychainManager:
    def __init__(self, master_path: str = MASTER_KEY_FILE, keychain_path: str = KEYCHAIN_FILE):
        self.master_path = master_path
        self.keychain_path = keychain_path
        self._ensure_master_key()
        self.kek = self._derive_kek()
        self.keys = self._load_or_init_keychain()

    def _ensure_master_key(self):
        if not os.path.exists(self.master_path):
            with open(self.master_path, "w") as f:
                f.write(Fernet.generate_key().decode('utf-8'))

    def _derive_kek(self) -> Fernet:
        with open(self.master_path, "r") as f:
            raw_key = f.read().strip().encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'static_salt_for_devcore_kms',
            iterations=100000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(raw_key)))

    def _load_or_init_keychain(self) -> list[str]:
        if not os.path.exists(self.keychain_path):
            initial_dek = Fernet.generate_key()
            wrapped = self.kek.encrypt(initial_dek).decode('utf-8')
            data = {"keys": [wrapped], "active_index": 0}
            with open(self.keychain_path, "w") as f:
                json.dump(data, f, indent=2)
            return [wrapped]
        with open(self.keychain_path, "r") as f:
            return json.load(f).get("keys", [])

    def get_active_cipher(self) -> Fernet:
        active_wrapped = self.keys[-1]
        active_raw = self.kek.decrypt(active_wrapped.encode('utf-8'))
        return Fernet(active_raw)

    def get_all_ciphers(self) -> list[Fernet]:
        ciphers = []
        for wrapped in self.keys:
            raw = self.kek.decrypt(wrapped.encode('utf-8'))
            ciphers.append(Fernet(raw))
        return ciphers

def lock_file(filepath: str, cipher: Fernet):
    """Encrypts a file atomically, skipping already encrypted files."""
    with open(filepath, 'rb') as f:
        data = f.read()

    # Skip files already encrypted with Fernet
    if data.startswith(b'gAAAAA'):
        return

    encrypted = cipher.encrypt(data)
    
    # Atomic file replacement
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), prefix=".lock_")
    with os.fdopen(fd, 'wb') as f:
        f.write(encrypted)
    os.replace(tmp_path, filepath)
    print(f"[LOCKED] {filepath}")

def unlock_file(filepath: str, ciphers: list[Fernet]):
    """Decrypts a file using the historical cipher ring."""
    with open(filepath, 'rb') as f:
        data = f.read()

    if not data.startswith(b'gAAAAA'):
        return

    decrypted = None
    for cipher in ciphers:
        try:
            decrypted = cipher.decrypt(data)
            break
        except InvalidToken:
            continue

    if decrypted is None:
        raise ValueError(f"No key in keychain can decrypt {filepath}")

    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), prefix=".unlock_")
    with os.fdopen(fd, 'wb') as f:
        f.write(decrypted)
    os.replace(tmp_path, filepath)
    print(f"[UNLOCKED] {filepath}")

if __name__ == "__main__":
    km = KeychainManager()
    sample_file = "test_transcript.jsonl"
    with open(sample_file, "w") as f:
        f.write('{"user": "developer", "prompt": "build an accessible world"}\n')

    # Lock file
    lock_file(sample_file, km.get_active_cipher())
    
    # Unlock file
    unlock_file(sample_file, km.get_all_ciphers())

    # Clean up test artifacts
    os.remove(sample_file)
    os.remove(MASTER_KEY_FILE)
    os.remove(KEYCHAIN_FILE)
```

---

## 3. Why Order Matters in Cryptographic Locking
[//]: # (SECTION_ID: SIRA-DOC-05_30-SEC-3)
1. **Derive KEK Before Reading Keychain**: The master key must be verified and PBKDF2-derived before the keychain JSON can be loaded into memory.
2. **Check `b'gAAAAA'` Header Before Encrypting**: Verifying the magic prefix prevents double-encrypting files into nested ciphertexts.
3. **Close File Descriptor Before `os.replace`**: Closing the temporary file descriptor `fd` via `with os.fdopen(...)` guarantees that the operating system releases file locks before atomic replacement.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_30-SEC-4)
**Q: What is a KDF?**  
A: A Key Derivation Function (like PBKDF2). It takes a master password or file and stretches it through thousands of cryptographic rounds to create a strong encryption key.

**Q: Why use `tempfile.mkstemp`?**  
A: It creates a temporary file with a unique random filename that only the current user can access, preventing race conditions and file collisions.

**Q: What happens if an unlock attempt fails all keys?**  
A: The script raises a `ValueError`, leaving the encrypted file untouched on disk so it can be restored when the proper master key is provided.
