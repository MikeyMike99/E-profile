# Model Quota Breach Detection & Graceful Fallback Architecture

## 1. Architectural Concept & Core Objective
Modern agentic workflows consume significant LLM context and rate limits. When developers selected heavy reasoning models (such as `pro` or high-effort reasoning aliases), sudden API rate limits (HTTP 429) or token exhaustion would cause catastrophic silent failures or sudden subagent crashes.

The Quota Breach Detection & Fallback Architecture introduces an end-to-end protective feedback loop:
1. **Low-Effort Defaults**: Server and client default to fast, token-efficient Flash models (`flash_lite` / `flash`).
2. **Stream Interception**: The backend agent manager inspects CLI stream events for rate-limit warnings and fallback triggers.
3. **Transparent UI Synchronization**: When a breach occurs, the backend emits a `model_fallback` event over WebSocket, immediately alerting the user, updating the dropdown, and announcing via ARIA live regions.

```
+-------------------------------------------------------------+
|                     CLI Subprocess Stream                   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Agent Manager Event Stream Parser              |
|        Detects "429 RESOURCE_EXHAUSTED" / Model Shift       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|             WebSocket Monotonic Dispatch Engine             |
|       Emits: {"type": "model_fallback", "model": "flash"}   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Frontend Client                        |
| 1. Live Region Announcement: "Rate limit reached. Flash on" |
| 2. Visual Top Warning Banner Activated                      |
| 3. Select Dropdown Value Synced to "gemini-2.0-flash"       |
+-------------------------------------------------------------+
```

---

## 2. Low-Effort Flash Default Strategy
To prevent unexpected developer billing spikes and context starvation, all system layers enforce low-effort models by default:
- **`server.py` WebSocket Handler**: Defaults empty model requests to `flash`.
- **`agent_manager.py` Subprocess Launcher**: Defaults task configurations to `flash_lite` or `flash` unless explicitly overridden.
- **Frontend `index.html` Selector**: Populates default selection with token-friendly Flash models.

---

## 3. UI Notification & ARIA Live Region Announcement
When a fallback event arrives at the browser:
1. **Banner Injection**: A sticky top banner element (`#quota-warning-banner`) is toggled from `hidden` to visible with high-contrast warning colors.
2. **Selector Sync**: The `<select id="model-select">` value is programmatically updated to reflect the active fallback model.
3. **Screen Reader Alert**: The text is appended to `<div id="sr-announcements" aria-live="assertive">` ensuring immediate auditory notification without blocking keyboard input.

---

## 4. Why Order Matters in Quota Handling
1. **Emit Notification Before Downstream Calls**: Alerting the client immediately upon catching the 429 error ensures the developer understands why response speeds or reasoning depths have shifted.
2. **Update Dropdown Before Subsequent Prompts**: If the dropdown is not synchronized before the user sends their next message, the frontend will attempt to re-request the exhausted model, triggering an endless 429 loop.
3. **Graceful Degradation Over Process Termination**: Instead of aborting the entire developer session, downgrading to Flash maintains workflow continuity.

---

## 5. Beginner Coder Q&A
**Q: What HTTP status code signifies a quota breach?**  
A: HTTP 429 (`Too Many Requests` or `RESOURCE_EXHAUSTED`), returned by upstream LLM API gateways.

**Q: Can users switch back to the Pro model later?**  
A: Yes. Once the API provider's rate-limit window resets (typically 60 seconds), users can re-select the Pro model from the UI dropdown.

**Q: How does this protect local server memory?**  
A: By catching errors early and switching to smaller token payloads, the WebSocket message queues avoid processing bloated failure responses.
