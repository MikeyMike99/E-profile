[//]: # (DOC_ID: SIRA-DOC-01_11 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 01.11: Problems Encountered: Internal Monologue & Robotic Bot-Speak

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_10_INGESTION_SWARM_PRIVILEGE_ESCALATION_TRAPS.md`](/docs/devlog/01_10_INGESTION_SWARM_PRIVILEGE_ESCALATION_TRAPS)
- **Next Problem Chapter**: [`01_12_PASSWORD_CRACKING_AND_ACTIVE_THREAT_SIMULATION_TRAPS.md`](/docs/devlog/01_12_PASSWORD_CRACKING_AND_ACTIVE_THREAT_SIMULATION_TRAPS)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-1)

When integrating speech synthesis (TTS) to provide an auditory coding feed for blind developers, early iterations attempted to read raw AI model outputs aloud.

As documented in DEVLOG Chapter 67 and Git history, this triggered severe auditory friction: **Internal Monologue Leakage**, **Punctuation Stuttering**, and **Robotic Narrative Bloat**.

This chapter breaks down the speech engineering hurdles and how deterministic intent mapping restored audio clarity.

---

## Issue 1: Streaming Raw Thinking Tokens to Speech
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-2)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-3)
Modern reasoning AI models generate extensive internal chains-of-thought (`thinking` blocks) before outputting code. In early streaming implementations, the WebSocket client piped these raw thought tokens directly to the audio synthesizer:

```text
[Audio Synthesizer]: "Thinking Process colon asterisks asterisks The user wants me 
to inspect the security manager dot py file open parenthesis line 45 close parenthesis..."
```

The blind developer was forced to listen to 45 seconds of rambling internal brainstorming just to find out that the AI had opened a file.

### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-4)
The streaming parser did not differentiate between user-facing conversational text, machine-readable tool parameters, and private model reasoning blocks. Everything received on the WebSocket was fed blindly into the speech queue.

---

## Issue 2: Punctuation Stuttering & Preamble Bloat
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-5)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-6)
Even when restricting audio to tool calls, speech synthesizers produced irritating audio artifacts:
1. **Pronunciation Stuttering**: When the AI output JSON or markdown containing single quotes, double quotes, or backticks, the TTS engine literally spoke the punctuation marks:
   > *"Opening quote server dot py end quote comma backtick view underscore file backtick."*
2. **The "Arcane Wizard" Trap**: An early experiment attempted to make the voice "cinematic" by generating fantasy roleplay prefixes:
   > *"I weave the arcane threads and peer into the matrix..."*
   During active server debugging, listening to a 10-second fantasy speech before learning whether a unit test passed was infuriating.

---

## The Architectural Solution: Intent-Driven Structural Mapping
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-7)

To achieve instantaneous, professional audio feedback, the team executed a series of targeted Git refactors (`f3748d1`, `5537605`, `9796a36`, `827c977`):

```text
+-------------------------------------------------------------------------------+
|                             Raw Tool Call Event                               |
|   tool_name: "replace_file_content"                                           |
|   raw_params: {"TargetFile": "server.py", "toolAction": "Updating WS loop"}   |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                      Deterministic Audio Sanitizer                            |
|  1. Strip all quotation marks, backticks, and markdown brackets               |
|  2. Remove first-person pronouns ("I will", "My gaze")                         |
|  3. Truncate deep insight explanations to the first concise sentence          |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                      Clean Voice of Siraugga Output                           |
|      "Updating WS loop in server.py" (Speech duration: 1.2 seconds)           |
+-------------------------------------------------------------------------------+
```

---

## Why Order Matters in Audio Pipeline Sanitization
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-8)

1. **Strip Internal Reasoning Before Speech Queueing**:
   - The JSON parser must discard `thinking` blocks *before* token chunks are placed into the audio synthesis queue. Queued speech frames cannot be cancelled without resetting the audio device.
2. **Normalize Punctuation Before Submitting to TTS API**:
   - Punctuation scrubbing must execute *before* generating phonetic audio waveforms. Once text is converted to MP3/WAV audio by ElevenLabs, speech artifacts cannot be removed.

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-9)

### Q: Why do speech synthesizers pronounce punctuation marks?
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-10)
**A:** Standard text-to-speech models are designed for audiobooks and human literature. When fed technical code containing brackets, underscores, and backticks, they attempt to pronounce every character literally so that nothing is missed.

### Q: Why not use a local TTS engine like eSpeak instead of cloud APIs?
[//]: # (SECTION_ID: SIRA-DOC-01_11-SEC-11)
**A:** eSpeak is extremely fast, but its mechanical robotic tone causes severe listening fatigue during 8-hour coding sessions. Modern neural voices (like ElevenLabs) sound natural and easy on the ears, provided the text input is sanitized properly.
