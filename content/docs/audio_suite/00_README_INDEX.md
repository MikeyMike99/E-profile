[//]: # (DOC_ID: JOSH-PLAY-INDEX | VERSION: v1.0 | SCOPE: PLAY)

# JOSHY Screen Reader & Nuitka Packaging Documentation Index

Welcome to the technical documentation and future compilation guide for the **JOSHY Audio Playback Suite**.

This folder documents the complete investigation, source code evidence, diagnostic test suite, and step-by-step engineering solution used to package **`accessible_output2`** and **`screenreader_speak.py`** into a standalone Windows executable (`JOSHY.exe` (JOSHY.exe)) and Windows Setup Installer (`JOSHY-Setup.exe` (JOSHY-Setup.exe)) using **Nuitka**.

---

[//]: # (SECTION_ID: JOSH-PLAY-INDEX-SEC-1)
## Documentation Directory Contents
[//]: # (SECTION_ID: JOSH-PLAY-00-SEC-1)

The documentation is organized into five focused, screen-reader-friendly guides:

1. **[`00_README_INDEX.md`](/docs/audio_suite/00_README_INDEX)** *(This File)*
   - Master table of contents, file map, and quick-reference checklist.

2. **[`01_PROBLEMS_WE_ENCOUNTERED.md`](/docs/audio_suite/01_PROBLEMS_WE_ENCOUNTERED)**
   - Plain-English explanation of the three bugs encountered during compilation and cross-PC installation:
     1. The initial `.exe` startup crash on Windows (Python 3.8+ DLL security restrictions).
     2. The NSIS Setup Installer error (`Error opening file for writing: \JOSHY.exe`).
     3. The cross-PC fallback bug where a second computer used the default Windows SAPI voice instead of NVDA or JAWS.

3. **[`02_SOURCE_CODE_EVIDENCE.md`](/docs/audio_suite/02_SOURCE_CODE_EVIDENCE)**
   - Exact quotes, library locations, and line-by-line analysis from the actual source documents:
     - Official `accessible_output2` documentation (`METADATA` and `readme.rst`).
     - `accessible_output2/__init__.py` (`load_library` and `find_datafiles`).
     - `platform_utils/paths.py` (`is_frozen`, `is_pyinstaller`, and `embedded_data_path`).
     - `accessible_output2/outputs/base.py` and `auto.py` (the uncaught `AttributeError` / `FileNotFoundError` bug in `Auto.__init__`).
     - `win32/lib/pywintypes.py` and `libloader/com.py` (frozen COM initialization rules).

4. **[`03_DIAGNOSTIC_TESTS_AND_CONCLUSIONS.md`](/docs/audio_suite/03_DIAGNOSTIC_TESTS_AND_CONCLUSIONS)**
   - Every command and live test executed in Python 3.13, the exact tracebacks and outputs returned, and how each test proved our conclusions before writing the fix.

5. **[`04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE.md`](/docs/audio_suite/04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE)**
   - Complete, step-by-step recipe for how the final solution works and how you can replicate it yourself on any future Python project using Nuitka and `accessible_output2`.

---

[//]: # (SECTION_ID: JOSH-PLAY-INDEX-SEC-2)
## Project File Map
[//]: # (SECTION_ID: JOSH-PLAY-00-SEC-2)

| File | Location | Role |
| :--- | :--- | :--- |
| `main.py` (t.py) | `<project_root>/main.py` | Main application GUI, global hotkeys, per-app audio mixer, and media player integration |
| `screenreader_speak.py` (screenreader_speak.py) | `<project_root>/screenreader_speak.py` | Self-healing `accessible_output2` initialization, DLL auto-extraction, and speech bridge |
| `nvda_client_data.py` (nvda_client_data.py) | `<project_root>/nvda_client_data.py` | Embedded Base64 payload of `nvdaControllerClient64.dll` and `nvdaControllerClient32.dll` |
| `compile_joshy.bat` (compile_joshy.bat) | `<project_root>/compile_joshy.bat` | One-click Nuitka compilation and Windows NSIS installer build script |
| `JOSHY.exe` (JOSHY.exe) | `<project_root>/JOSHY.exe` | Compiled standalone native executable |
| `JOSHY-Setup.exe` (JOSHY-Setup.exe) | `<project_root>/JOSHY-Setup.exe` | Distributable Windows Setup Installer with Desktop and Start Menu shortcuts |

---

[//]: # (SECTION_ID: JOSH-PLAY-INDEX-SEC-3)
## Quick Checklist for Future Recompilations
[//]: # (SECTION_ID: JOSH-PLAY-00-SEC-3)

If you ever modify `main.py` (t.py) in the future and want to rebuild both `JOSHY.exe` and `JOSHY-Setup.exe`:

1. Make sure `JOSHY.exe` is closed (not currently running in the background) so Windows does not lock the file.
2. Double-click `compile_joshy.bat` (compile_joshy.bat) in `<project_root>`.
3. Wait approximately 1 to 2 minutes until you see:
   `SUCCESS: JOSHY.exe and JOSHY-Setup.exe compiled successfully!`
4. Distribute `JOSHY-Setup.exe` (JOSHY-Setup.exe) to any Windows PC.

---

[//]: # (SECTION_ID: JOSH-PLAY-INDEX-SEC-4)
## New to Screen Readers or Accessible Coding? Start Here First!
[//]: # (SECTION_ID: JOSH-PLAY-00-SEC-4)

If you are a beginner developer reading this documentation for the first time—and you did not build `JOSHY.exe` and have never worked with screen readers before—read **[`00A_BEGINNER_GUIDE_TO_SCREENREADERS_AND_ACCESSIBILITY.md`](/docs/audio_suite/00A_BEGINNER_GUIDE_TO_SCREENREADERS_AND_ACCESSIBILITY)** before diving into Chapter 1.

It answers the core questions a beginner coder asks when opening this folder:
1. **What is a screen reader (NVDA, JAWS), and how do visually impaired users interact with a PC?**
2. **Why does an app need `screenreader_speak.py` and `accessible_output2` if a screen reader is already running?**
3. **Why is speaking through the user's active screen reader so much better than using Windows' built-in default TTS (`SAPI`)?**
4. **What do terms like `.dll`, `ctypes`, `COM`, "freezing" (`sys.frozen`), and Nuitka mean in plain English?**
5. **How can I reuse `screenreader_speak.py` (screenreader_speak.py) and `nvda_client_data.py` (nvda_client_data.py) in my own Python projects to build accessible applications for visually impaired individuals?**

---

[//]: # (SECTION_ID: JOSH-PLAY-INDEX-SEC-5)
## Chapter 5 Added: Building the `.bat` File From Scratch
[//]: # (SECTION_ID: JOSH-PLAY-00-SEC-5)

6. **[`05_STEP_BY_STEP_BAT_FILE_CREATION_GUIDE.md`](/docs/audio_suite/05_STEP_BY_STEP_BAT_FILE_CREATION_GUIDE)**
   - A complete beginner's guide to creating `compile_joshy.bat` (compile_joshy.bat) from a blank Notepad file, explaining every batch command (`@echo off`, `cd /d "%~dp0"`, `^`, `$LOCALAPPDATA` vs. `%%LOCALAPPDATA%%`, `%ERRORLEVEL%`, `pause`) and every Nuitka flag line by line.
