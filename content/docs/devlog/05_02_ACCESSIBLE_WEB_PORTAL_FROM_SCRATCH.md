# Pillar 05.2: From-Scratch Creation Guide: Accessible Web Portal & Flip Card

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_01_QUART_STREAMING_SERVER_FROM_SCRATCH.md`](/docs/devlog/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH)
- **Next From-Scratch Guide**: [`05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH)

---

## Overview

This guide walks you through building an accessible, screen-reader-optimized web frontend (`index.html`) from a blank file.

You will implement three core features:
1. **Semantic Chat Interface**: An ARIA-friendly chat area with minimal heading clutter.
2. **The Accessible Flip Card**: Direct raw markdown editing using native `<textarea>` elements.
3. **Resilient WebSocket Client**: Automatic 4-second keep-alive pings and sequence acknowledgments.

---

## Step-by-Step Implementation

### Step 1: Open a Blank HTML File
```bash
nano templates/index.html
```

### Step 2: HTML Skeleton & ARIA Live Regions (Lines 1–25)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Siraugga Command Center</title>
    <link rel="stylesheet" href="/static/css/tailwind.css">
</head>
<body class="bg-gray-950 text-gray-100 flex flex-col h-screen">
    <!-- Main Accessible Live Stream Region -->
    <main id="chatLog" class="flex-1 overflow-y-auto p-4 space-y-4" aria-live="polite" aria-atomic="false">
        <div class="p-3 bg-gray-900 rounded">Siraugga Command Center Online.</div>
    </main>

    <!-- Interactive Artifact Flip Card Container -->
    <div id="artifactModal" class="hidden fixed inset-0 bg-black/80 flex items-center justify-center p-4">
        <div class="bg-gray-900 border border-gray-700 rounded-lg max-w-2xl w-full p-4">
            <h2 class="text-lg font-bold mb-2">Artifact Plan Editor</h2>
            <textarea id="rawEditor" class="w-full h-64 bg-black text-green-400 font-mono p-3 rounded" aria-label="Markdown Editor"></textarea>
            <button onclick="saveArtifact()" class="mt-3 px-4 py-2 bg-blue-600 rounded font-semibold">Save Artifact</button>
        </div>
    </div>
```

### Step 3: Resilient WebSocket Client & Keep-Alive Loop (Lines 26–65)
```html
    <script>
        let ws;
        let lastSeq = 0;

        function connect() {
            ws = new WebSocket('ws://' + window.location.host + '/ws');

            ws.onopen = () => {
                console.log("[WS] Connected to Siraugga Engine.");
                // 1. Resynchronize if reconnecting
                if (lastSeq > 0) {
                    ws.send(JSON.stringify({ type: 'sync', last_seq: lastSeq }));
                }
                // 2. Start 4-Second Keep-Alive Heartbeat
                setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({ type: 'ping' }));
                    }
                }, 4000);
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'pong') return;

                if (msg.seq) {
                    lastSeq = msg.seq;
                    // Acknowledge chunk delivery immediately
                    ws.send(JSON.stringify({ type: 'ack', seq: msg.seq }));
                }

                if (msg.type === 'chunk') {
                    const el = document.createElement('div');
                    el.className = "p-2 bg-gray-800 rounded font-mono text-sm";
                    el.innerText = msg.text;
                    document.getElementById('chatLog').appendChild(el);
                }
            };

            ws.onclose = () => setTimeout(connect, 2000);
        }

        function openArtifactEditor(content) {
            const modal = document.getElementById('artifactModal');
            const editor = document.getElementById('rawEditor');
            editor.value = content;
            modal.classList.remove('hidden');
            // Auto-focus immediately so screen readers announce the input
            editor.focus();
        }

        connect();
    </script>
</body>
</html>
```

---

## Why Order Matters in Client-Side Architecture

1. **Auto-Focus Immediately Upon Modal Reveal**:
   - Calling `editor.focus()` must occur *immediately after* removing the `hidden` class. If focus is set before unhiding, browsers ignore the focus call, leaving screen reader users lost in the background document.
2. **Send ACK After Rendering Update**:
   - Acknowledge the sequence number *only after* storing or rendering the message. If the browser sends an `ack` before the DOM renders and an error occurs during parsing, the missed chunk cannot be re-requested.

---

## Verification & Testing

1. Open `http://127.0.0.1:5000` in Google Chrome or Mozilla Firefox.
2. Press `F12` and inspect the **Console** tab:
   - Confirm `[WS] Connected to Siraugga Engine.` appears.
   - Confirm ping/pong frames transmit every 4 seconds in the **Network -> WS** tab.
3. Test screen reader navigation (NVDA: `Insert + Down Arrow`):
   - Speech synthesizer reads chat output smoothly without getting trapped in unlabelled frames.

---

## Beginner Coder Q&A

### Q: What does `aria-live="polite"` do?
**A:** It tells screen readers to announce new messages as soon as the user finishes speaking or navigating, rather than rudely interrupting them mid-sentence (`aria-live="assertive"`).

### Q: Why not use a rich visual editor like TinyMCE?
**A:** Visual editors generate deeply nested, irregular HTML that breaks screen reader navigation shortcuts. A plain `<textarea>` guarantees standard arrow navigation and full compatibility.
