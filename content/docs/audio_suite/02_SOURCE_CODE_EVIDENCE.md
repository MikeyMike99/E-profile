[//]: # (DOC_ID: JOSH-PLAY-02_SOURCE_CODE_EVI | VERSION: v1.0 | SCOPE: PLAY)

# Chapter 2: Where the Information Was Found (Primary Source Documents)

- **Previous**: [`01_PROBLEMS_WE_ENCOUNTERED.md`](/docs/audio_suite/01_PROBLEMS_WE_ENCOUNTERED)
- **Next**: [`03_DIAGNOSTIC_TESTS_AND_CONCLUSIONS.md`](/docs/audio_suite/03_DIAGNOSTIC_TESTS_AND_CONCLUSIONS)

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-1)
## Overview
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-1)

Every conclusion in our investigation was verified directly against the official package documentation and the installed source code inside Python 3.13's `site-packages`. Below are the exact source files, relative links, line numbers, and verbatim code excerpts.

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-2)
## Source 1: Official `accessible_output2` Package Metadata & `readme.rst`
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-2)

- **Local Package Info**: `<python_site_packages>/accessible_output2-0.17.dist-info/METADATA` (Lines 1–63)
- **Upstream GitHub Source**: `https://raw.githubusercontent.com/accessibleapps/accessible_output2/master/readme.rst`

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-3)
### Verbatim Excerpt (Lines 1–60 of `METADATA`)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-3)
```text
Metadata-Version: 2.1
Name: accessible-output2
Version: 0.17
Summary: Library to provide speech and braille output to a variety of different screen readers and other accessibility solutions.
Author: Tyler Spivey
Requires-Dist: libloader
Requires-Dist: platform-utils
Requires-Dist: pywin32 ; sys_platform == "win32"

Accessible Output 2: Make your app speak
==================================================
Accessible Output 2 is an MIT licensed library for speaking and brailling through multiple screen readers and other accessibility systems.

Accessible Output 2 makes selection of the appropriate speech and Braille output a snap, and also allows the programmer to select and use a specific output, for instance to force speaking through the Microsoft Speech API even if the user has a screen reader loaded.

    >>> import accessible_output2.outputs.auto
    >>> o = accessible_output2.outputs.auto.Auto()
    >>> o.output("Some text") #attempts to both speak and braille the given text through the first available output
    >>> o.speak("Some other text", interrupt=True)
```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-4)
### What This Source Tells Us
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-4)
1. `accessible_output2` depends on three key packages on Windows: `libloader`, `platform-utils`, and `pywin32`.
2. `Auto()` is designed to automatically prioritize active screen readers (NVDA, JAWS, Window-Eyes, System Access, SuperNova/Dolphin, PC-Talker, ZDSR) and only use Microsoft Speech API (SAPI) if no screen reader is active.

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-5)
## Source 2: `accessible_output2/__init__.py` (DLL Loading & Packaging Hook)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-5)

- **Local File**: `<python_site_packages>/accessible_output2/__init__.py` (Lines 8–49)

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-6)
### Verbatim Excerpt (Lines 8–23 and 38–48)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-6)
```python
def load_library(libname, cdll=False):
    if paths.is_frozen():
        libfile = os.path.join(
            paths.embedded_data_path(), "accessible_output2", "lib", libname
        )
    else:
        libfile = os.path.join(paths.module_path(), "lib", libname)
    if not os.path.exists(libfile):
        _cxfreeze_libfile = os.path.join(
            paths.embedded_data_path(), "lib", "accessible_output2", "lib", libname
        )
        if os.path.exists(_cxfreeze_libfile):
            libfile = _cxfreeze_libfile
    if cdll:
        return ctypes.cdll[libfile]
    return ctypes.windll[libfile]

def find_datafiles():
    import platform
    from glob import glob
    import accessible_output2

    if platform.system() != "Windows":
        return []
    path = os.path.join(accessible_output2.__path__[0], "lib", "*.dll")
    results = glob(path)
    dest_dir = os.path.join("accessible_output2", "lib")
    return [(dest_dir, results)]
```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-7)
### What This Source Tells Us
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-7)
1. Look at `find_datafiles()` (lines 38–48): The library requires its physical `.dll` files (`nvdaControllerClient64.dll`, `nvdaControllerClient32.dll`, `dolapi.dll`, `SAAPI32.dll`, `PCTKUSR64.dll`, `ZDSRAPI_x64.dll`) to be placed in a folder named `accessible_output2\lib`.
2. Look at `load_library()` (lines 8–23): When `paths.is_frozen()` is `True` (inside a compiled `.exe`), it looks for the DLL inside `os.path.join(paths.embedded_data_path(), "accessible_output2", "lib", libname)`.
3. Crucially, if `libfile` does not exist at that path, `load_library()` does **not** return `None` or raise `OutputError`—it executes `ctypes.windll[libfile]` on the missing path, which causes Python's `ctypes` module to raise `FileNotFoundError` and `AttributeError`.

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-8)
## Source 3: `platform_utils/paths.py` (How `embedded_data_path()` Works When Frozen)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-8)

- **Local File**: `<python_site_packages>/platform_utils/paths.py` (Lines 16–142)

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-9)
### Verbatim Excerpt (Lines 16–33, 79–91, and 129–141)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-9)
```python
def is_frozen() -> bool:
    import _imp
    return (
        hasattr(sys, "frozen")
        or hasattr(sys, "importers")
        or _imp.is_frozen("__main__")
    )

def is_pyinstaller() -> bool:
    return is_frozen() and hasattr(sys, "_MEIPASS")

def embedded_data_path() -> str:
    if is_pyinstaller():
        return sys._MEIPASS
    elif is_frozen():
        return app_path()
    else:
        return module_path()
```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-10)
### What This Source Tells Us
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-10)
1. When compiled with Nuitka, `sys.frozen = True` is set, so `is_frozen()` returns `True`.
2. However, Nuitka is **not** PyInstaller, so `sys._MEIPASS` does not exist. `is_pyinstaller()` returns `False`.
3. Therefore, `embedded_data_path()` falls back to `app_path()`, which returns the directory containing the executable (`%LOCALAPPDATA%\Programs\JOSHY\`).
4. When `accessible_output2` combines `embedded_data_path()` with `"accessible_output2\lib"`, it expects the DLLs to live on disk at `%LOCALAPPDATA%\Programs\JOSHY\accessible_output2\lib\`.

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-11)
## Source 4: The Uncaught Exception Bug in `Auto.__init__` (`auto.py` & `base.py`)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-11)

- **Local File 1**: `<python_site_packages>/accessible_output2/outputs/base.py` (Lines 1–55)
- **Local File 2**: `<python_site_packages>/accessible_output2/outputs/auto.py` (Lines 6–26)

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-12)
### Verbatim Excerpt from `base.py` (Lines 1–2 and 40–50)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-12)
```python
from accessible_output2 import load_library
from platform_utils import paths

class Output(object):
    name = "Unnamed Output"

    def __init__(self):
        if hasattr(self, "lib32"):
            self.lib = load_library(self.lib32)
        if hasattr(self, "lib64"):
            self.lib = load_library(self.lib64)
```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-13)
### Verbatim Excerpt from `auto.py` (Lines 10–18)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-13)
```python
class Auto(Output):
    def __init__(self):
        self.outputs = []
        for output in get_outputs():
            try:
                self.outputs.append(output())
            except OutputError:
                pass
```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-14)
### What This Proves (The Root Cause of Problem 3)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-14)
1. In `auto.py`, the loop only catches `except OutputError:`.
2. When `Output.__init__` runs for NVDA on line 46 of `base.py`, `load_library()` raises `AttributeError: C:\...\accessible_output2\lib\nvdaControllerClient64.dll`.
3. Because `AttributeError` does not inherit from `OutputError`, the exception escapes `auto.py` and causes `Auto()` to crash immediately.
4. When `Auto()` crashes, our application catches the error and switches to the emergency fallback: `win32com.client.Dispatch("SAPI.SpVoice")`.

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-15)
## Source 5: PyWin32 Dynamic COM Loading When Frozen (`pywintypes.py` & `libloader/com.py`)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-15)

- **Local File 1**: `<python_site_packages>/libloader/com.py` (Lines 1–36)
- **Local File 2**: `<python_site_packages>/win32/lib/pywintypes.py` (Lines 33–48)

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-16)
### Verbatim Excerpt from `pywintypes.py` (Lines 33–48)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-16)
```python
def __import_pywin32_system_module__(modname):
    # This function imports pywintypesXX.dll / pythoncomXX.dll
    if hasattr(sys, "frozen"):
        # If frozen, look for the dll in sys.path
        for path in sys.path:
            found = os.path.join(path, modname + ".dll")
            if os.path.isfile(found):
                break
        else:
            raise ImportError(f"Module '{modname}' isn't in frozen sys.path {sys.path}")
```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-17)
### What This Source Tells Us
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-17)
When `accessible_output2.outputs` imports `jaws.py` and `sapi5.py`, it imports `libloader.com`, which imports `pywintypes` and `pythoncom`. Importing `pythoncom` and `pywintypes` at the very top of `screenreader_speak.py` (and including `--include-package=win32com` in Nuitka) ensures the C-extension modules are registered before frozen path lookups occur.

---

- **Next Chapter**: Read [`03_DIAGNOSTIC_TESTS_AND_CONCLUSIONS.md`](/docs/audio_suite/03_DIAGNOSTIC_TESTS_AND_CONCLUSIONS) to see the exact live terminal tests we ran to prove every single finding above.

---

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-18)
## Beginner Coder Q&A: Understanding Chapter 2 (Reading Library Source Code)
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-18)

If you are a beginner developer reading Chapter 2, you might wonder how we found these files and why we fixed the problem the way we did. Here are the answers to the four most common beginner questions about this chapter:

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-1)
### 1. "Where did you find these files (`site-packages`), and how did you know you could open them?"
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-1)
- When you install a library in Python using `pip install accessible-output2`, Python downloads the library's `.py` files into a folder on your computer called `Lib\site-packages\`.
- Many beginners think installed libraries are locked "black boxes." In reality, almost all Python libraries are just regular `.py` text files sitting in `site-packages` that you can open and read whenever something behaves unexpectedly.
- You can always find where any library lives on your computer by running:
  ```powershell
  python -c "import accessible_output2; print(accessible_output2.__file__)"
  ```

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-2)
### 2. "If `auto.py` line 14 had a bug (`except OutputError:`), why didn't we just edit `auto.py` inside `site-packages`?"
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-2)
- **Never edit files inside `site-packages` directly!**
- Why? Because `site-packages` only exists on your current computer. If you ever reinstall Python, move your project to another computer, or share your project with another coder who runs `pip install accessible-output2`, `pip` will download a fresh, unedited copy of `accessible_output2` and your fix will be gone.
- Instead, we put the fix inside **our own project file** (`screenreader_speak.py` (screenreader_speak.py)) by wrapping `Output.__init__` at runtime. That way, our fix stays inside our project folder forever and works on any computer without touching `site-packages`.

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-3)
### 3. "In Source 4, why did `from accessible_output2 import load_library` ignore our first fix?"
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-3)
- Think of `accessible_output2` as a main phonebook, and `load_library` as a phone number inside it.
- When `base.py` ran `from accessible_output2 import load_library` on line 1, Python made a **separate copy reference** of that function specifically for `base.py`.
- When our old code later changed `accessible_output2.load_library = _safe_load_library`, we updated the main phonebook, but `base.py` was still holding onto the original function reference!
- However, the original `load_library` function calls `paths.embedded_data_path()` every time it runs. By updating `platform_utils.paths.embedded_data_path` instead, the original function immediately started looking in the right folder.

[//]: # (SECTION_ID: JOSH-PLAY-02_SOURCE_CODE_EVI-SEC-4)
### 4. "What does `lambda: parent_dir` mean when we override `embedded_data_path`?"
[//]: # (SECTION_ID: JOSH-PLAY-02-SEC-4)
- Inside `accessible_output2`, the code calls `paths.embedded_data_path()` with parentheses `()`—meaning it expects `embedded_data_path` to be a **function** it can call, not a plain text string.
- In Python, writing `lambda: parent_dir` is a short, one-line way of writing:
  ```python
  def my_custom_path_function():
      return parent_dir
  ```
- Whenever `accessible_output2` calls `paths.embedded_data_path()`, our `lambda` function hands back the exact folder where our screen reader `.dll` files are located.
