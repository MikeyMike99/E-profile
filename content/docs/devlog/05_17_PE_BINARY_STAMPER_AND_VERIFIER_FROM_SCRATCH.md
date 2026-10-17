[//]: # (DOC_ID: SIRA-DOC-05_17 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# PE Binary Stamper & Verifier from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_17-SEC-1)
Recompiling a large Python engine using Nuitka takes 8 to 15 minutes. If license keys, user tiers, or build metadata are baked directly into source code, creating custom builds for different developers becomes impractically slow.

The PE Binary Stamper (`stamper.py`) appends encrypted metadata trailers directly to the end of pre-compiled Portable Executable (`.exe`) or ELF binaries in under 5 milliseconds. The binary's runtime reads its own trailer from disk, decrypts the payload with a shared secret, and configures privileges instantly without altering executable PE section headers.

```
+-------------------------------------------------------------+
|               Compiled Windows PE Executable                |
|             (.text, .data, .rsrc, import tables)            |
+-------------------------------------------------------------+
| MAGIC START: b"__SIRAUGGA_STAMP_START__"                    |
| Encrypted Payload: Fernet-AES128 JSON {"tier": 5, ...}     |
| MAGIC END:   b"__SIRAUGGA_STAMP_END__"                      |
+-------------------------------------------------------------+
```

---

## 2. Complete Python Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_17-SEC-2)
Save the following script as `stamper.py`:

```python
import os
import sys
import json
import base64
from cryptography.fernet import Fernet

MAGIC_START = b"__SIRAUGGA_STAMP_START__"
MAGIC_END = b"__SIRAUGGA_STAMP_END__"
SHARED_SECRET = Fernet.generate_key()  # In production, load from KMS / secure environment

def stamp_binary(target_exe: str, metadata: dict, key: bytes = SHARED_SECRET) -> bool:
    """Appends an encrypted JSON trailer to an existing executable binary."""
    if not os.path.exists(target_exe):
        raise FileNotFoundError(f"Binary not found: {target_exe}")
    
    # 1. Serialize and encrypt metadata
    json_bytes = json.dumps(metadata).encode("utf-8")
    cipher = Fernet(key)
    encrypted_bytes = cipher.encrypt(json_bytes)
    
    # 2. Construct trailer package
    trailer = MAGIC_START + encrypted_bytes + MAGIC_END
    
    # 3. Append directly to binary
    with open(target_exe, "ab") as f:
        f.write(trailer)
    
    print(f"Successfully stamped {len(trailer)} bytes onto {target_exe}")
    return True

def read_stamp(target_exe: str, key: bytes = SHARED_SECRET) -> dict:
    """Reads and decrypts metadata from the executable's trailer."""
    if not os.path.exists(target_exe):
        raise FileNotFoundError(f"Binary not found: {target_exe}")
    
    file_size = os.path.getsize(target_exe)
    # Read up to the last 8KB of the binary
    read_len = min(file_size, 8192)
    
    with open(target_exe, "rb") as f:
        f.seek(file_size - read_len, os.SEEK_SET)
        chunk = f.read(read_len)
    
    start_idx = chunk.find(MAGIC_START)
    end_idx = chunk.find(MAGIC_END)
    
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        raise ValueError("No valid stamp metadata found in executable trailer.")
    
    encrypted_payload = chunk[start_idx + len(MAGIC_START):end_idx]
    
    # Decrypt and parse JSON
    cipher = Fernet(key)
    decrypted_bytes = cipher.decrypt(encrypted_payload)
    return json.loads(decrypted_bytes.decode("utf-8"))

if __name__ == "__main__":
    test_bin = "dummy_app.exe"
    # Create a dummy binary for demonstration
    with open(test_bin, "wb") as f:
        f.write(b"MZ" + b"\x00" * 1024)  # Minimal PE header simulation
    
    sample_meta = {"user_tier": 5, "licensee": "Game Studio Admin", "sandbox": False}
    stamp_binary(test_bin, sample_meta)
    
    extracted = read_stamp(test_bin)
    print("Extracted Stamp Metadata:", extracted)
    
    # Clean up test binary
    os.remove(test_bin)
```

---

## 3. Why Order Matters in Binary Stamping
[//]: # (SECTION_ID: SIRA-DOC-05_17-SEC-3)
1. **Append in Binary Mode (`ab`)**: Writing in text mode (`a`) can convert carriage return line breaks (`\r\n`), corrupting the cryptographic ciphertext.
2. **Seek Relative to End of File**: Reading only the trailing 8KB prevents loading massive 50MB binaries into memory, keeping startup latency under 5 milliseconds.
3. **Verify Bounds Before Decrypting**: Ensuring `start_idx < end_idx` avoids slicing corrupted chunks into the Fernet decryptor.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_17-SEC-4)
**Q: Does appending data break the Windows executable?**  
A: No! The Windows PE loader reads header tables from the front of the file to determine section boundaries. Trailing overlay data past the final section is ignored by the OS loader.

**Q: Can a developer tamper with the trailer?**  
A: No. Because the trailer is encrypted with AES-128 via Fernet, tampering with a single byte causes a cryptographic integrity check failure (`InvalidSignature`).

**Q: Where is this used in the Siraugga pipeline?**  
A: The build pipeline generates one master `.exe` via Nuitka, and stamping deploys custom tier configurations (`dev`, `mod`, `admin`) in milliseconds.
