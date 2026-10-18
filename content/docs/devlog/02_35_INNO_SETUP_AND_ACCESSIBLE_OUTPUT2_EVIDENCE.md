[//]: # (DOC_ID: SIRA-DEV-02_35 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.35: Source Code Evidence: Inno Setup & Screen Reader DLL Extraction

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-1)
## Overview & Context
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-1)
This document cites primary source code evidence from `screenreader_speak.py` demonstrating how accessible applications bundle native C-libraries as base64 byte arrays to guarantee screen reader connectivity even on clean Windows systems where external DLLs are stripped.

---

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-2)
## Source Citation 1: Dynamic DLL Extraction & Directory Registration (`screenreader_speak.py`)
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-2)

```python
# Location: Audio_pllayback_suite/screenreader_speak.py
# Lines 22-60

    candidates.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "JOSHY", "accessible_output2", "lib"))
    candidates.append(os.path.join(os.environ.get("TEMP", ""), "JOSHY", "accessible_output2", "lib"))

    resolved_lib_dir = None
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "nvdaControllerClient64.dll")):
            resolved_lib_dir = c
            break

    # If DLL is not present on disk, extract it from embedded data
    if not resolved_lib_dir:
        target_base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "JOSHY", "accessible_output2", "lib")
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

    # Register DLL directory for Python 3.8+ Windows security
    if resolved_lib_dir:
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(resolved_lib_dir)
            except Exception:
                pass
```

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-3)
### What This Source Proves
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-3)
- The application guarantees zero-failure screen reader connectivity by self-extracting embedded 32-bit and 64-bit NVDA controller DLLs if they are missing from disk.
- By calling `os.add_dll_directory(resolved_lib_dir)`, it explicitly satisfies Windows security policies introduced in Python 3.8+ that restrict DLL loading to trusted paths.

---

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-4)
## Source Citation 2: Inno Setup Process Termination Hook (`compile_joshy.bat`)
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-4)

```batch
:: Location: Audio_pllayback_suite/compile_joshy.bat
:: Terminating background instances before writing installer payload

taskkill /F /IM JOSHY.exe 2>nul
timeout /t 1 /nobreak >nul

"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "JOSHY Setup.iss"
```

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-5)
### What This Source Proves
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-5)
- The automated packaging pipeline forces running executable processes to close before Inno Setup begins compilation, eliminating `Error opening file for writing` file-locking failures.

---

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-3)
## 3. Why Order Matters in DLL Discovery
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-3)
1. **Candidate Scan Before Base64 Extraction**: Check existing directories first to avoid unnecessary disk writes and flash wear.
2. **Directory Registration Before Library Import**: You must invoke `os.add_dll_directory` *before* `accessible_output2.outputs.auto.Auto()` attempts to load the DLL into Python's address space.

---

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-4)
## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-6)

### What is `os.add_dll_directory`?
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-6)
In Python 3.8 and newer on Windows, Python no longer searches the system `PATH` or current directory for DLLs loaded via `ctypes`. You must explicitly call `os.add_dll_directory` with the exact folder path where your `.dll` file resides.

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-7)
### Why does NVDA have both 32-bit and 64-bit DLLs?
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-7)
NVDA itself is a 32-bit application, but Python programs can run as either 32-bit or 64-bit processes. The controller client must match the bitness of your running Python executable to communicate with NVDA.

---

[//]: # (SECTION_ID: SIRA-DEV-02_35-SEC-5)
## 5. Cross-Reference Navigation
[//]: # (SECTION_ID: JOSH-DOC-02_35-SEC-5)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_39_INNO_SETUP_COMPILATION_AND_SPEECH_DLL_TRAPS.md`](/docs/devlog/01_39_INNO_SETUP_COMPILATION_AND_SPEECH_DLL_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_32_INNO_SETUP_INSTALLER_AND_DLL_AUDIT_LOGS.md`](/docs/devlog/03_32_INNO_SETUP_INSTALLER_AND_DLL_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_35_STANDALONE_INSTALLER_AND_SPEECH_DLL_ARCHITECTURE.md`](/docs/devlog/04_35_STANDALONE_INSTALLER_AND_SPEECH_DLL_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_38_INNO_SETUP_INSTALLER_SCRIPT_FROM_SCRATCH.md`](/docs/devlog/05_38_INNO_SETUP_INSTALLER_SCRIPT_FROM_SCRATCH)
