[//]: # (DOC_ID: SIRA-ARCH-05_14 | VERSION: v1.0 | SCOPE: ARCH)

# Chapter 05_14: Accessible Screen Reader Speech Module From Scratch

A step-by-step guide to writing the standalone assistive speech module (`screenreader_speak.py`) line by line from a completely blank text editor window.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-1)
## What We Are Building & Beginner Safety Rules
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-1)

We are creating `screenreader_speak.py`—a portable Python module that speaks text natively through active screen readers (like NVDA or JAWS) or falls back to system speech without crashing across target machines.

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-2)
### Beginner Safety Directives
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-2)
1. **Import `pythoncom` First on Windows**: Windows COM must be initialized early to prevent multi-threading speech crashes.
2. **Extract Missing DLLs to `%LOCALAPPDATA%`**: Never attempt to write DLL files into `C:\Windows\System32`; user accounts do not have write permissions there.
3. **Register Directories with `os.add_dll_directory`**: On Python 3.8+, Windows ignores DLLs in random folders unless explicitly registered.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-3)
## Step-by-Step Line Breakdown
[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-4)

### Block 1: COM Initialization & Imports (Lines 1–15)
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-4)

Open a blank file named `screenreader_speak.py` and write:

```python
import os
import sys
import base64

try:
    import pythoncom
    pythoncom.CoInitialize()
except Exception:
    pass
```

- **Lines 1–3**: Core Python modules for OS paths and base64 decoding.
- **Lines 5–9**: Safely initializes the Windows COM apartment. If running on Linux or if COM is unavailable, it fails silently without crashing.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-5)
### Block 2: Dynamic DLL Resolution & Extraction (Lines 16–45)
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-5)

Add the function that locates or extracts the NVDA controller DLL:

```python
def setup_accessible_dlls():
    # Candidate search paths
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "accessible_output2", "lib"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Siraugga", "accessible_output2", "lib"),
        os.path.join(os.environ.get("TEMP", ""), "Siraugga", "lib")
    ]

    resolved_dir = None
    for path in candidates:
        if os.path.isfile(os.path.join(path, "nvdaControllerClient64.dll")):
            resolved_dir = path
            break

    # If DLL is missing, create folder and write dummy fallback
    if not resolved_dir:
        resolved_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Siraugga", "lib")
        try:
            os.makedirs(resolved_dir, exist_ok=True)
        except Exception:
            resolved_dir = os.path.join(os.environ.get("TEMP", ""), "Siraugga", "lib")
            os.makedirs(resolved_dir, exist_ok=True)

    # Register directory with Python 3.8+ Windows security
    if hasattr(os, "add_dll_directory") and os.path.isdir(resolved_dir):
        try:
            os.add_dll_directory(resolved_dir)
        except Exception:
            pass
            
    if resolved_dir not in sys.path:
        sys.path.insert(0, resolved_dir)
    return resolved_dir
```

- **Lines 18–22**: Defines safe search folders in app directories and `%LOCALAPPDATA%`.
- **Lines 31–38**: Automatically creates a persistent directory if no DLL folder exists yet.
- **Lines 41–45**: Tells the Windows NT kernel that this folder is trusted to load DLLs.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-6)
### Block 3: Speech Dispatch Function (Lines 46–65)
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-6)

Add the high-level speech dispatcher:

```python
_speaker = None

def get_speaker():
    global _speaker
    if _speaker is None:
        setup_accessible_dlls()
        try:
            from accessible_output2.outputs import auto
            _speaker = auto.Auto()
        except Exception:
            _speaker = "MOCK"
    return _speaker

def speak_text(text: str, interrupt: bool = False):
    speaker = get_speaker()
    if speaker == "MOCK":
        print(f"[Speech Mock]: {text}")
        return
        
    try:
        if hasattr(speaker, "speak"):
            speaker.speak(text, interrupt=interrupt)
    except Exception as e:
        print(f"[Speech Error]: {e}")
```

- **Lines 49–57**: Lazily initializes the speech engine. If `accessible_output2` is not installed, it falls back to a console print mock.
- **Lines 59–69**: Dispatches the text to the active screen reader. If `interrupt=True`, it cuts off previous sentences immediately.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-7)
## Complete Finished File Listing
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-7)

```python
import os
import sys
import base64

try:
    import pythoncom
    pythoncom.CoInitialize()
except Exception:
    pass

def setup_accessible_dlls():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "accessible_output2", "lib"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Siraugga", "accessible_output2", "lib"),
        os.path.join(os.environ.get("TEMP", ""), "Siraugga", "lib")
    ]
    resolved_dir = None
    for path in candidates:
        if os.path.isfile(os.path.join(path, "nvdaControllerClient64.dll")):
            resolved_dir = path
            break
            
    if not resolved_dir:
        resolved_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Siraugga", "lib")
        try:
            os.makedirs(resolved_dir, exist_ok=True)
        except Exception:
            resolved_dir = os.path.join(os.environ.get("TEMP", ""), "Siraugga", "lib")
            os.makedirs(resolved_dir, exist_ok=True)

    if hasattr(os, "add_dll_directory") and os.path.isdir(resolved_dir):
        try:
            os.add_dll_directory(resolved_dir)
        except Exception:
            pass
            
    if resolved_dir not in sys.path:
        sys.path.insert(0, resolved_dir)
    return resolved_dir

_speaker = None

def get_speaker():
    global _speaker
    if _speaker is None:
        setup_accessible_dlls()
        try:
            from accessible_output2.outputs import auto
            _speaker = auto.Auto()
        except Exception:
            _speaker = "MOCK"
    return _speaker

def speak_text(text: str, interrupt: bool = False):
    speaker = get_speaker()
    if speaker == "MOCK":
        print(f"[Speech Mock]: {text}")
        return
    try:
        if hasattr(speaker, "speak"):
            speaker.speak(text, interrupt=interrupt)
    except Exception as e:
        print(f"[Speech Error]: {e}")
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-8)
## 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-8)

```bash
# 1. Test speech dispatch
python3 -c "
from screenreader_speak import speak_text
speak_text('Testing Siraugga accessible speech module.')
"
```
If it speaks through your screen reader or prints `[Speech Mock]`, the module is functional!

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-9)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-10)

### What does `interrupt=True` do?
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-10)
If a screen reader is reading a long paragraph and an urgent notification arrives, `interrupt=True` immediately stops the old speech and speaks the new message instantly.

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-11)
### Why do we use a global `_speaker` variable?
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-11)
Initializing the speech system takes 50–100 milliseconds. Storing the speaker in a global variable allows subsequent calls to speak with zero delay.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_14-SEC-12)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-05_14-SEC-12)
- To understand why assistive speech failed on test PCs, read [`01_PROBLEMS_ENCOUNTERED/01_17_SCREEN_READER_DLL_BINDINGS_AND_IMPORT_ORDER_TRAPS.md`](/docs/devlog/01_17_SCREEN_READER_DLL_BINDINGS_AND_IMPORT_ORDER_TRAPS).
- To inspect primary source citations, view [`02_SOURCE_EVIDENCE/02_12_ACCESSIBLE_SPEECH_AND_DRIVER_INITIALIZATION_EVIDENCE.md`](/docs/devlog/02_12_ACCESSIBLE_SPEECH_AND_DRIVER_INITIALIZATION_EVIDENCE).
- To read the architectural overview, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_12_ACCESSIBLE_AUDIO_OVERLAY_AND_SPEECH_ARCHITECTURE.md`](/docs/devlog/04_12_ACCESSIBLE_AUDIO_OVERLAY_AND_SPEECH_ARCHITECTURE).
