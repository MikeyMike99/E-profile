[//]: # (DOC_ID: JOSH-PLAY-00A | VERSION: v1.1 | SCOPE: JOSHY Audio Suite)

# Beginner Developer Guide: What Are Screen Readers & How Does This Help Me Build Accessible Apps?

- **Back to Index**: [`00_README_INDEX.md`](/docs/audio_suite/00_README_INDEX)
- **Next Chapter**: [`01_PROBLEMS_WE_ENCOUNTERED.md`](/docs/audio_suite/01_PROBLEMS_WE_ENCOUNTERED)

---

## Introduction: Reading This Documentation as a Beginner Coder
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-1)

If you are a beginner programmer picking up this documentation for the first time—and you did not build `JOSHY.exe` and have never used a screen reader—you will naturally ask several foundational questions before reading Chapters 1 through 4.

This guide answers those exact beginner questions in plain English, giving you a general overview without getting bogged down in complex operating system internals.

---

## Question 1: What Is a Screen Reader? (I Did Not Know They Existed!)
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-2)

A **screen reader** is an essential piece of software that visually impaired and blind individuals run continuously on their computers. Instead of looking at a monitor with a mouse, a visually impaired user navigates Windows entirely with keyboard shortcuts while their screen reader converts what is happening on the computer into:
1. **High-speed spoken audio** (often 300 to 500+ words per minute, customized to the user's preferred voice and pitch).
2. **Refreshable Braille output** (physical pins on a Braille display device connected to the computer that rise and fall in real time so the user can read text with their fingers).

The most common Windows screen readers you will see mentioned in this documentation are:
- **NVDA (NonVisual Desktop Access)**: A very popular, free, open-source screen reader used worldwide.
- **JAWS (Job Access With Speech)**: A widely used commercial professional screen reader.
- **System Access, SuperNova (Dolphin), Window-Eyes, PC-Talker, and ZDSR**: Other regional and commercial screen readers.

---

## Question 2: If the User Already Has a Screen Reader Running, Why Does My App Need Special Code (`accessible_output2`) to Speak?
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-3)

By default, a screen reader only reads standard menus and buttons when a user actively clicks or presses `Tab` inside a window.

However, many applications need to announce information **automatically or from the background**:
- **Example 1 (Background Utilities like JOSHY)**: Imagine a user is typing an email in Microsoft Word and presses a global keyboard shortcut (`Ctrl+Alt+Shift+Right`) to skip to the next song in their music player, or adjusts playback volume. Because the application window is not focused on the screen, a normal screen reader says nothing. With `screenreader_speak("Track: Bohemian Rhapsody")` or `screenreader_speak("Playback Volume 70%")`, your app speaks the update immediately through the user's screen reader without pulling them away from their work.
- **Example 2 (Accessible Games, Timers, & Live Dashboards)**: When a timer runs out, a download finishes, a quiz question updates, or an event happens in an audio game, your Python code needs a way to say: *"Hey Screen Reader, speak and braille this sentence right now!"*

That is what the **`accessible_output2`** library does. It gives your Python program a single universal command (`output("Hello")`) that automatically detects whichever screen reader the user is running and sends your message directly to it.

---

## Question 3: Why Was It a Problem When the App Used "Default Windows TTS (SAPI)" Instead of the Screen Reader?
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-4)

In [`01_PROBLEMS_WE_ENCOUNTERED.md`](/docs/audio_suite/01_PROBLEMS_WE_ENCOUNTERED), you will read that on a second PC, the app spoke using **Microsoft SAPI (`SAPI.SpVoice`)** instead of NVDA or JAWS, and we treated that as a bug. A beginner coder might ask: *"If it still spoke out loud, why is that bad?"*

Here is why visually impaired users strongly prefer their active screen reader over default Windows SAPI TTS:
1. **Talking Over Each Other**: SAPI is a separate built-in Windows voice. If your app speaks using SAPI while the user's screen reader is reading something else, both voices talk at the exact same time in different voices and speeds, making both impossible to understand.
2. **Speed and Control**: Visually impaired users configure their screen reader to a fast, comfortable reading speed and silence it instantly whenever they press the `Ctrl` key. Default SAPI speaks in a slow, unconfigured system voice and ignores the user's screen reader controls.
3. **No Braille Support**: Default SAPI only outputs audio; it cannot send text to a deaf-blind or Braille user's physical Braille display. Routing through `accessible_output2` to NVDA or JAWS supports both speech and Braille automatically.

*(Note: SAPI is still useful as a last-resort backup if a sighted user or a computer with no screen reader running opens your app, which is why `accessible_output2` keeps SAPI at a lower priority of `101` while real screen readers have priority `100`.)*

---

## Question 4: Plain-English Glossary of Technical Terms Used in Chapters 1–4
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-5)

When reading the rest of the documentation, you will see a few technical terms. Here is all you need to know about what they mean:

- **`.dll` File (Dynamic Link Library)**:
  Think of a `.dll` file as a small helper plugin written in C. For Python to send a message to **NVDA**, NVDA provides a tiny 150 KB helper file named `nvdaControllerClient64.dll`. Your Python script hands the text to this `.dll`, and the `.dll` hands it to NVDA.
- **`ctypes` (`ctypes.windll`)**:
  The built-in tool inside Python that opens a `.dll` file so Python can call functions inside it.
- **`COM` (`win32com` / `pythoncom` / `pywintypes`)**:
  A built-in Windows messaging system that lets one program talk to another program without needing a separate `.dll` file. **JAWS** and **Windows SAPI** use COM instead of a `.dll` file.
- **"Freezing" (`sys.frozen`) & Nuitka**:
  When you write a `.py` script on your computer, you have Python installed. Most people downloading your app do **not** have Python installed. **Nuitka** is a compiler that translates your `.py` code into native C machine code and packs everything into a standalone `.exe` file (`JOSHY.exe`). In the Python world, a script packed into an `.exe` is called **"frozen"** (`sys.frozen = True`).
- **Why Freezing Caused the Problem We Solved**:
  When your code runs as a normal `.py` file on your own computer, `nvdaControllerClient64.dll` sits quietly inside your Python installation folder, where `accessible_output2` easily finds it. When packed into a single `.exe` and installed on *someone else's* computer, that Python folder does not exist! Our solution packs a copy of that `.dll` right inside the `.exe` (`nvda_client_data.py`) and automatically places it where `accessible_output2` expects to find it.

---

## Question 5: How Will This Documentation Help Me Create My Own Accessible Application for Visually Impaired Individuals?
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-6)

You do not need to be an expert in C, DLLs, or Nuitka internals to build an accessible application. Because all the hard investigative work documented in Chapters 1–4 is already solved, **you can reuse our exact setup as a plug-and-play building block for any project you create**:

### 1. Copy Two Files Into Your New Project
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-1)
Whenever you start a new Python project (an accessible game, a study tool, a media player, a productivity app, etc.), simply copy these two files from this project into your new folder:
- `screenreader_speak.py` (screenreader_speak.py)
- `nvda_client_data.py` (nvda_client_data.py)

### 2. Speak Any Message With Two Lines of Python Code
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-2)
In your own Python script, import `screenreader_speak` and call it whenever you want to announce something to the user:
```python
from screenreader_speak import screenreader_speak

# Announce when your app starts, when a button is pressed, or when a status changes:
screenreader_speak("Welcome to my accessible app. Press F1 for help.")
```

### 3. Compile Your App for Other Computers Using Chapter 4
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-3)
When you are ready to turn your Python script into a professional `.exe` and Windows Setup Installer so visually impaired users can install it on their PCs without needing Python:
- Open [`04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE.md`](/docs/audio_suite/04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE).
- Copy the Nuitka command from `compile_joshy.bat` (compile_joshy.bat) and replace `main.py` and `JOSHY` with your own script and app name.
- Because `screenreader_speak.py` and `nvda_client_data.py` are already engineered to self-extract and register the screen reader DLLs on any PC, your app will immediately speak through NVDA, JAWS, and other screen readers on every computer it is installed on.

---

- **Next Step**: Continue to [`01_PROBLEMS_WE_ENCOUNTERED.md`](/docs/audio_suite/01_PROBLEMS_WE_ENCOUNTERED) with this background in mind!

---

## Question 6: So the Order of Imports Really Matters in Python?
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-7)

**Yes!** In simple everyday Python scripts (like importing `math`, `random`, or `time`), the order of your `import` lines usually does not matter.

However, when you are building a Windows desktop application that uses **COM (`pywin32`)**, **native `.dll` files**, and **runtime patches**, **the order of imports matters a lot** for three specific reasons:

### 1. `pythoncom` and `pywintypes` Must Be Imported First
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-1)
- Even the original creator of `pywin32` wrote a warning inside `pywintypes.py` (located in `<python_lib>/site-packages/win32/lib/pywintypes.py`) explaining that if another Windows module is imported *before* `pywintypes`, Windows can load the wrong copy of the DLL or fail to find it in a frozen `.exe`.
- When `import pythoncom` and `import pywintypes` run at the very top of [`screenreader_speak.py`](../screenreader_speak.py#L1-L5), Python registers them in its internal loaded-modules list (`sys.modules`). When `accessible_output2` later asks for them to talk to JAWS or SAPI, they are already loaded and ready.

### 2. Setting Up Paths Must Happen *Before* Importing and Calling `Auto()`
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-2)
- Think of `accessible_output2.outputs.auto.Auto()` like a train leaving the station: the moment it starts, it immediately checks the tracks (`platform_utils.paths.embedded_data_path()`) for its `.dll` files.
- If you import and run `Auto()` *before* extracting the `.dll` files, calling `os.add_dll_directory()`, and pointing `embedded_data_path` to the right folder, the train derails before your setup code ever runs.

### 3. The `from module import function` Timing Trap
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-3)
- In Python, when a file runs `from accessible_output2 import load_library` (as seen in `<python_lib>/site-packages/accessible_output2/outputs/base.py` on line 1), it grabs whatever `load_library` function existed **at that exact millisecond**.
- If you try to replace `accessible_output2.load_library` *after* `base.py` has already been imported, `base.py` ignores your change because it already saved the old function!
- That is why in [`screenreader_speak.py`](../screenreader_speak.py#L63-L84), we configure `platform_utils.paths.embedded_data_path` and wrap `accessible_output2.outputs.base.Output.__init__` **first**, and only import `accessible_output2.outputs.auto` inside `_get_screenreader()` **after** all setup steps are complete.


## Cross-References & System Parallels
[//]: # (SECTION_ID: JOSH-PLAY-00A-SEC-8)

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels: Accessibility & Speech Engines (Click to Expand Dropdown)</summary>

| Related Project / Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Echoes of the World Engine** | [World Chunking & Spatial Coordinates](/docs/echoes/CLASS_WORLD_ARCHITECTURE) — Uses the same `screenreader_speak` DLL bindings to announce 3D player positions and soundscape coordinates in real time. | Echoes 3D Engine |
| **E-Profile Portfolio Portal** | [E-Profile Devlog: Chapter 5](/docs/eprofile/DEVLOG#chapter-5-screen-reader-accessibility-as-an-operational-physical-access-point-secops--wcag-synergy) — Establishing screen reader access as the operational physical access point for blind cybersecurity administrators. | E-Profile Devlog |
| **DevCore Web Streaming** | [Devlog 01_05: Screen Reader Spam & Focus Traps](/docs/devlog/01_05_SCREEN_READER_SPAM_AND_PHANTOM_KEYSTROKES) — Preventing audio buffer flooding and managing ARIA live region queues over WebSockets. | 5-Pillar Devlog |

</details>
