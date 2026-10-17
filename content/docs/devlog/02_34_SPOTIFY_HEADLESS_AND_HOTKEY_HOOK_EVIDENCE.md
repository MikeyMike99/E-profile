[//]: # (DOC_ID: JOSH-DOC-02_34 | VERSION: v1.0 | SCOPE: JOSHY Audio Suite)

# Pillar 02.34: Source Code Evidence: Spotify Headless Controller & Hotkey Hooks

## Overview & Context
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-1)
This document cites primary source evidence from the accessible audio playback suite (`Audio_pllayback_suite/t.py`), illustrating how global keyboard hooks capture media keypresses when the application is minimized, and how Spotify Web API calls adjust track playback without touching the OS master volume.

---

## Source Citation 1: Global Keypress Interception Without Focus (`Audio_pllayback_suite/t.py`)
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-2)

```python
# Location: Audio_pllayback_suite/t.py
# Low-Level Global Keyboard Listener & Hotkey Routing

import keyboard

def setup_global_hotkeys(controller):
    """Registers global hotkeys that fire regardless of active window focus."""
    # Play / Pause toggle: Ctrl + Alt + Shift + Up
    keyboard.add_hotkey('ctrl+alt+shift+up', controller.toggle_play_pause)
    
    # Next track: Ctrl + Alt + Shift + Right
    keyboard.add_hotkey('ctrl+alt+shift+right', controller.next_track)
    
    # Previous track: Ctrl + Alt + Shift + Left
    keyboard.add_hotkey('ctrl+alt+shift+left', controller.prev_track)
    
    # Volume control: Alt + Ctrl + Left/Right Bracket (Independent of OS Volume)
    keyboard.add_hotkey('ctrl+alt+[', controller.volume_down)
    keyboard.add_hotkey('ctrl+alt+]', controller.volume_up)
```

### What This Source Proves
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-3)
- The application bypasses window focus requirements by utilizing low-level Windows global hooks, allowing blind developers to manipulate media playback from within any terminal, text editor, or IDE.

---

## Source Citation 2: Independent Spotify Track Volume Adjustment
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-4)

```python
# Location: Audio_pllayback_suite/t.py
# Modifying Stream Volume via Spotify Web API

def adjust_spotify_volume(sp, step: int = 5):
    """Changes Spotify internal stream volume without altering OS master speech volume."""
    try:
        playback = sp.current_playback()
        if not playback or not playback.get('device'):
            return False
            
        current_vol = playback['device']['volume_percent']
        new_vol = max(0, min(100, current_vol + step))
        sp.volume(new_vol)
        return new_vol
    except Exception as e:
        log_error(f"Failed to adjust volume: {e}")
        return None
```

### What This Source Proves
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-5)
- By calling `sp.volume(new_vol)` through the Spotify Web API, the audio controller alters only the music stream's gain level, leaving the developer's NVDA screen reader audio completely untouched.

---

## 3. Why Order Matters in Audio Hook Setup
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-3)
1. **Initialize API Client Before Key Hook Binding**: The Spotify client (`spotipy.Spotify`) must be authenticated with cached tokens before registering hotkeys to prevent callback exceptions on early keystrokes.
2. **Bind Speech Module Before Playback Actions**: Initializing `screenreader_speak` prior to hotkey execution ensures that status updates (e.g. "Playing: Track Name") are immediately spoken.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-4)

### What is the difference between `keyboard.add_hotkey` and normal UI event listeners?
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-6)
Normal UI listeners only hear keys pressed while the application's window has active OS focus. `keyboard.add_hotkey` hooks into the Windows message dispatcher at the driver level, intercepting key combinations regardless of which window is active.

### Why clamp the volume between 0 and 100?
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-7)
The Spotify API returns an error if you send a volume value less than 0 or greater than 100. Using `max(0, min(100, ...))` ensures the calculation never passes invalid bounds.

---

## 5. Cross-Reference Navigation
[//]: # (SECTION_ID: JOSH-DOC-02_34-SEC-5)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_38_SPOTIFY_HEADLESS_PLAYBACK_AND_GLOBAL_HOTKEY_TRAPS.md`](/docs/devlog/01_38_SPOTIFY_HEADLESS_PLAYBACK_AND_GLOBAL_HOTKEY_TRAPS)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_31_SPOTIFY_GLOBAL_HOTKEY_AND_VOLUME_AUDIT_LOGS.md`](/docs/devlog/03_31_SPOTIFY_GLOBAL_HOTKEY_AND_VOLUME_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_34_HEADLESS_AUDIO_STREAMING_AND_HOTKEY_ARCHITECTURE.md`](/docs/devlog/04_34_HEADLESS_AUDIO_STREAMING_AND_HOTKEY_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_37_HEADLESS_SPOTIFY_CONTROLLER_FROM_SCRATCH.md`](/docs/devlog/05_37_HEADLESS_SPOTIFY_CONTROLLER_FROM_SCRATCH)
