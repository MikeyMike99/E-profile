[//]: # (DOC_ID: SIRA-DOC-02_22 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Accessible Video Player Source Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_22-SEC-1)
This document records source code evidence from `sandbox/templates/video_application.html`. It demonstrates the implementation of the DevCore Media Player, which provides fully accessible HTML5 video playback, screen reader status announcements, and asynchronous playlist persistence.

---

## 2. Decoupled Accessible Control Markup Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_22-SEC-2)
The video controls are separated from the native iframe and rendered with accessible ARIA semantics:

```html
<!-- sandbox/templates/video_application.html: Accessible Controls -->
<div class="controls-overlay" role="region" aria-label="Media Player Controls">
    <div id="media-announcer" class="sr-only" aria-live="polite"></div>

    <button id="playPauseBtn" class="control-btn" aria-label="Play or Pause Video (Shortcut: Space)">
        <span id="playIcon">▶ Play</span>
    </button>

    <button id="seekBackBtn" class="control-btn" aria-label="Rewind 10 seconds (Shortcut: J)">
        ⏪ -10s
    </button>

    <button id="seekForwardBtn" class="control-btn" aria-label="Fast forward 10 seconds (Shortcut: L)">
        ⏩ +10s
    </button>

    <input type="range" id="volumeSlider" min="0" max="100" value="80" 
           aria-label="Volume Slider (Shortcut: Up or Down Arrow)"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="80">
</div>
```

---

## 3. Global Keyboard Shortcuts & Screen Reader Feedback Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_22-SEC-3)
Keyboard events are intercepted at the window level, announcing state changes via the live region:

```javascript
// sandbox/templates/video_application.html: Keyboard event listener
window.addEventListener('keydown', (e) => {
    // Prevent triggering shortcuts when typing in text inputs
    if (e.target.tagName === 'INPUT' && e.target.type === 'text') return;

    const video = document.getElementById('mainVideo');
    const announcer = document.getElementById('media-announcer');

    if (e.code === 'Space') {
        e.preventDefault();
        if (video.paused) {
            video.play();
            announcer.textContent = "Playing.";
        } else {
            video.pause();
            announcer.textContent = "Paused at " + formatTime(video.currentTime);
            savePlaybackState(video.currentTime);
        }
    } else if (e.key === 'j' || e.key === 'J') {
        video.currentTime = Math.max(0, video.currentTime - 10);
        announcer.textContent = "Rewound 10 seconds. Now at " + formatTime(video.currentTime);
    } else if (e.key === 'l' || e.key === 'L') {
        video.currentTime = Math.min(video.duration, video.currentTime + 10);
        announcer.textContent = "Forward 10 seconds. Now at " + formatTime(video.currentTime);
    }
});
```

---

## 4. State Persistence & Playlist JSON Loading Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_22-SEC-4)
The player loads track data asynchronously from `playlist.json` and saves progress to `playback_state.json`:

```javascript
// sandbox/templates/video_application.html: State persistence
async function loadPlaylist() {
    try {
        const resp = await fetch('/static/playlist.json');
        const data = await resp.json();
        renderPlaylist(data.tracks);
        
        // Restore last known playback position
        const stateResp = await fetch('/static/playback_state.json');
        const state = await stateResp.json();
        if (state.last_time && state.track_id) {
            loadTrack(state.track_id, state.last_time);
        }
    } catch (err) {
        console.error("Error loading media playlist:", err);
    }
}

async function savePlaybackState(currentTime) {
    const payload = {
        track_id: currentTrackId,
        last_time: currentTime,
        timestamp: Date.now()
    };
    await fetch('/api/media/save_state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
}
```

---

## 5. Why Order Matters in Media Playback
[//]: # (SECTION_ID: SIRA-DOC-02_22-SEC-5)
1. **Check Target Tag Before Handling Shortcuts**: Ensuring the active focus target is not a text box prevents pressing `Space` while typing a chat prompt from toggling video playback.
2. **Update Screen Reader Before Seeking**: Announcing the new timestamp immediately gives auditory confirmation while the media decoder buffers the new frame.
3. **Save State on Pause**: Persisting progress when the user pauses guarantees that closing the browser preserves the exact resume timestamp.

---

## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_22-SEC-6)
**Q: What is `formatTime(video.currentTime)` doing?**  
A: It converts raw seconds (e.g., `254.3`) into human-readable strings (`"04:14"`) so screen readers speak clear minutes and seconds.

**Q: Why use `aria-valuenow` on the volume slider?**  
A: Screen readers inspect `aria-valuenow` to announce the exact numeric volume percentage to blind users as the slider moves.

**Q: Can this player play local `.mp4` and `.webm` files?**  
A: Yes! The player supports all standard HTML5 audio and video formats mapped through the static directory.
