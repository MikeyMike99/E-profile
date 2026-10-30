import os
import sys
import shutil
import subprocess
import site

print("==========================================")
print("  Antigravity / Siraugga Compiler Initiated (Nuitka Secure)")
print("==========================================")

base_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Discover agy CLI
agy_path = shutil.which('agy')

if not agy_path:
    search_paths = site.getsitepackages()
    try:
        search_paths.append(site.getusersitepackages())
    except:
        pass
        
    for loc in search_paths:
        base_python_dir = os.path.dirname(os.path.dirname(loc))
        for possible_name in ["agy.exe", "agy", "agy.bat", "agy.cmd"]:
            potential_path = os.path.join(base_python_dir, 'Scripts', possible_name)
            if os.path.exists(potential_path):
                agy_path = potential_path
                break
        if agy_path: break

if not agy_path or not os.path.exists(agy_path):
    try:
        for loc in search_paths:
            base_dir_pkg = os.path.dirname(os.path.dirname(loc))
            for root, dirs, files in os.walk(base_dir_pkg):
                for possible_name in ["agy.exe", "agy", "agy.bat", "agy.cmd"]:
                    if possible_name in files:
                        agy_path = os.path.join(root, possible_name)
                        break
                if agy_path and os.path.exists(agy_path):
                    break
            if agy_path and os.path.exists(agy_path):
                break
    except:
        pass

if not agy_path or not os.path.exists(agy_path):
    print("WARNING: agy.exe not found! Creating dummy.")
    with open("agy.exe", "wb") as f:
        f.write(b"MZ_DUMMY_EXECUTABLE")
    agy_path = os.path.abspath("agy.exe")

# Find heavy open-source libraries to exclude from C-compilation
import google
import pygments
import pydantic

google_path = list(google.__path__)[0] if hasattr(google, '__path__') else os.path.dirname(google.__file__)
pygments_path = os.path.dirname(pygments.__file__)
pydantic_path = os.path.dirname(pydantic.__file__)


print("[Build] Executing VFS Packer...")
subprocess.run([sys.executable, "pack_vfs.py"], check=True)

nuitka_args = [
    sys.executable, "-m", "nuitka",
    "--disable-ccache",
    "--assume-yes-for-downloads",
    "--standalone",
    "--onefile",
    "--low-memory",
    
    # Exclude open-source bloat from C-compilation to prevent MSVC OOM crashes
    "--nofollow-import-to=google",
    "--nofollow-import-to=pygments",
    "--nofollow-import-to=pydantic",
    
    # Include them as raw Python data files instead
    f"--include-data-dir={google_path}=google",
    f"--include-data-dir={pygments_path}=pygments",
    f"--include-data-dir={pydantic_path}=pydantic",
    
    "--include-package=security",
    "--include-package=plugins",
    f"--include-data-file={agy_path}={os.path.basename(agy_path)}",
    "--include-data-file=assets.bin=assets.bin",
    "--output-filename=Siraugga.exe",
    "desktop_app.py"
]

print("Running command:", " ".join(nuitka_args))
subprocess.run(nuitka_args, check=True)
