[//]: # (DOC_ID: SIRA-DOC-02_26 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# NVDA DLL Movement Engine & 3D Grid Source Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_26-SEC-1)
This document records source code evidence from the genesis of the developer's journey in late 2024 (documented in `docs/The_Manifesto/01_Echoes_in_the_Void.md` and `docs/The_Manifesto/02_The_Echoes_Architecture.md`). It documents how `NVDAController.dll` was loaded via Python `ctypes` to build a 3D coordinate movement engine that bypassed terminal screen reader silence.

---

## 2. ctypes DLL Loading Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_26-SEC-2)
Direct bridge to the NVDA screen reader C-library:

```python
# Genesis Engine: Direct NVDA DLL binding
import ctypes
import os
import sys

def load_nvda_driver():
    """Loads NVDAController.dll directly into Python memory."""
    dll_path = os.path.abspath("NVDAController.dll")
    if not os.path.exists(dll_path):
        print(f"Warning: {dll_path} not found. Speech unavailable.")
        return None
    
    try:
        nvda = ctypes.windll.LoadLibrary(dll_path)
        # Configure C argument types for unicode strings
        nvda.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
        nvda.nvdaController_speakText.restype = ctypes.c_long
        return nvda
    except Exception as e:
        print(f"Failed to load NVDA DLL: {e}")
        return None
```

---

## 3. 3D Coordinate Grid & 8-Way Compass Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_26-SEC-3)
The mathematical movement engine that eliminated the terminal "blank" problem:

```python
# Genesis Engine: 3D Coordinate Movement & Speech
player_position = {'x': 0, 'y': 0, 'z': 0}
MAP_BOUNDS = {'min_x': -10, 'max_x': 10, 'min_y': -10, 'max_y': 10}

DIRECTIONS = {
    'north': (0, 1),
    'northeast': (1, 1),
    'east': (1, 0),
    'southeast': (1, -1),
    'south': (0, -1),
    'southwest': (-1, -1),
    'west': (-1, 0),
    'northwest': (-1, 1)
}

def move_player(direction: str, nvda_handle):
    global player_position
    if direction not in DIRECTIONS:
        return
    
    dx, dy = DIRECTIONS[direction]
    new_x = player_position['x'] + dx
    new_y = player_position['y'] + dy
    
    # Boundary enforcement
    if not (MAP_BOUNDS['min_x'] <= new_x <= MAP_BOUNDS['max_x'] and
            MAP_BOUNDS['min_y'] <= new_y <= MAP_BOUNDS['max_y']):
        if nvda_handle:
            nvda_handle.nvdaController_speakText("Blocked! Wall ahead.")
        return

    player_position['x'] = new_x
    player_position['y'] = new_y
    
    # Speak new state immediately in player's headphones
    msg = f"{direction.capitalize()}. Position: {new_x}, {new_y}, {player_position['z']}"
    if nvda_handle:
        nvda_handle.nvdaController_speakText(msg)
```

---

## 4. State Persistence to JSON Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_26-SEC-4)
Isolating player state from logic to survive program restarts:

```python
# Genesis Engine: Saving player state
import json

STATE_FILE = "player_log.json"

def save_player_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(player_position, f, indent=2)
```

---

## 5. Why Order Matters in Audio Movement
[//]: # (SECTION_ID: SIRA-DOC-02_26-SEC-5)
1. **Define Argument Types Before DLL Function Call**: Setting `argtypes = [ctypes.c_wchar_p]` is mandatory; passing a Python string to a C function without specifying `wchar_p` causes Windows memory access violations.
2. **Validate Boundaries Before State Mutation**: Updating `player_position` before checking boundaries would allow players to walk through walls and get trapped in invalid coordinates.
3. **Cancel Prior Speech Before Announcing Rapid Moves**: Canceling previous speech prevents a walking player from having coordinate announcements lag multiple seconds behind actual movement.

---

## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_26-SEC-6)
**Q: What is a `c_wchar_p` in ctypes?**  
A: A C-compatible pointer to a wide character string (UTF-16 on Windows), required for passing Unicode text to Windows API DLLs.

**Q: Why was this movement engine built with pure math instead of a 2D array?**  
A: A mathematical grid requires almost zero memory compared to large 2D tile arrays and easily expands infinitely in all directions.

**Q: Did this script run with a visual window?**  
A: No! It was completely headless and auditory, proving that complex spatial worlds can be experienced purely through audio feedback.
