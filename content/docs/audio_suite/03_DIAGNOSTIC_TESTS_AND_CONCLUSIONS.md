[//]: # (DOC_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST | VERSION: v1.0 | SCOPE: PLAY)

# Chapter 3: Diagnostic Tests Executed & How We Reached Our Conclusions

- **Previous**: [`02_SOURCE_CODE_EVIDENCE.md`](/docs/audio_suite/02_SOURCE_CODE_EVIDENCE)
- **Next**: [`04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE.md`](/docs/audio_suite/04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE)

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-1)
## Overview
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-1)

Rather than guessing why the second PC fell back to the default Windows SAPI voice, we executed a sequence of six controlled diagnostic tests in Windows Python 3.13 (`python.exe`).

Below is the complete record of every test command, its exact output, and the conclusion it proved.

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-2)
## Test 1: Unfrozen Baseline Verification
[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-3)

### What We Tested
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-3)
We tested how `accessible_output2.outputs.auto.Auto()` behaves when run normally in Python 3.13 without being frozen into an `.exe`.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-4)
### Exact Command Run
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-4)
```powershell
python -c "import accessible_output2.outputs.auto; a = accessible_output2.outputs.auto.Auto(); print('Loaded outputs:', [o.name for o in a.outputs]); print('Active output:', a.get_first_available_output())"
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-5)
### Exact Output Returned
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-5)
```text
Loaded outputs: ['System Access', 'NVDA', 'jaws', 'Dolphin', 'PC Talker', 'ZDSR', 'sapi5']
Active output: <accessible_output2.outputs.nvda.NVDA object at 0x000001C768ED67B0>
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-6)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-6)
- In normal Python (`sys.frozen` not set), `accessible_output2` uses `paths.module_path()` which resolves to `<python_site_packages>\accessible_output2\lib`.
- Because all `.dll` files exist in `site-packages`, all Windows output classes initialize cleanly and `Auto()` selects `NVDA` (priority `100`) ahead of `sapi5` (priority `101`).

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-7)
## Test 2: Simulating a Frozen Executable (`sys.frozen = True`)
[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-8)

### What We Tested
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-8)
When Nuitka (or any packager) compiles a Python script into an `.exe`, it sets `sys.frozen = True`. We simulated this in Python to see the very first thing that fails inside `accessible_output2`.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-9)
### Exact Command Run
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-9)
```powershell
python -c "import sys; sys.frozen = True; import accessible_output2.outputs.auto; a = accessible_output2.outputs.auto.Auto()"
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-10)
### Exact Output Returned
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-10)
```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "<python_site_packages>\accessible_output2\outputs\__init__.py", line 5, in <module>
    from libloader import com
  File "<python_site_packages>\libloader\com.py", line 3, in <module>
    from pywintypes import com_error
  File "<python_site_packages>\win32\lib\pywintypes.py", line 124, in <module>
    __import_pywin32_system_module__("pywintypes", globals())
  File "<python_site_packages>\win32\lib\pywintypes.py", line 47, in __import_pywin32_system_module__
    raise ImportError(f"Module '{modname}' isn't in frozen sys.path {sys.path}")
ImportError: Module 'pywintypes' isn't in frozen sys.path
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-11)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-11)
- When `sys.frozen = True`, `pywintypes` and `pythoncom` switch their internal DLL loader logic (as seen in `pywintypes.py` line 33).
- Pre-importing `import pythoncom` and `import pywintypes` at the top of `screenreader_speak.py` and bundling `--include-package=win32com` in Nuitka prevents this `ImportError`.

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-12)
## Test 3: Reproducing the Exact Second-PC Crash in `Auto()`
[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-13)

### What We Tested
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-13)
Next, we pre-imported `pythoncom` and `pywintypes`, set `sys.frozen = True`, and called `accessible_output2.outputs.auto.Auto()` where `paths.embedded_data_path()` points to an executable directory that does **not** have the `accessible_output2\lib` subfolder—which is the exact state on the second PC.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-14)
### Exact Command Run
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-14)
```powershell
python -c "import pythoncom, pywintypes, sys; sys.frozen = True; import accessible_output2.outputs.auto; a = accessible_output2.outputs.auto.Auto()"
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-15)
### Exact Output Returned
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-15)
```text
Traceback (most recent call last):
  File "<python_install>\Lib\ctypes\__init__.py", line 461, in __getattr__
    dll = self._dlltype(name)
  File "<python_install>\Lib\ctypes\__init__.py", line 390, in __init__
    self._handle = _dlopen(self._name, mode)
FileNotFoundError: Could not find module '<app_install_dir>\accessible_output2\lib\nvdaControllerClient64.dll' (or one of its dependencies). Try using the full path with constructor syntax.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "<python_site_packages>\accessible_output2\outputs\auto.py", line 13, in __init__
    self.outputs.append(output())
  File "<python_site_packages>\accessible_output2\outputs\base.py", line 46, in __init__
    self.lib = load_library(self.lib64, cdll=self.cdll)
  File "<python_site_packages>\accessible_output2\__init__.py", line 23, in load_library
    return ctypes.windll[libfile]
  File "<python_install>\Lib\ctypes\__init__.py", line 468, in __getitem__
    return getattr(self, name)
  File "<python_install>\Lib\ctypes\__init__.py", line 463, in __getattr__
    raise AttributeError(name)
AttributeError: <app_install_dir>\accessible_output2\lib\nvdaControllerClient64.dll
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-16)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-16)
This traceback proved the entire chain of events on the second computer:
1. When frozen, `accessible_output2/__init__.py` line 10 looks for `os.path.join(paths.embedded_data_path(), "accessible_output2", "lib", "nvdaControllerClient64.dll")`.
2. When that file is missing, `ctypes.windll[libfile]` on line 23 raises `FileNotFoundError`, which `ctypes.__getattr__` converts into `AttributeError`.
3. In `accessible_output2/outputs/auto.py` line 14, the loop only has `except OutputError:`. Because `AttributeError` is not an `OutputError`, `Auto.__init__` crashes completely.
4. When `Auto()` crashed on the second PC, the `except Exception:` safety fallback in `screenreader_speak.py` caught the error and initialized `win32com.client.Dispatch("SAPI.SpVoice")`, causing JOSHY to speak with the default Windows TTS voice.

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-17)
## Test 4: Direct Verification of NVDA DLL and JAWS COM
[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-18)

### What We Tested
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-18)
We tested communicating directly with `nvdaControllerClient64.dll` via `ctypes.windll` and with JAWS via `win32com.client.Dispatch('FreedomSci.JawsApi')` to verify that the underlying screen reader interfaces on Windows work without error.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-19)
### Exact Commands Run
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-19)
```powershell
# 1. Direct NVDA Controller Client Test
python -c "import ctypes; lib = ctypes.windll[r'<project_root>\accessible_output2\lib\nvdaControllerClient64.dll']; print('NVDA running test:', lib.nvdaController_testIfRunning()); print('NVDA speak result:', lib.nvdaController_speakText('JOSHY direct connection test'))"

# 2. Direct JAWS COM Test
python -c "import win32com.client; j = win32com.client.Dispatch('FreedomSci.JawsApi'); print('JAWS dispatch success')"
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-20)
### Exact Outputs Returned
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-20)
```text
NVDA running test: 0
NVDA speak result: 0
JAWS dispatch success
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-21)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-21)
- Return code `0` from `nvdaController_testIfRunning()` and `nvdaController_speakText()` confirms that `nvdaControllerClient64.dll` communicates with NVDA immediately as long as the DLL file is on disk and its path is known.

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-22)
## Test 5: Verifying the `embedded_data_path` Fix in Simulated Frozen Mode
[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-23)

### What We Tested
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-23)
We tested overriding `platform_utils.paths.embedded_data_path` in simulated frozen mode (`sys.frozen = True`) to point to the folder containing `accessible_output2\lib`, and then ran `accessible_output2.outputs.auto.Auto()`.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-24)
### Exact Command Run
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-24)
```powershell
python -c "import pythoncom, pywintypes, sys; sys.frozen = True; import platform_utils.paths; platform_utils.paths.embedded_data_path = lambda: r'<project_root>'; import accessible_output2.outputs.auto; a = accessible_output2.outputs.auto.Auto(); print('Loaded outputs:', [o.name for o in a.outputs]); print('Active output:', a.get_first_available_output()); a.output('Testing accessible output two speech'); print('Speech completed successfully!')"
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-25)
### Exact Output Returned
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-25)
```text
Loaded outputs: ['System Access', 'NVDA', 'jaws', 'Dolphin', 'PC Talker', 'ZDSR', 'sapi5']
Active output: <accessible_output2.outputs.nvda.NVDA object at 0x00000204040F27B0>
Speech completed successfully!
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-26)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-26)
- Overriding `platform_utils.paths.embedded_data_path` fixes `accessible_output2`'s internal path lookup across all modules (`base.py`, `nvda.py`, `dolphin.py`, `system_access.py`, `pc_talker.py`, `zdsr.py`) simultaneously without modifying `accessible_output2`'s source code.

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-27)
## Test 6: Verifying the Fault-Tolerant `Output.__init__` Wrapper
[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-28)

### What We Tested
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-28)
What if a user's machine is missing an optional third-party DLL (such as `PCTKUSR64.dll` or `ZDSRAPI_x64.dll`)? We tested wrapping `accessible_output2.outputs.base.Output.__init__` so that any unexpected exception during DLL loading is converted into `OutputError`.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-29)
### Exact Command Run
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-29)
```powershell
python -c "import os, sys, pythoncom, pywintypes
sys.frozen = True
import platform_utils.paths
platform_utils.paths.embedded_data_path = lambda: r'C:\NonExistentPath'
import accessible_output2.outputs.base
_orig_init = accessible_output2.outputs.base.Output.__init__
def _safe_init(self, *args, **kwargs):
    try:
        _orig_init(self, *args, **kwargs)
    except Exception as e:
        raise accessible_output2.outputs.base.OutputError(str(e))
accessible_output2.outputs.base.Output.__init__ = _safe_init

import accessible_output2.outputs.auto
auto = accessible_output2.outputs.auto.Auto()
print('Available outputs even with non-existent DLL path:', [o.name for o in auto.outputs])
print('Active screenreader:', auto.get_first_available_output().name)"
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-30)
### Exact Output Returned
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-30)
```text
Available outputs even with non-existent DLL path: ['System Access', 'jaws', 'Dolphin', 'sapi5']
Active screenreader: sapi5
```

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-31)
### How We Reached Our Conclusion
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-31)
- Converting any exception inside `Output.__init__` into `OutputError` ensures `Auto.__init__` **never** crashes even if a third-party screen reader DLL is missing or blocked by antivirus software. Instead, `Auto()` cleanly skips that single driver and continues checking the rest of the screen readers.

---

- **Next Chapter**: Read [`04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE.md`](/docs/audio_suite/04_STEP_BY_STEP_SOLUTION_AND_COMPILATION_GUIDE) for the complete, reusable step-by-step recipe to apply this solution in this project and any future Python project.

---

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-32)
## Beginner Coder Q&A: Understanding Chapter 3 (How to Run Tests & Read Tracebacks)
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-32)

If you are a beginner developer reading Chapter 3, you might wonder how these terminal tests work and how you can use the same tricks to debug your own accessible Python apps. Here are the answers to the key beginner questions for this chapter:

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-1)
### 1. "What does `python -c "..."` mean in all of these commands?"
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-1)
- Usually, beginners create a file like `scratch_test.py`, save it, and run `python scratch_test.py`.
- Adding `-c` (which stands for **command**) tells Python: *"Run the code inside these quotation marks right now in memory without needing a `.py` file."*
- Using `python -c "..."` is one of the fastest ways to test whether a library or screen reader works without cluttering your project folder with temporary test files.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-2)
### 2. "Why did you set `sys.frozen = True` in Tests 2, 3, 5, and 6 instead of compiling the `.exe` every time?"
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-2)
- Compiling a program with Nuitka takes 1 to 2 minutes, and when a compiled GUI `.exe` crashes with the console disabled (`--windows-console-mode=disable`), Windows hides the error message so you cannot see what went wrong.
- As we saw in Chapter 2, `accessible_output2` checks `hasattr(sys, "frozen")` to decide whether it is running inside a compiled `.exe`.
- By typing `import sys; sys.frozen = True` inside normal Python, we **tricked** `accessible_output2` into running its `.exe` mode right inside our terminal! That let us see the exact crash message in **1 second** instead of waiting 2 minutes per compile.

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-3)
### 3. "In Test 3, why does the output show TWO error tracebacks (`FileNotFoundError` AND `AttributeError`)?"
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-3)
- Notice the line in the middle of Test 3's output:
  `During handling of the above exception, another exception occurred:`
- This is called a **chained exception** in Python:
  1. **The Top Error (`FileNotFoundError`)** is the **true root cause**: Windows could not find `nvdaControllerClient64.dll` at that folder path.
  2. **The Bottom Error (`AttributeError`)** is the **final exception thrown**: When `ctypes` caught the missing file error, it converted it into an `AttributeError`.
- **Beginner Debugging Rule**: When you see a chained traceback in Python, read the **top error** to understand *why* it broke, and look at the **bottom error** to see *what exception type* your `try...except` block needs to catch!

[//]: # (SECTION_ID: JOSH-PLAY-03_DIAGNOSTIC_TEST-SEC-4)
### 4. "In Test 4, `nvdaController_testIfRunning()` returned `0`. Doesn't `0` mean `False` (Not Running) in Python?"
[//]: # (SECTION_ID: JOSH-PLAY-03-SEC-4)
- This is a very common beginner confusion!
- In Python, `0` means `False` and `1` means `True`.
- However, `nvdaControllerClient64.dll` is written in the **C programming language** for Windows. In C and Windows system functions, a return code of **`0` means "Success / No Error"** (meaning NVDA **is** running and everything succeeded), while any non-zero number is an error code (for example, `1722` means the RPC server / NVDA is unavailable).
- That is why `nvda.py` checks `self.lib.nvdaController_testIfRunning() == 0` to confirm NVDA is active.
