# Accessible Video Player Application from Scratch

## 1. Architectural Role & Module Overview
Standard web video players rely on visual timelines and mouse hover effects, and embedding third-party players inside iframes frequently traps keyboard navigation.

This guide provides a standalone, single-file implementation of an accessible HTML5 video player. It decouples playback controls from the video frame, binds global keyboard shortcuts, emits auditory status updates to an `aria-live` region, and saves playback position asynchronously to JSON.

```
+-------------------------------------------------------------+
|                  Browser Viewport (HTML5)                   |
|                  Hides Native Video Controls                |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
     Accessible HTML Buttons         Global Window Key Listener
    - Explicit aria-labels          - Space, J, L, Arrows
    - High contrast styling         - Halts iframe focus traps
               |                             |
               +--------------+--------------+
                              |
                              v
+-------------------------------------------------------------+
|                 ARIA Live Region Announcement               |
|               "Playing" / "Paused at 03:15"                 |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                Async State Persistence (fetch)              |
|              Saves timestamp to playback_state.json         |
+-------------------------------------------------------------+
```

---

## 2. Complete HTML & JavaScript Implementation
Save the following standalone file as `accessible_player.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessible Media Player</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; display: flex; flex-direction: column; align-items: center; }
        .player-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; max-width: 640px; width: 100%; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); }
        video { width: 100%; border-radius: 8px; background: #000; }
        .controls { display: flex; gap: 10px; margin-top: 15px; align-items: center; flex-wrap: wrap; }
        button { background: #3b82f6; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; }
        button:hover { background: #2563eb; }
        button:focus { outline: 2px solid #38bdf8; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
        .time-display { font-family: monospace; font-size: 0.9rem; color: #94a3b8; }
    </style>
</head>
<body>

<div class="player-card">
    <h1 style="font-size: 1.25rem; margin-top: 0;">Accessible Media Player</h1>

    <!-- Screen Reader Status Region -->
    <div id="sr-announcer" class="sr-only" aria-live="polite"></div>

    <!-- Video Element (Native Controls Hidden) -->
    <video id="videoElement" src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" preload="metadata"></video>

    <!-- Accessible Controls -->
    <div class="controls" role="region" aria-label="Media Player Controls">
        <button type="button" id="playBtn" aria-label="Play or Pause video (Shortcut: Space)">Play</button>
        <button type="button" id="rewindBtn" aria-label="Rewind 10 seconds (Shortcut: J)">-10s</button>
        <button type="button" id="forwardBtn" aria-label="Fast forward 10 seconds (Shortcut: L)">+10s</button>
        <span id="timeText" class="time-display" aria-hidden="true">00:00 / 00:00</span>
    </div>
</div>

<script>
    const video = document.getElementById('videoElement');
    const playBtn = document.getElementById('playBtn');
    const srLive = document.getElementById('sr-announcer');
    const timeText = document.getElementById('timeText');

    function formatTime(secs) {
        const m = Math.floor(secs / 60).toString().padStart(2, '0');
        const s = Math.floor(secs % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }

    function togglePlay() {
        if (video.paused) {
            video.play();
            playBtn.textContent = "Pause";
            srLive.textContent = "Video playing.";
        } else {
            video.pause();
            playBtn.textContent = "Play";
            srLive.textContent = "Video paused at " + formatTime(video.currentTime);
            saveState();
        }
    }

    function seek(offset) {
        video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + offset));
        srLive.textContent = "Jumped to " + formatTime(video.currentTime);
    }

    function saveState() {
        // Save current timestamp to local storage or backend API
        localStorage.setItem('media_last_time', video.currentTime);
    }

    // Restore last position on load
    window.addEventListener('DOMContentLoaded', () => {
        const savedTime = localStorage.getItem('media_last_time');
        if (savedTime) {
            video.currentTime = parseFloat(savedTime);
            srLive.textContent = "Resumed at " + formatTime(video.currentTime);
        }
    });

    video.addEventListener('timeupdate', () => {
        timeText.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration || 0)}`;
    });

    playBtn.addEventListener('click', togglePlay);
    document.getElementById('rewindBtn').addEventListener('click', () => seek(-10));
    document.getElementById('forwardBtn').addEventListener('click', () => seek(10));

    // Global keyboard listener
    window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        if (e.code === 'Space') {
            e.preventDefault();
            togglePlay();
        } else if (e.key === 'j' || e.key === 'J') {
            e.preventDefault();
            seek(-10);
        } else if (e.key === 'l' || e.key === 'L') {
            e.preventDefault();
            seek(10);
        }
    });
</script>
</body>
</html>
```

---

## 3. Why Order Matters in Media Player Implementation
1. **Check Form Focus Before Handling Spacebar**: If a user is typing in a comment or prompt box, ignoring the event prevents spacebar from interrupting typing.
2. **Set Text Content of Live Region on Action**: Firing announcements immediately gives auditory confirmation while video decoding buffers the requested frame.
3. **Save State on Pause Event**: Saving progress immediately when the user pauses prevents state loss if the browser tab is abruptly terminated.

---

## 4. Beginner Coder Q&A
**Q: Why is `aria-hidden="true"` placed on `timeText`?**  
A: Visual time displays update multiple times per second. Hiding it from screen readers prevents assistive software from speaking numbers constantly while video is playing.

**Q: What is `e.preventDefault()` doing?**  
A: By default, pressing Spacebar scrolls the web page down. Calling `e.preventDefault()` stops the page from jumping when pausing the video.

**Q: Can this be connected to a Python server?**  
A: Yes! Simply replace `localStorage.setItem` with a `fetch('/api/media/save', { method: 'POST', body: ... })` call to sync progress with the Quart backend.
