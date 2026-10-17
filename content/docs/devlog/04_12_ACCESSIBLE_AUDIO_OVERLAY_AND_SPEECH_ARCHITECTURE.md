[//]: # (DOC_ID: SIRA-DOC-04_12 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 04_12: Accessible Audio Overlay & Speech Architecture

An architectural guide to Siraugga's **Accessible Audio Overlay & Speech Engine**—combining headless audio streaming, background global keyboard listeners, and dynamic multi-driver screen reader integration.

---

## Architectural Overview & Topology
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-1)

Visually impaired developers need to control media, review agent output, and receive auditory notifications without having to manually switch focus away from their code editor or terminal.

The Accessible Audio Overlay architecture operates on three synchronized planes:

```
┌────────────────────────────────────────────────────────┐
│              GLOBAL KEYBOARD HOOK PLANE                │
│    (pynput / Win32 RegisterHotKey - System-Wide)       │
│                                                        │
│    • Captures global hotkeys (Ctrl+Alt+P, Ctrl+Alt+S)  │
│    • Operates headlessly with ZERO window focus        │
└───────────────────────────┬────────────────────────────┘
                            │ Dispatches Action Event
                            ▼
┌────────────────────────────────────────────────────────┐
│               HEADLESS MEDIA ENGINE PLANE              │
│    (Background Audio Pipeline / Spotify Connect)       │
│                                                        │
│    • Plays, pauses, adjusts volume in background       │
│    • Emits track metadata strings to Speech Engine     │
└───────────────────────────┬────────────────────────────┘
                            │ Sends Speech String
                            ▼
┌────────────────────────────────────────────────────────┐
│             ASSISTIVE SPEECH DISPATCH PLANE            │
│                 (screenreader_speak.py)                │
│                                                        │
│    1. NVDA Controller Client DLL (Direct Memory IPC)   │
│    2. JAWS COM Automation Interface                    │
│    3. Windows SAPI5 Speech Synthesizer (Fallback)      │
└────────────────────────────────────────────────────────┘
```

---

## The Assistive Driver Hierarchy
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-2)

When speech output is requested, the engine cascades through three tiers of assistive output:
1. **Tier 1: Direct NVDA Memory IPC (`nvdaControllerClient64.dll`)**:
   - Highest priority. Sends text directly into NVDA's active synthesizer buffer via unmanaged C++ calls.
   - Preserves user speech rate, pitch, and voice profile.
2. **Tier 2: JAWS Automation API**:
   - If NVDA is not running, attempts connection to Freedom Scientific's JAWS speech server.
3. **Tier 3: Windows SAPI5 COM Driver**:
   - Final fallback if no active screen reader is detected. Uses the built-in Microsoft Speech API.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-3)

In multi-driver assistive audio architectures, initialization order guarantees driver binding:
1. **Extract Bundled DLLs Before Library Import**: Screen reader discovery occurs during module load time. Writing the DLLs to disk must precede importing `accessible_output2`.
2. **Register DLL Directory with Windows NT Kernel**: Python 3.8+ blocks unverified DLL paths. `os.add_dll_directory()` must run before any Win32 `LoadLibrary` call.
3. **Initialize Thread COM Apartment Before Dispatch**: Invoking `pythoncom.CoInitialize()` inside the speech thread must occur before instantiating speech objects.

---

## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-4)

To add multi-driver screen reader speech output to your application in under 2 minutes:

```python
import sys, os

# Step 1: Import the hardened speech module
from screenreader_speak import speak_text

def notify_user_accessibly(message: str):
    # Step 2: Dispatch speech directly to NVDA / JAWS / SAPI
    print(f"[Console]: {message}")
    speak_text(message)

# Example Usage:
notify_user_accessibly("Build completed successfully. Zero errors.")
```

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-5)

### Why can't I just use `pyttsx3`?
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-6)
`pyttsx3` only talks to the computer's generic default robotic voice (SAPI5). It cannot talk to NVDA or JAWS. Visually impaired developers listen to NVDA at 400+ words per minute; generic TTS is painfully slow and jarring.

### How do global keyboard shortcuts work without window focus?
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-7)
The application registers low-level keyboard hooks with the Windows operating system (`SetWindowsHookEx` or `RegisterHotKey`). The OS intercepts the keys before they reach the active window and routes them to our background handler.

### Does this require administrator privileges to run?
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-8)
No. The embedded DLL is written to `%LOCALAPPDATA%`, which does not require admin rights, and user-level keyboard hooks run with standard privileges.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_12-SEC-9)
- To understand why assistive speech failed on secondary PCs, read [`01_PROBLEMS_ENCOUNTERED/01_17_SCREEN_READER_DLL_BINDINGS_AND_IMPORT_ORDER_TRAPS.md`](/docs/devlog/01_17_SCREEN_READER_DLL_BINDINGS_AND_IMPORT_ORDER_TRAPS).
- To inspect the primary source code of the dynamic DLL extractor, view [`02_SOURCE_EVIDENCE/02_12_ACCESSIBLE_SPEECH_AND_DRIVER_INITIALIZATION_EVIDENCE.md`](/docs/devlog/02_12_ACCESSIBLE_SPEECH_AND_DRIVER_INITIALIZATION_EVIDENCE).
- To build the complete accessible speech engine from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_14_ACCESSIBLE_SCREEN_READER_SPEECH_MODULE_FROM_SCRATCH.md`](/docs/devlog/05_14_ACCESSIBLE_SCREEN_READER_SPEECH_MODULE_FROM_SCRATCH).
