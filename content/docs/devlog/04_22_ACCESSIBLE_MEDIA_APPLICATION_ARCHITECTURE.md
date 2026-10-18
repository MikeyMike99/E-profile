[//]: # (DOC_ID: SIRA-DEV-04_22 | VERSION: v1.0 | SCOPE: DEV)

# Accessible Media Application Architecture

[//]: # (SECTION_ID: SIRA-DEV-04_22-SEC-1)
## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_22-SEC-1)
Standard web video players rely on visual scrubbers, hovering mouse controls, and embedded iframes that capture keyboard focus. For blind developers and screen reader users, this creates a frustrating experience where playback state cannot be audited and keystrokes become trapped.

The Accessible Media Application Architecture decouples media playback from presentation. Built inside `sandbox/templates/video_application.html`, it provides a headless control layer, top-level keyboard event routing, and continuous asynchronous state synchronization.

```
+-------------------------------------------------------------+
|                Top-Level Web Portal Window                  |
|                 Global Keystroke Listener                   |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
      Space / J / L / Arrows          Screen Reader Engine
               |                             |
               v                             v
+-----------------------------+  +----------------------------+
|   Headless Control Engine   |  |   ARIA Live Announcement   |
|   - video.play() / pause()  |  |   - "Paused at 04:12"      |
|   - video.currentTime += 10 |  |   - "Volume 80%"           |
+-----------------------------+  +----------------------------+
               |
               v
+-------------------------------------------------------------+
|               Asynchronous Persistence Gateway              |
|        Writes timestamp to static/playback_state.json       |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_22-SEC-2)
## 2. Decoupled Headless Control Layer
[//]: # (SECTION_ID: SIRA-DOC-04_22-SEC-2)
Rather than allowing the browser's native `<video>` element or third-party iframes to manage user input, the architecture hides native controls (`controls="false"`) and exposes native HTML `<button>` and `<input>` elements. Every button carries explicit `aria-label` metadata and keyboard accesskeys.

---

[//]: # (SECTION_ID: SIRA-DEV-04_22-SEC-3)
## 3. Auditory Feedback & Live Region Announcements
[//]: # (SECTION_ID: SIRA-DOC-04_22-SEC-3)
Every state transition (Play, Pause, Seek, Speed Adjustment, Track Change) formats a concise human-readable sentence and injects it into `<div id="media-announcer" aria-live="polite">`. Assistive software speaks the update immediately in the user's headphones without interrupting active typing.

---

[//]: # (SECTION_ID: SIRA-DEV-04_22-SEC-4)
## 4. Why Order Matters in Media Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_22-SEC-4)
1. **Intercept Keystrokes at Window Level First**: Capturing shortcuts before the focus moves into the video element prevents the iframe from trapping the keyboard.
2. **Announce State Change Before Async Save**: Firing the screen reader announcement immediately ensures immediate auditory feedback while the background `fetch()` writes state to disk.
3. **Restore Position Before Calling Play**: Setting `currentTime` to the saved timestamp before unpausing prevents the player from briefly echoing audio from track start.

---

[//]: # (SECTION_ID: SIRA-DEV-04_22-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_22-SEC-5)
**Q: Why hide native video controls?**  
A: Native controls across Chrome, Firefox, and Safari have inconsistent keyboard shortcuts and often fail to announce seek timestamps to screen readers.

**Q: Can this architecture play YouTube videos?**  
A: Yes! By wrapping the YouTube IFrame API in headless JavaScript functions, the same accessible keyboard shortcuts control YouTube streams.

**Q: How does the application remember where I left off?**  
A: Every pause and track transition sends an async JSON POST to `/api/media/save_state`, which writes the exact timestamp to `playback_state.json`.
