[//]: # (DOC_ID: SIRA-ARCH-05_10 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.10: From-Scratch Creation Guide: WSL/Windows File Bridge

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_09_OFFLINE_PASSWORD_CRACK_LAB_FROM_SCRATCH.md`](/docs/devlog/05_09_OFFLINE_PASSWORD_CRACK_LAB_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-1)

This guide walks you through building a **Two-Stage Windows-to-WSL File Transfer Bridge** (`wsl_io_bridge.py`) from a blank editor.

This utility completely eliminates the "Broken Pipe" and silent file truncation bugs that occur when piping large files from Windows web servers into Linux environments via `wsl.exe` stdin streams.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-3)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-3)
```bash
nano wsl_io_bridge.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-4)
### Step 2: Implement the Two-Stage Transfer Function (Lines 1–45)
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-4)
```python
import os
import subprocess
import tempfile

def transfer_to_wsl(file_content: str, linux_dest_path: str):
    """Safely transfers large text/markdown files from Windows into WSL Linux."""
    # Stage 1: Stage file to Windows Host Temporary Directory
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as tf:
        tf.write(file_content)
        win_temp_path = tf.name

    try:
        # Stage 2: Convert Windows path to Linux mount format using wslpath
        wsl_src_path = subprocess.check_output(
            ["wsl.exe", "wslpath", "-a", win_temp_path],
            stderr=subprocess.PIPE
        ).decode('utf-8').strip()

        # Stage 3: Perform atomic file copy inside Linux
        subprocess.check_call(
            ["wsl.exe", "cp", wsl_src_path, linux_dest_path],
            stderr=subprocess.PIPE
        )
        print(f"[BRIDGE SUCCESS] File copied to Linux: {linux_dest_path}")

    finally:
        # Stage 4: Mandatory Host Cleanup (Clean Workspace Protocol)
        if os.path.exists(win_temp_path):
            os.remove(win_temp_path)
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-5)
## Why Order Matters in Host-to-WSL Transfers
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-5)

1. **Close Windows File Descriptor Before Invoking Copy**:
   - The file handle must exit the `with tempfile` context manager *before* `wsl.exe` tries to copy it. If Windows still holds an exclusive write lock, the Linux copy command will fail with a sharing violation.
2. **Execute Path Conversion Before Copy**:
   - `wslpath -a` must resolve the exact absolute mount path before calling `cp`. Passing raw Windows backslash paths (`C:\...`) to Linux `cp` triggers a "No such file or directory" error.
3. **Always Clean Up in `finally`**:
   - The temporary Windows file must be erased in a `finally` block, ensuring that even if Linux disk quotas are exceeded, dead files do not accumulate on the Windows host.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-6)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-6)

Verify that your transfer bridge moves files without pipe corruption:

```bash
python3 -c "
from wsl_io_bridge import transfer_to_wsl
import subprocess

test_data = '# Cross-OS Bridge Test\n' + ('Data integrity line.\n' * 200)
transfer_to_wsl(test_data, '/tmp/bridge_verified.md')

# Read back from Linux
result = subprocess.check_output(['wsl.exe', 'cat', '/tmp/bridge_verified.md']).decode('utf-8')
assert result == test_data
print('[PASS] Cross-OS file bridge verified with 100% byte integrity!')
"
```

**Expected Output**:
```text
[BRIDGE SUCCESS] File copied to Linux: /tmp/bridge_verified.md
[PASS] Cross-OS file bridge verified with 100% byte integrity!
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-7)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-8)

### Q: Why not use `wsl.exe bash -c "echo 'text' > file"`?
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-8)
**A:** If your text contains single quotes, double quotes, dollar signs (`$`), or backticks, Bash will attempt to evaluate them as shell variables or commands, corrupting your text. Using file copies avoids all shell escaping issues.

[//]: # (SECTION_ID: SIRA-ARCH-05_10-SEC-9)
### Q: Does this work for binary files (like images or zip archives)?
[//]: # (SECTION_ID: SIRA-DOC-05_10-SEC-9)
**A:** Yes! Simply open the temporary file in binary mode (`mode='wb'`) and write raw bytes. The `wsl.exe cp` command will transfer the binary file flawlessly.
