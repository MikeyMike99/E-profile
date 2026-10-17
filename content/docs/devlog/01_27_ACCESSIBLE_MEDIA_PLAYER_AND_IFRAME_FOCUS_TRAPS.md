# Accessible Media Player & Iframe Focus Traps

## 1. The Problem: The Embedded Video Focus Trap
Modern web developers frequently embed video and audio players using native `<video>` elements or third-party `<iframe>` tags. While sighted users easily click controls with a mouse, embedded players are notorious keyboard and screen reader death traps.

Once keyboard focus enters a raw video `<iframe>`, the third-party player intercepts all keystrokes. Sighted navigation disappears, and screen reader users cannot `Tab` or `Shift+Tab` back into the main developer workspace.

```
+-------------------------------------------------------------+
|                     Main Web Workspace                      |
|                  User presses 'Tab' key                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|             Embedded Third-Party Video Iframe               |
|            [KEYBOARD TRAP: Focus Cannot Escape]             |
|   - Spacebar doesn't pause cleanly                          |
|   - Left/Right arrows don't announce seek position          |
|   - Escape key fails to return focus to chat                |
+-------------------------------------------------------------+
```

---

## 2. Inaudible Playback Feedback
In standard web players, adjusting volume or seeking forward 10 seconds provides only visual cues (like a moving timeline scrubber). To a blind developer, there is zero auditory feedback indicating whether the track paused, what percentage volume is set to, or how many minutes remain.

---

## 3. The Solution: Accessible Headless Overlay & State JSON
To solve this, Siraugga engineered the DevCore Media Player (`sandbox/templates/video_application.html`):
1. **Decoupled Headless Controls**: All playback controls (Play, Pause, Seek, Next Track) are rendered as native HTML buttons outside the video viewport, equipped with explicit `aria-label` tags.
2. **Global Keyboard Shortcuts**: Standard keys (`Space` for Toggle, `J`/`L` for -/+ 10s seek, `M` for Mute) are captured at the window level, preventing iframe trapping.
3. **Live Region Status Announcements**: Any action updates an `aria-live="polite"` container (e.g., "Paused at 04:12", "Volume 80%").
4. **State Persistence**: The current track index and timestamp are continuously written to `playback_state.json` and `playlist.json`, allowing instant resumption after browser refresh.

---

## 4. Why Order Matters in Accessible Media Control
1. **Intercept Global Keys Before Iframe Focus**: Capturing media shortcuts at the document level prevents the nested media frame from swallowing keyboard navigation.
2. **Update Live Region Before Adjusting Track**: Informing the screen reader of the seek operation before updating the video buffer ensures auditory feedback precedes audio playback.
3. **Persist State to Disk on Pause**: Saving timestamp to `playback_state.json` immediately upon pausing protects progress against accidental tab closures.

---

## 5. Beginner Coder Q&A
**Q: What is a keyboard trap?**  
A: A defect where a keyboard user can focus into an element (like an iframe or dialog) but cannot navigate out using standard Tab or Escape keys.

**Q: Why use `aria-live="polite"` for media controls?**  
A: `polite` waits until any ongoing screen reader announcement finishes before speaking the playback time, preventing speech from stuttering.

**Q: Where are the playlist tracks defined?**  
A: In `sandbox/static/playlist.json`, which the player loads asynchronously on boot.
