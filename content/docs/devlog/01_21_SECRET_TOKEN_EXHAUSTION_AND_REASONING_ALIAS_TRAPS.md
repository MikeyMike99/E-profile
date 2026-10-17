[//]: # (DOC_ID: SIRA-DOC-01_21 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 01_21: Secret Token Exhaustion & Reasoning Alias Traps

Autonomous coding agents can rapidly consume developer billing quotas when underlying model aliases hide expensive reasoning loops. This chapter documents how selecting "Fast & Responsive" models secretly triggered high-effort planning models, and how **explicit alias mapping** and **transparent fallback UI reflection** solved the vulnerability.

---

## What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-1)

While testing the web portal's model selection menu, developers noticed that their daily API quota was disappearing in less than an hour despite explicitly selecting the lightweight "Flash" model tier:
- **Catastrophic Quota Drain**: A single conversational query consumed over 40,000 reasoning tokens even though the user only asked a basic syntax question.
- **The Silent Downgrade Trap**: When the API hit HTTP 429 quota exhaustion, the CLI automatically downgraded the session to an even lower tier, but the web UI dashboard remained completely unaware, displaying the wrong model badge.
- **Screen Reader Blindness**: Visually impaired developers had no indication that a model switch occurred, leaving them confused by sudden changes in response speed and verbosity.

---

## Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-2)

The issue originated from a disconnect between user intent and internal CLI model flags:
- **The High-Effort Reasoning Suffix**: In `ui_config.json`, the "Fast Flash" option was mapped to `gemini-3.8-flash-high`. In the `agy` CLI, the `-high` suffix commands the engine to provision deep chain-of-thought "Pro" reasoning loops for planning, completely defeating the purpose of choosing Flash.
- **UI State Desynchronization**: The frontend JavaScript assumed the backend was running whichever model was currently selected in the HTML `<select>` dropdown. It did not listen for backend `model_fallback` telemetry events.
- **Missing ARIA Announcements**: Without an accessible alert region, dynamic model changes remained invisible to assistive screen readers.

```
Anti-Pattern (Hidden Reasoning):
User clicks "Fast Flash" ---> Sends gemini-3.8-flash-high ---> Triggers Pro Reasoning Loop ---> 40K Tokens Wasted!

Hardened Architecture:
User clicks "Fast Flash" ---> Strictly maps to flash-low ---> Consumes 800 Tokens ---> Preserves Quotas!
```

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-3)

In token budgeting and model routing, sequence prevents financial exhaustion:
1. **Map Model Aliases Before Prompt Dispatch**: The orchestrator must sanitize model names to strict low-effort identifiers (`-low`) before sending the command line to the subprocess.
2. **Listen for System Downgrade Events Before Token Streaming**: The WebSocket parser must check for `step_type: "system"` and `"quota"` keywords before processing response tokens.
3. **Trigger Visual and Auditory Alerts Simultaneously**: When a fallback occurs, update the DOM dropdown, set the `(Forced)` badge, and dispatch an ARIA live announcement in the same event tick.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-4)

### What is the difference between `flash-low` and `flash-high`?
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-5)
`flash-low` uses the raw, ultra-fast model with minimal thinking overhead. `flash-high` forces the model to run internal multi-step reasoning steps before responding, which can multiply token usage by 20x to 50x!

### What does HTTP 429 mean?
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-6)
HTTP 429 is the standard web error code for `Too Many Requests`. It means you have exceeded the rate limit or quota allocated to your API key.

### How does Siraugga make model fallbacks transparent?
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-7)
The backend emits a `{"type": "model_fallback", "model": "flash-low"}` WebSocket message. The browser immediately colors the model tag yellow and announces: *"Warning: Model downgraded due to API quota."*

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-01_21-SEC-8)
- To see the primary source code of quota protection and fallback handling, read [`02_SOURCE_EVIDENCE/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE.md`](/docs/devlog/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE).
- To view architectural decision records on quota optimization, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY.md`](/docs/devlog/04_02_THE_5_TIER_ZERO_TRUST_HIERARCHY).
- To build an asynchronous streaming server with quota protection from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH.md`](/docs/devlog/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH).
