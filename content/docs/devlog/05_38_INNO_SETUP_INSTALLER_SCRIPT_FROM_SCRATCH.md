[//]: # (DOC_ID: JOSH-DOC-05_38 | VERSION: v1.0 | SCOPE: JOSHY Audio Suite)

# Pillar 05.38: From-Scratch Creation Guide: Inno Setup Windows Installer Script

## Overview & Beginner Context
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-1)
This guide teaches you how to write an Inno Setup script (`JOSHY Setup.iss`) and its companion build batch file (`compile_joshy.bat`) line by line from scratch. It compiles your Python executable into a professional Windows installer that terminates running background processes before overwriting binaries.

---

## 1. Line-by-Line Construction
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-1)

### Block 1: The Build Automation Script (`compile_joshy.bat`)
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-2)
```batch
@echo off
echo [Step 1/3] Terminating any active background instances...
taskkill /F /IM JOSHY.exe 2>nul
timeout /t 1 /nobreak >nul

echo [Step 2/3] Compiling Python executable with PyInstaller...
pyinstaller --noconfirm --onedir --windowed --name JOSHY t.py

echo [Step 3/3] Compiling Inno Setup Installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "JOSHY Setup.iss"
echo Build Complete: Output in Output\JOSHY-Setup.exe
```
- Ensures running processes are killed before PyInstaller or Inno Setup attempt to write to disk.

### Block 2: The Inno Setup Script Definition (`JOSHY Setup.iss`)
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-3)
```iss
[Setup]
AppName=JOSHY Audio Suite
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\JOSHY
DefaultGroupName=JOSHY
OutputDir=Output
OutputBaseFilename=JOSHY-Setup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "dist\JOSHY\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\JOSHY Audio Suite"; Filename: "{app}\JOSHY.exe"
Name: "{autodesktop}\JOSHY"; Filename: "{app}\JOSHY.exe"

[Run]
Filename: "{app}\JOSHY.exe"; Description: "Launch JOSHY Audio Suite"; Flags: nowait postinstall skipifsilent
```
- Sets `PrivilegesRequired=lowest` so non-admin users can install the application without elevation prompts.
- Packages all files from `dist\JOSHY` into `{localappdata}\Programs\JOSHY`.

---

## 2. 10-Second Verification Checklist
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-2)
1. Run `compile_joshy.bat`.
2. Inspect `Output\JOSHY-Setup.exe`.
3. Run installer -> App extracts and launches cleanly.

---

## 3. Beginner Coder Q&A
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-3)

### What does `PrivilegesRequired=lowest` mean in Inno Setup?
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-4)
It configures the installer to run without requiring Windows Administrator (UAC) prompts. The app installs into the user's `%LOCALAPPDATA%` folder, allowing it to install on restricted school or workplace computers.

---

## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: JOSH-DOC-05_38-SEC-4)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_39_INNO_SETUP_COMPILATION_AND_SPEECH_DLL_TRAPS.md`](/docs/devlog/01_39_INNO_SETUP_COMPILATION_AND_SPEECH_DLL_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_35_INNO_SETUP_AND_ACCESSIBLE_OUTPUT2_EVIDENCE.md`](/docs/devlog/02_35_INNO_SETUP_AND_ACCESSIBLE_OUTPUT2_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_32_INNO_SETUP_INSTALLER_AND_DLL_AUDIT_LOGS.md`](/docs/devlog/03_32_INNO_SETUP_INSTALLER_AND_DLL_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_35_STANDALONE_INSTALLER_AND_SPEECH_DLL_ARCHITECTURE.md`](/docs/devlog/04_35_STANDALONE_INSTALLER_AND_SPEECH_DLL_ARCHITECTURE)
