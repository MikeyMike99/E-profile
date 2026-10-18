[//]: # (DOC_ID: SIRA-DEV-02_12 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 02_12: Accessible Speech & Driver Initialization Evidence

Primary source evidence from the Siraugga accessible speech engine demonstrating how runtime dynamic DLL extraction, directory registration, and COM apartment management guarantee screen reader speech across diverse client machines.

---

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-1)
## Source Citation 1: Dynamic DLL Extraction & Fallback (`screenreader_speak.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-1)

This excerpt displays how the speech module discovers or automatically writes the required NVDA controller DLLs from embedded byte data:

```python
# Location: <project_root>/screenreader_speak.py
# Lines: 25-53

    resolved_lib_dir = None
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "nvdaControllerClient64.dll")):
            resolved_lib_dir = c
            break

    # If DLL is not present on disk, extract it from embedded data
    if not resolved_lib_dir:
        target_base = os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Programs", "JOSHY", "accessible_output2", "lib"
        )
        try:
            os.makedirs(target_base, exist_ok=True)
            resolved_lib_dir = target_base
        except Exception:
            resolved_lib_dir = os.path.join(os.environ.get("TEMP", ""), "JOSHY", "accessible_output2", "lib")
            os.makedirs(resolved_lib_dir, exist_ok=True)

        try:
            import nvda_client_data
            dll64_path = os.path.join(resolved_lib_dir, "nvdaControllerClient64.dll")
            if not os.path.isfile(dll64_path):
                with open(dll64_path, "wb") as f:
                    f.write(base64.b64decode(nvda_client_data.NVDA_CLIENT_64))
            dll32_path = os.path.join(resolved_lib_dir, "nvdaControllerClient32.dll")
            if not os.path.isfile(dll32_path):
                with open(dll32_path, "wb") as f:
                    f.write(base64.b64decode(nvda_client_data.NVDA_CLIENT_32))
        except Exception as e:
            print(f"[ScreenReader DLL Warning]: {e}")
```

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-2)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-2)
- **Zero-Dependency Binary Portability**: If a compiled executable is moved to a clean Windows computer without Python or developer tools installed, lines 41–50 extract the necessary 64-bit and 32-bit NVDA controller DLLs on the fly into `%LOCALAPPDATA%` or `%TEMP%`.
- **Elimination of Silent SAPI Fallback**: By ensuring the DLL is physically written to disk before `accessible_output2` initializes, the application speaks natively through NVDA instead of falling back to robotic system voices.

---

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-3)
## Source Citation 2: Windows DLL Directory Registration (`screenreader_speak.py`)
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-3)

This excerpt shows how the module complies with Windows security restrictions introduced in Python 3.8+:

```python
# Location: <project_root>/screenreader_speak.py
# Lines: 54-65

    # Register DLL directory for Python 3.8+ Windows security
    if resolved_lib_dir:
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(resolved_lib_dir)
            except Exception:
                pass
        if resolved_lib_dir not in sys.path:
            sys.path.insert(0, resolved_lib_dir)
```

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-4)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-4)
- **Python 3.8+ DLL Preload Defense**: Python 3.8 stopped loading DLLs from `PATH` or the current working directory to prevent DLL hijacking attacks. Invoking `os.add_dll_directory()` explicitly authorizes Windows to load libraries from the resolved folder.
- **Backwards Compatibility**: The `if hasattr(os, "add_dll_directory")` check ensures the code runs cleanly on older Python 3.7 or Linux environments without throwing `AttributeError`.

---

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-5)

In Windows assistive audio synthesis, initialization order controls thread safety:
1. **Initialize COM (`pythoncom.CoInitialize()`) Before Object Creation**: Windows speech APIs rely on Component Object Model (COM) interfaces. Any background worker thread must initialize its COM apartment before invoking speech functions.
2. **Extract DLLs Before Importing Output Backend**: `accessible_output2` scans for DLLs at the exact moment of import. If you extract the DLL *after* importing the library, the library has already defaulted to SAPI.
3. **Register `os.add_dll_directory` Before `ctypes.windll`**: Windows NT kernel restricts DLL search paths. Calling `add_dll_directory()` must precede any `windll.LoadLibrary()` call.

---

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-7)

### Why are both 32-bit and 64-bit DLLs extracted?
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-7)
While most modern operating systems are 64-bit, some screen readers or specialized assistive drivers still run as 32-bit processes. Extracting both guarantees compatibility regardless of architecture.

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-8)
### What is `base64.b64decode` doing here?
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-8)
The binary `.dll` file is converted into an ASCII text string stored inside `nvda_client_data.py`. `b64decode` turns that string back into the exact executable machine code bytes required by Windows.

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-9)
### Why does the code check `%LOCALAPPDATA%` before `%TEMP%`?
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-9)
`%LOCALAPPDATA%` is persistent across reboots and local to the logged-in user. `%TEMP%` can be purged by automated Windows disk cleaners mid-session, which could delete the DLL while the program is running.

---

[//]: # (SECTION_ID: SIRA-DEV-02_12-SEC-10)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_12-SEC-10)
- To understand the symptoms that prompted this embedded DLL architecture, read [`01_PROBLEMS_ENCOUNTERED/01_17_SCREEN_READER_DLL_BINDINGS_AND_IMPORT_ORDER_TRAPS.md`](/docs/devlog/01_17_SCREEN_READER_DLL_BINDINGS_AND_IMPORT_ORDER_TRAPS).
- To view diagnostic audit logs verifying DLL loading and COM apartment initialization, visit [`03_DIAGNOSTIC_TESTS/03_11_SCREEN_READER_DLL_AND_DRIVER_AUDIT_LOGS.md`](/docs/devlog/03_11_SCREEN_READER_DLL_AND_DRIVER_AUDIT_LOGS).
- To write the standalone accessible speech module from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_14_ACCESSIBLE_SCREEN_READER_SPEECH_MODULE_FROM_SCRATCH.md`](/docs/devlog/05_14_ACCESSIBLE_SCREEN_READER_SPEECH_MODULE_FROM_SCRATCH).
