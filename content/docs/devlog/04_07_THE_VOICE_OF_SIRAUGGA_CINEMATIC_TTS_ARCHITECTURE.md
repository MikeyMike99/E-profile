[//]: # (DOC_ID: SIRA-DEV-04_07 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 04.7: Architecture Solutions: The Voice of Siraugga Cinematic TTS

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_06_PRE_FLIGHT_SELF_HEALING_SUPERVISOR_ARCHITECTURE.md`](/docs/devlog/04_06_PRE_FLIGHT_SELF_HEALING_SUPERVISOR_ARCHITECTURE)
- **Next Architecture Chapter**: [`04_08_IN_MEMORY_EXECUTION_AND_CLEAN_WORKSPACE_PROTOCOL.md`](/docs/devlog/04_08_IN_MEMORY_EXECUTION_AND_CLEAN_WORKSPACE_PROTOCOL)

---

[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-04_07-SEC-1)

Screen readers provide functional text-to-speech for static documents, but fall short during rapid, multi-file agentic coding sprints.

This chapter details the architecture of **The Voice of Siraugga**—an intent-driven, cinematic neural audio pipeline engineered to provide real-time, low-latency auditory telemetry for blind developers.

---

[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-2)
## Architectural Data Flow
[//]: # (SECTION_ID: SIRA-DOC-04_07-SEC-2)

```text
+-------------------------------------------------------------------------------+
|                       Agent Orchestrator (agent_manager.py)                   |
|  - Parses stream-json from AI CLI                                             |
|  - Detects tool call: tool_name="replace_file_content", params={...}          |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                        Phonetic Sanitizer & Extractor                         |
|  1. Discards internal thought blocks ("thinking")                             |
|  2. Combines toolAction + toolSummary ("Updating Route: WebSocket handler")   |
|  3. Strips speech-breaking quotes, backticks, and first-person pronouns       |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                           Cinematic TTS Proxy Service                         |
|  - Encodes sanitized text to ElevenLabs Neural WebSocket stream               |
|  - Generates low-latency Opus/MP3 audio chunks                                |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                       Accessible Browser Client (Web Audio)                   |
|  - Decodes audio buffer via HTML5 Web Audio API                               |
|  - Plays concise narration smoothly alongside visual chat stream              |
+-------------------------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-3)
## Key Design Principles
[//]: # (SECTION_ID: SIRA-DOC-04_07-SEC-3)

1. **Sub-2-Second Total Latency**: By synthesizing speech concurrently as tool calls are dispatched, audio feedback arrives before file I/O operations finish.
2. **Deterministic Intent Generation**: Never prompts an LLM to generate speech phrases. Speech strings are built deterministically from structured metadata, eliminating conversational fluff.
3. **Phonetic Hygiene**: Neural speech models stutter when reading syntax code. Stripping quotation marks and special punctuation ensures fluid, natural human pronunciation.

---

[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-4)
## Why Order Matters in Neural Audio Pipelines
[//]: # (SECTION_ID: SIRA-DOC-04_07-SEC-4)

1. **Phonetic Sanitization Before Audio Synthesis**:
   - The text must be stripped of backticks and quotes *before* being submitted to the TTS engine. Once audio waveforms are generated, pronunciation errors cannot be corrected without resynthesizing.
2. **Buffer Pruning Before Re-Queueing**:
   - If an agent generates three tool calls in under 500ms, the audio player must prune stale queued sentences to stay synchronized with live code execution.

---

[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-6)

### Q: Why use the Web Audio API instead of standard `<audio>` tags?
[//]: # (SECTION_ID: SIRA-DOC-04_07-SEC-6)
**A:** Standard HTML `<audio>` elements suffer from 500ms startup latency and buffering delays. The Web Audio API provides hardware-accelerated, instantaneous buffer playback ideal for rapid developer updates.

[//]: # (SECTION_ID: SIRA-DEV-04_07-SEC-7)
### Q: What voice model is used for Siraugga?
[//]: # (SECTION_ID: SIRA-DOC-04_07-SEC-7)
**A:** The engine integrates with ElevenLabs using deep, authoritative, neural narrator voices designed to sound calm, clear, and distinct from the user's personal screen reader voice.
