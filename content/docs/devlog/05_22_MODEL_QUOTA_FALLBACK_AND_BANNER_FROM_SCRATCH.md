[//]: # (DOC_ID: SIRA-ARCH-05_22 | VERSION: v1.0 | SCOPE: ARCH)

# Model Quota Fallback & Accessible Banner from Scratch

[//]: # (SECTION_ID: SIRA-ARCH-05_22-SEC-1)
## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_22-SEC-1)
When developers run intensive coding tasks with heavy reasoning models (such as `pro` or high-effort reasoning configurations), API rate limits (HTTP 429) can exhaust quotas without warning. Without graceful handling, the application either crashes silently or strands the user in broken loops.

This guide details how to implement an end-to-end quota breach detection and fallback system. When a rate limit is detected in the backend CLI stream, the server downgrades execution to a fast Flash model, dispatches a `model_fallback` WebSocket event, and updates the frontend UI with an accessible warning banner and ARIA live region announcement.

```
+-------------------------------------------------------------+
|                Backend: Agent Manager Stream                |
|             Catches "RESOURCE_EXHAUSTED" / 429              |
+-------------------------------------------------------------+
                              |
                     WebSocket Broadcast
              {"type": "model_fallback", ...}
                              |
                              v
+-------------------------------------------------------------+
|                Frontend: WebSocket Event Handler            |
|       1. Displays accessible warning banner                 |
|       2. Synchronizes <select> value to "flash"             |
|       3. Injects alert into aria-live="assertive"           |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_22-SEC-2)
## 2. Complete Python Backend Handler
[//]: # (SECTION_ID: SIRA-DOC-05_22-SEC-2)
Save the following snippet in your backend stream parser (`agent_manager.py`):

```python
import json
import asyncio

FALLBACK_MODEL = "gemini-2.0-flash"

async def process_cli_stream(stream_generator, ws_send_func, current_model: str):
    """Parses raw CLI stdout and intercepts quota rate limits."""
    active_model = current_model
    
    async for raw_line in stream_generator:
        try:
            line_str = raw_line.decode("utf-8").strip() if isinstance(raw_line, bytes) else raw_line.strip()
            if not line_str:
                continue

            # Detect quota exhaustion signals
            if "RESOURCE_EXHAUSTED" in line_str or "429" in line_str or "Quota exceeded" in line_str:
                print(f"[QUOTA BREACH] Upstream limit reached for {active_model}. Falling back to {FALLBACK_MODEL}...")
                active_model = FALLBACK_MODEL
                
                fallback_packet = {
                    "type": "model_fallback",
                    "original_model": current_model,
                    "new_model": FALLBACK_MODEL,
                    "reason": "Upstream API rate limit reached. Switched to fast Flash model."
                }
                await ws_send_func(json.dumps(fallback_packet))
            
            # Normal event processing continues...
            await ws_send_func(json.dumps({"type": "chunk", "text": line_str}))

        except Exception as err:
            print(f"[STREAM PARSER ERROR] {err}")
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_22-SEC-3)
## 3. Complete Frontend HTML & JavaScript Handler
[//]: # (SECTION_ID: SIRA-DOC-05_22-SEC-3)
Add the banner and JavaScript listener to `index.html`:

```html
<!-- Top Accessible Warning Banner -->
<div id="quota-warning-banner" 
     role="alert" 
     class="hidden bg-amber-900 border-b border-amber-600 px-4 py-2 text-amber-100 flex items-center justify-between text-sm">
    <div class="flex items-center gap-2">
        <span class="font-bold">⚠️ Notice:</span>
        <span id="quota-banner-message">API Quota limit reached. Model downgraded to Flash.</span>
    </div>
    <button type="button" 
            onclick="document.getElementById('quota-warning-banner').classList.add('hidden')"
            class="text-amber-300 hover:text-white text-xs underline focus:outline-none">
        Dismiss
    </button>
</div>

<!-- Screen Reader Live Region -->
<div id="sr-announcements" aria-live="assertive" class="sr-only"></div>

<!-- Model Selector Dropdown -->
<select id="model-select" class="bg-slate-800 text-white border border-slate-600 rounded px-2 py-1">
    <option value="gemini-2.0-flash">Gemini 2.0 Flash (Default)</option>
    <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
</select>

<script>
    function handleServerEvent(eventData) {
        const data = JSON.parse(eventData);

        if (data.type === "model_fallback") {
            // 1. Show the warning banner
            const banner = document.getElementById('quota-warning-banner');
            const messageEl = document.getElementById('quota-banner-message');
            messageEl.textContent = data.reason;
            banner.classList.remove('hidden');

            // 2. Synchronize the select dropdown
            const selector = document.getElementById('model-select');
            selector.value = data.new_model;

            // 3. Announce to screen readers
            const srLive = document.getElementById('sr-announcements');
            srLive.textContent = "Alert: " + data.reason;
        }
    }
</script>
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_22-SEC-4)
## 4. Why Order Matters in Quota Handling
[//]: # (SECTION_ID: SIRA-DOC-05_22-SEC-4)
1. **Dispatch Fallback Before Dropping the Line**: Sending the `model_fallback` event immediately informs the user before subsequent token streams fail or stall.
2. **Update Dropdown Value Before User Retries**: Synchronizing the `<select>` element prevents the next user prompt from blindly re-triggering the same 429 rate limit.
3. **Use `role="alert"` and `aria-live="assertive"`**: Rate limit downgrades alter the intelligence and speed of the session; assertive priority ensures screen reader users hear the alert immediately.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_22-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_22-SEC-5)
**Q: Why fall back to Flash instead of stopping the task?**  
A: Workflows often involve simple tool commands or text summaries. Flash models have higher rate limits and lower token costs, allowing the developer to finish their session smoothly.

**Q: Does the banner block the user from working?**  
A: No. It sits non-intrusively at the top of the interface and includes a keyboard-accessible dismiss button.

**Q: What is the difference between `polite` and `assertive` live regions?**  
A: `polite` waits until the screen reader finishes speaking the current sentence. `assertive` interrupts immediately, which is appropriate for critical error and rate-limit alerts.
