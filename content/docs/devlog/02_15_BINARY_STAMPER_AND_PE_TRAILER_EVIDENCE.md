[//]: # (DOC_ID: SIRA-DEV-02_15 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 02_15: Binary Stamper & PE Trailer Evidence

Primary source evidence from the Siraugga portable executable suite demonstrating how AES-encrypted metadata is stamped directly into Windows PE executable binary trailers without corrupting binary execution.

---

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-1)
## Source Citation 1: Cryptographic Binary Stamping (`security/stamper.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-1)

This excerpt displays how `stamp_exe` duplicates a master compiled binary and injects an AES-128 Fernet-encrypted JSON payload into the trailer:

```python
# Location: <project_root>/security/stamper.py
# Lines: 6-39

MAGIC_START = b"\n---AGY_STAMP_START---\n"
MAGIC_END = b"\n---AGY_STAMP_END---\n"

# AES-128 (Fernet) internal key for the binary stamping process
# This prevents the payload from being read in plaintext by inspecting the binary
STAMP_KEY = b'A4l7KaUtSVz1kvIS0SPXP2olNkyY6XVLNOhrEtTvkrc='

def get_cipher():
    return Fernet(STAMP_KEY)

def stamp_exe(source_exe: str, dest_exe: str, payload: dict):
    """
    Copies the source .exe and safely appends an AES-encrypted JSON payload to the bottom.
    This creates a uniquely stamped executable without recompiling.
    """
    import shutil
    
    if not os.path.exists(source_exe):
        raise FileNotFoundError(f"Source executable {source_exe} not found.")
        
    # 1. Copy the clean master .exe
    shutil.copy2(source_exe, dest_exe)
    
    # 2. Prepare and encrypt the payload
    payload_bytes = json.dumps(payload).encode('utf-8')
    encrypted_payload = get_cipher().encrypt(payload_bytes)
    
    # 3. Inject the ciphertext at the end of the binary
    stamp_data = MAGIC_START + encrypted_payload + MAGIC_END
    with open(dest_exe, "ab") as f:
        f.write(stamp_data)
        
    print(f"Successfully stamped {dest_exe} with AES-encrypted payload: {payload}")
```

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-2)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-2)
- **Instantaneous Client Packaging (0.1 Seconds)**: Rather than spending 10 minutes compiling a 40MB+ Nuitka binary for every client trial, `stamp_exe` appends encrypted metadata in milliseconds.
- **Ciphertext Protection**: Plaintext JSON is encrypted with AES-128 Fernet before injection. Attackers using hex editors or `strings` utilities cannot view expiration dates or client IDs.

---

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-3)
## Source Citation 2: Volatile RAM Extraction from Self (`security/stamper.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-3)

This excerpt shows how the running binary reads its own trailer from disk to verify expiration status:

```python
# Location: <project_root>/security/stamper.py
# Lines: 40-75

def read_stamp() -> dict:
    """
    Reads the currently executing binary (sys.executable) to see if it was stamped
    with an encrypted JSON payload. Decrypts and returns the dictionary if found in RAM.
    """
    if not getattr(sys, 'frozen', False):
        # We are running natively in Python (not an .exe)
        return None
        
    exe_path = sys.executable
    if not os.path.exists(exe_path):
        return None
        
    try:
        # Read the last 4096 bytes of the binary (where our stamp would be)
        with open(exe_path, "rb") as f:
            f.seek(0, 2) # End of file
            file_size = f.tell()
            read_size = min(4096, file_size)
            f.seek(file_size - read_size)
            tail_data = f.read()

        if MAGIC_START in tail_data and MAGIC_END in tail_data:
            start_idx = tail_data.find(MAGIC_START) + len(MAGIC_START)
            end_idx = tail_data.find(MAGIC_END)
            encrypted_payload = tail_data[start_idx:end_idx]
            
            decrypted_bytes = get_cipher().decrypt(encrypted_payload)
            return json.loads(decrypted_bytes.decode('utf-8'))
    except Exception as e:
        print(f"[STAMPER ERROR]: Could not parse binary stamp: {e}")
        
    return None
```

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-4)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-4)
- **Tail-Seeking Optimization**: Instead of reading a 40MB file into memory, line 58 seeks directly to the last 4096 bytes (`file_size - read_size`), decoding the metadata in under 0.5 milliseconds.
- **`sys.frozen` Guard**: Gracefully exits if running in raw Python scripts, allowing identical code to execute in development mode and compiled production binaries.

---

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-5)

In binary trailer stamping, byte placement sequence ensures executable integrity:
1. **Copy Binary Before Modification**: Always perform a complete binary clone (`shutil.copy2`) before modifying the destination file.
2. **Encrypt Payload Before Adding Magic Delimiters**: The ciphertext must be wrapped in unique byte boundaries (`MAGIC_START` / `MAGIC_END`) to allow deterministic slice extraction.
3. **Append Exclusively at Offset EOF (`"ab"`)**: Never write in `"r+b"` without seeking to `f.seek(0, 2)`. Overwriting existing binary bytes permanently corrupts the Windows PE header.

---

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-7)

### Why doesn't adding data to the end of an `.exe` break it?
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-7)
The Windows Portable Executable (PE) header contains an exact file length and section table. The Windows OS loader loads only the declared sections into memory and ignores any trailing bytes appended after the last section.

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-8)
### What is `sys.frozen`?
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-8)
When Python code is compiled into an executable using Nuitka or PyInstaller, the compiler injects `sys.frozen = True`. In normal Python scripts, this variable does not exist.

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-9)
### What happens if the trial is expired?
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-9)
If `current_time > stamp["expires"]`, the server refuses to spawn AI agent processes and directs the web UI to render a full-screen lock screen.

---

[//]: # (SECTION_ID: SIRA-DEV-02_15-SEC-10)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_15-SEC-10)
- To understand why portable binaries required dynamic stamping, read [`01_PROBLEMS_ENCOUNTERED/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS.md`](/docs/devlog/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS).
- To view diagnostic test logs of binary stamp extraction, visit [`03_DIAGNOSTIC_TESTS/03_14_BINARY_STAMP_EXTRACTION_AND_EXPIRATION_LOGS.md`](/docs/devlog/03_14_BINARY_STAMP_EXTRACTION_AND_EXPIRATION_LOGS).
- To build the complete binary stamping script from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_17_PE_BINARY_STAMPER_AND_VERIFIER_FROM_SCRATCH.md`](/docs/devlog/05_17_PE_BINARY_STAMPER_AND_VERIFIER_FROM_SCRATCH).
