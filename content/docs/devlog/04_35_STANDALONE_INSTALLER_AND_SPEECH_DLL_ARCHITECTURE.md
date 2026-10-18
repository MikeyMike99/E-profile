[//]: # (DOC_ID: SIRA-DEV-04_35 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 04.35: Architectural Blueprint: Standalone Installer & Screen Reader DLL Architecture

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-1)
## Executive Summary
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-1)
This blueprint details the architectural solution for compiling accessible Python applications into self-contained, enterprise-grade Windows installers (`JOSHY-Setup.exe`) using PyInstaller and Inno Setup, featuring automated process termination and self-extracting screen reader DLL libraries (`nvdaControllerClient64.dll`).

---

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-1)
## 1. Automated Build & Distribution Pipeline
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-1)

```
Developer Build Execution (`compile_joshy.bat`):
          │
          ▼
1. Process Termination Hook (`taskkill /F /IM JOSHY.exe`)
          │
          ▼
2. PyInstaller Packaging (Compiles Python into single-file binary)
          │
          ▼
3. Inno Setup Compiler (`ISCC.exe` packages binary into Setup wizard)
          │
          ▼
Clean Machine Execution (`JOSHY.exe`):
          │
          ├── DLL present in %LOCALAPPDATA%? ──► Loaded via os.add_dll_directory
          │
          └── DLL missing? ──► Extracted from embedded base64 in `nvda_client_data.py`
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-2)
## 2. Core Functional Modules
[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-1)

### 1. The Pre-Build Process Reaping Hook
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-1)
- Embedded in `compile_joshy.bat` to eliminate file-locking errors during compilation and deployment.
- Closes any active or hung instances of the application before attempting to write updated binaries to disk.

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-2)
### 2. The Self-Extracting Embedded DLL Architecture (`screenreader_speak.py`)
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-2)
- Solves the missing screen reader DLL problem on clean machines.
- Embeds the official 32-bit and 64-bit NVDA controller DLLs as base64 string constants inside `nvda_client_data.py`.
- At application startup, the loader checks if the DLL is present on disk. If absent, it decodes the payload and writes it directly to `%LOCALAPPDATA%\Programs\JOSHY\accessible_output2\lib\`.
- Automatically calls `os.add_dll_directory` to satisfy modern Windows DLL search restrictions.

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-3)
### 3. The Graceful Output Fallback Hierarchy
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-3)
- Tiers speech engines automatically:
  1. **Primary**: NVDA Controller Client (Native Screen Reader).
  2. **Secondary**: Microsoft SAPI5 (Windows Desktop Speech Synthesizer).
  3. **Tertiary**: Standard Console Output / Diagnostic Log.

---

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-3)
## 3. Why Order Matters in Windows Software Distribution
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-3)
1. **Terminate Processes Before Installer Run**: You must ensure no lock is held on the target file before the installer begins file extraction.
2. **Register DLL Directory Before Driver Instantiation**: The folder containing the native library must be registered with `os.add_dll_directory` *before* Python tries to call `windll.LoadLibrary`.

---

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-4)
## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-2)

### Why not just put the DLL in `C:\Windows\System32`?
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-2)
Writing to `System32` requires Administrator privileges, which standard non-technical users may not have. Writing to `%LOCALAPPDATA%` requires zero elevated permissions and works cleanly for any standard user account.

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-3)
### How does base64 embedding prevent antivirus false positives?
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-3)
Compiling external `.dll` files loose inside a zip or installer often triggers false-positive heuristical warnings from antivirus software. Storing the DLL inside a signed, structured Python data module eliminates heuristic scanning alerts.

---

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-5)
## 5. Reusable Quick-Start Recipe (2-Minute Deployment)
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-5)
1. Generate base64 data file: `python -c "import base64; open('nvda_client_data.py','w').write(f'NVDA_CLIENT_64 = \"{base64.b64encode(open(\"nvdaControllerClient64.dll\",\"rb\").read()).decode()}\"')"`
2. Add dynamic extraction to your speech module.
3. Run `compile_joshy.bat` to generate `JOSHY-Setup.exe`.

---

[//]: # (SECTION_ID: SIRA-DEV-04_35-SEC-6)
## 6. Cross-Reference Navigation
[//]: # (SECTION_ID: JOSH-DOC-04_35-SEC-6)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_39_INNO_SETUP_COMPILATION_AND_SPEECH_DLL_TRAPS.md`](/docs/devlog/01_39_INNO_SETUP_COMPILATION_AND_SPEECH_DLL_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_35_INNO_SETUP_AND_ACCESSIBLE_OUTPUT2_EVIDENCE.md`](/docs/devlog/02_35_INNO_SETUP_AND_ACCESSIBLE_OUTPUT2_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_32_INNO_SETUP_INSTALLER_AND_DLL_AUDIT_LOGS.md`](/docs/devlog/03_32_INNO_SETUP_INSTALLER_AND_DLL_AUDIT_LOGS)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_38_INNO_SETUP_INSTALLER_SCRIPT_FROM_SCRATCH.md`](/docs/devlog/05_38_INNO_SETUP_INSTALLER_SCRIPT_FROM_SCRATCH)
