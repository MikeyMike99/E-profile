# Pillar 05.37: From-Scratch Creation Guide: Headless Spotify Controller with Global Hotkeys

## Overview & Beginner Context
This guide teaches you how to write an accessible headless Spotify controller script (`t.py`) from scratch. It registers global keyboard shortcuts that work when Spotify is minimized and modulates Spotify's internal volume without changing Windows master audio or screen reader speech.

---

## 1. Line-by-Line Construction

### Block 1: Imports and Spotify Authentication (Lines 1–25)
```python
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import keyboard
import time

CLIENT_ID = "your_client_id_here"
CLIENT_SECRET = "your_client_secret_here"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-modify-playback-state user-read-playback-state"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    cache_path=".spotify_token_cache"
))
```
- Authenticates with Spotify Web API using cached tokens stored locally.

### Block 2: Playback Actions and Independent Volume Modulation (Lines 26–55)
```python
def toggle_play_pause():
    try:
        playback = sp.current_playback()
        if playback and playback.get('is_playing'):
            sp.pause_playback()
            print("[AUDIO]: Paused")
        else:
            sp.start_playback()
            print("[AUDIO]: Playing")
    except Exception as e:
        print(f"[ERROR]: {e}")

def change_volume(delta: int):
    try:
        playback = sp.current_playback()
        if playback and playback.get('device'):
            current = playback['device']['volume_percent']
            new_vol = max(0, min(100, current + delta))
            sp.volume(new_vol)
            print(f"[VOLUME]: Spotify stream set to {new_vol}% (OS Volume unchanged)")
    except Exception as e:
        print(f"[ERROR]: {e}")
```
- Calls `sp.volume()` directly, avoiding the Windows Core Audio API so NVDA speech volume is untouched.

### Block 3: Registering Global Windows Hooks (Lines 56–75)
```python
def main():
    print("Accessible Headless Spotify Controller Active.")
    print("Hotkeys:")
    print("  Ctrl+Alt+Shift+Up   : Play / Pause")
    print("  Ctrl+Alt+[ / ]      : Volume Down / Up (-5% / +5%)")
    
    keyboard.add_hotkey('ctrl+alt+shift+up', toggle_play_pause)
    keyboard.add_hotkey('ctrl+alt+[', lambda: change_volume(-5))
    keyboard.add_hotkey('ctrl+alt+]', lambda: change_volume(5))
    
    keyboard.wait()

if __name__ == '__main__':
    main()
```
- Keeps the script listening in background for hotkey events.

---

## 2. 10-Second Verification Checklist
1. Minimize Spotify to system tray.
2. Open terminal and run `python t.py`.
3. Press `Ctrl + Alt + Shift + Up` -> Spotify plays immediately.

---

## 3. Beginner Coder Q&A

### What is `keyboard.wait()`?
`keyboard.wait()` is a blocking call that keeps your Python script running indefinitely in the background so it can continue intercepting global keyboard events until you press Ctrl+C.

---

## 4. Cross-Reference Navigation
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_38_SPOTIFY_HEADLESS_PLAYBACK_AND_GLOBAL_HOTKEY_TRAPS.md`](/docs/devlog/01_38_SPOTIFY_HEADLESS_PLAYBACK_AND_GLOBAL_HOTKEY_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_34_SPOTIFY_HEADLESS_AND_HOTKEY_HOOK_EVIDENCE.md`](/docs/devlog/02_34_SPOTIFY_HEADLESS_AND_HOTKEY_HOOK_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_31_SPOTIFY_GLOBAL_HOTKEY_AND_VOLUME_AUDIT_LOGS.md`](/docs/devlog/03_31_SPOTIFY_GLOBAL_HOTKEY_AND_VOLUME_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_34_HEADLESS_AUDIO_STREAMING_AND_HOTKEY_ARCHITECTURE.md`](/docs/devlog/04_34_HEADLESS_AUDIO_STREAMING_AND_HOTKEY_ARCHITECTURE)
