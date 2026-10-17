[//]: # (DOC_ID: SIRA-DOC-05_28 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# NVDA DLL Coordinate Audio Engine from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_28-SEC-1)
Standard game loops and command-line scripts rely on visual monitors. For blind developers, terminal output often results in the frustrating "blank, blank, blank" screen reader silence.

This guide details how to build the foundational 3D coordinate movement engine from scratch (`echoes_engine.py`). Using Python `ctypes`, it loads `NVDAController.dll` directly into process memory, calculates spatial coordinates on an 8-way directional compass, announces position instantly in the player's ear, and saves world state to JSON.

```
+-------------------------------------------------------------+
|                  Keyboard Keystroke Input                   |
|                   (North, South, East, West)                |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|               Mathematical 3D Grid Engine                   |
|   - Updates (x, y, z) coordinates                           |
|   - Enforces boundary walls (-10 to +10)                    |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
      ctypes C-Function Call         State Persistence
      NVDAController.dll             Writes to player_log.json
               |                             |
               v                             v
+-----------------------------+  +----------------------------+
|     NVDA Screen Reader      |  |     Persistent Memory      |
|  "North. Position: 0, 1, 0" |  |     (Survives reboots)     |
+-----------------------------+  +----------------------------+
```

---

## 2. Complete Python Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_28-SEC-2)
Save the following script as `echoes_engine.py`:

```python
import os
import sys
import json
import ctypes

STATE_FILE = "player_log.json"
BOUNDS = {"min_x": -5, "max_x": 5, "min_y": -5, "max_y": 5}

DIRECTIONS = {
    "n": (0, 1, "North"),
    "s": (0, -1, "South"),
    "e": (1, 0, "East"),
    "w": (-1, 0, "West"),
    "ne": (1, 1, "North-East"),
    "nw": (-1, 1, "North-West"),
    "se": (1, -1, "South-East"),
    "sw": (-1, -1, "South-West"),
}

class AccessibleAudioEngine:
    def __init__(self):
        self.player_pos = {"x": 0, "y": 0, "z": 0}
        self.nvda = self._init_nvda()
        self.load_state()

    def _init_nvda(self):
        """Loads the C-library NVDAController.dll via ctypes."""
        try:
            dll = ctypes.windll.LoadLibrary("NVDAController.dll")
            dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
            dll.nvdaController_speakText.restype = ctypes.c_long
            print("[AUDIO] NVDAController.dll initialized successfully.")
            return dll
        except Exception:
            print("[AUDIO] NVDAController.dll not found. Falling back to stdout speech.")
            return None

    def speak(self, text: str):
        """Speaks text via NVDA or prints to console."""
        print(f">> {text}")
        if self.nvda:
            self.nvda.nvdaController_speakText(text)

    def load_state(self):
        """Loads saved player coordinates from disk."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    self.player_pos = json.load(f)
                self.speak(f"World loaded. Resuming at {self.player_pos['x']}, {self.player_pos['y']}")
            except Exception:
                pass

    def save_state(self):
        """Saves current coordinates to JSON."""
        with open(STATE_FILE, "w") as f:
            json.dump(self.player_pos, f, indent=2)

    def move(self, dir_key: str):
        """Calculates coordinate shift and announces new position."""
        dir_key = dir_key.lower().strip()
        if dir_key not in DIRECTIONS:
            self.speak("Unknown direction. Use N, S, E, W, NE, NW, SE, SW.")
            return

        dx, dy, dir_name = DIRECTIONS[dir_key]
        target_x = self.player_pos["x"] + dx
        target_y = self.player_pos["y"] + dy

        # Enforce boundaries
        if not (BOUNDS["min_x"] <= target_x <= BOUNDS["max_x"] and
                BOUNDS["min_y"] <= target_y <= BOUNDS["max_y"]):
            self.speak(f"Thud! Blocked by wall at {dir_name}.")
            return

        self.player_pos["x"] = target_x
        self.player_pos["y"] = target_y
        self.save_state()

        self.speak(f"{dir_name}. Coordinates: {target_x}, {target_y}")

if __name__ == "__main__":
    engine = AccessibleAudioEngine()
    print("\nAccessible Grid Engine Active. Type 'n', 's', 'e', 'w', or 'quit':")
    
    # Simulate movement steps
    for step in ["n", "n", "e", "w", "s"]:
        engine.move(step)

    # Clean up test state
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
```

---

## 3. Why Order Matters in Audio Game Loops
[//]: # (SECTION_ID: SIRA-DOC-05_28-SEC-3)
1. **Define `c_wchar_p` Before Calling DLL**: Failing to declare the argument type results in Python passing standard 8-bit strings to a 16-bit wide character function, producing memory corruption.
2. **Check Bounds Before Mutating State**: Testing collision boundaries before modifying `self.player_pos` ensures the player never enters an invalid spatial coordinate.
3. **Save State Immediately After Position Shift**: Writing to `player_log.json` on each move guarantees world continuity even if the user abruptly terminates the process.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_28-SEC-4)
**Q: What is a wide character pointer (`c_wchar_p`)?**  
A: A pointer to a sequence of 16-bit Unicode characters used natively by Windows API functions to support international text.

**Q: Can this run on Linux or Mac?**  
A: `NVDAController.dll` is Windows-specific for the NVDA screen reader. On Linux, developers bind to `speech-dispatcher` or `Orca`, and on macOS they call `AVSpeechSynthesizer`.

**Q: Why was this the start of the DevCore journey?**  
A: It proved that software does not need monitors or visual graphics to be deeply immersive, responsive, and completely accessible.
