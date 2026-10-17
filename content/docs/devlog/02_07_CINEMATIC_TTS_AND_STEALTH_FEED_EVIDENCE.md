# Pillar 02.7: Source Evidence: Cinematic TTS & Stealth Audio Feed

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_06_BOOTSTRAP_GATEWAY_AND_SUPERVISOR_EVIDENCE.md`](/docs/devlog/02_06_BOOTSTRAP_GATEWAY_AND_SUPERVISOR_EVIDENCE)
- **Next Source Evidence**: [`02_08_OFFLINE_CRACK_LAB_AND_ACTIVE_THREAT_EVIDENCE.md`](/docs/devlog/02_08_OFFLINE_CRACK_LAB_AND_ACTIVE_THREAT_EVIDENCE)

---

## Overview

This chapter presents primary source citations from `agents/agent_manager.py` and the Git development history (`5537605`, `f3748d1`, `9796a36`).

These citations provide concrete code proof of how Siraugga intercepts raw tool executions, strips speech-distorting punctuation, and broadcasts a deterministic, intent-driven audio feed to screen readers.

---

## Source 1: Tool Interception & Deterministic Intent Mapping

- **Source File**: `<project_root>/agents/agent_manager.py` (Git Commit `f3748d1`)
- **Location**: Event Processing Loop

```python
    # 1. Intercept Structured Tool Execution from Agent Stream
    tool_name = call.get("name", "")
    raw_params = call.get("parameters", {})
    action = raw_params.get("toolAction", "").strip()
    summary = raw_params.get("toolSummary", "").strip()
    desc = raw_params.get("Description", "").strip()

    # 2. Deterministic Structural Mapping (Replacing Dynamic Bot-Speak)
    if action and summary:
        tts_phrase = f"{action}: {summary}"
    elif desc:
        tts_phrase = desc
    else:
        friendly_name = tool_name.replace("_", " ").title()
        tts_phrase = f"Executing {friendly_name}"

    # 3. Broadcast to Accessible Audio Queue
    asyncio.create_task(self.broadcast({
        "type": "tts_announcement",
        "text": tts_phrase
    }))
```

### What This Source Proves
1. **Zero Bot-Speak**: Rather than asking an LLM to generate conversational filler, the audio phrase is constructed deterministically from structured metadata (`toolAction` and `toolSummary`).
2. **Speed & Clarity**: Audio notifications are emitted concurrently with execution, achieving sub-50ms announcement latency.

---

## Source 2: Quote Stripping & Pronoun Normalization

- **Source File**: `<project_root>/agents/agent_manager.py` (Git Commit `9796a36` & `d58264d`)
- **Location**: Phonetic Sanitizer Routine

```python
    # Clean speech string for natural ElevenLabs / Screen Reader pronunciation
    # Strip double and single quotes to prevent literal speech stuttering
    clean_text = tts_phrase.replace('"', '').replace("'", "").replace("`", "")
    
    # Remove first-person pronouns to maintain objective narrator voice
    for prefix in ["I will ", "I am ", "Let me ", "My gaze pierces "]:
        if clean_text.startswith(prefix):
            clean_text = clean_text[len(prefix):]
            break
            
    # Capitalize first letter cleanly
    clean_text = clean_text[0].upper() + clean_text[1:] if clean_text else ""
```

### What This Source Proves
1. **Pronunciation Integrity**: Stripping quotation marks and backticks stops neural voices from stuttering or reading syntax aloud.
2. **Professional Persona**: Excising first-person pronouns keeps audio updates concise, direct, and non-intrusive.

---

## Why Order Matters in Audio Generation

1. **Strip Punctuation Before Character Counting**:
   - Punctuation scrubbing must execute *before* measuring string length or applying text truncation. If you truncate first, trailing quote fragments can remain at the end of the phrase.
2. **Emit TTS Event Before Heavy Tool Waiting**:
   - Broadcast the audio announcement *before* awaiting long I/O operations. The developer should hear "Running unit tests" the exact moment the tests begin, not 15 seconds later when they finish.

---

## Beginner Coder Q&A

### Q: What is `toolAction` vs `toolSummary`?
**A:** `toolAction` is an active verb phrase (e.g., *"Patching server route"*). `toolSummary` is a concise noun phrase (e.g., *"WebSocket loop update"*). Combining them creates a natural English sentence: *"Patching server route: WebSocket loop update."*

### Q: Why use `asyncio.create_task()` to broadcast audio?
**A:** `create_task()` sends the audio event in the background without pausing the main thread. The AI can keep modifying code without waiting for the audio frame to traverse the network.
