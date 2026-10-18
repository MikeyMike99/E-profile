[//]: # (DOC_ID: SIRA-ARCH-05_08 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.8: From-Scratch Creation Guide: Cinematic TTS Proxy & Sanitizer

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_07_BOOTSTRAP_SUPERVISOR_GATEWAY_FROM_SCRATCH.md`](/docs/devlog/05_07_BOOTSTRAP_SUPERVISOR_GATEWAY_FROM_SCRATCH)
- **Next From-Scratch Guide**: [`05_09_OFFLINE_PASSWORD_CRACK_LAB_FROM_SCRATCH.md`](/docs/devlog/05_09_OFFLINE_PASSWORD_CRACK_LAB_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-1)

This guide walks you through building an **Intent-Driven Text-to-Speech (TTS) Sanitizer & Proxy** (`cinematic_tts.py`) from a blank editor.

You will implement the phonetic sanitizer that strips speech-breaking punctuation, removes first-person bot-speak, and maps structured tool metadata into natural audio status announcements for blind developers.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-2)
## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-3)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-3)
```bash
nano cinematic_tts.py
```

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-4)
### Step 2: Implement the Phonetic Text Sanitizer (Lines 1–30)
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-4)
```python
import re

class PhoneticSanitizer:
    @staticmethod
    def clean_for_speech(raw_phrase: str) -> str:
        """Strips quotes, backticks, and conversational bot-speak for natural audio."""
        if not raw_phrase:
            return ""

        # 1. Strip punctuation marks that cause TTS stuttering
        cleaned = raw_phrase.replace('"', '').replace("'", "").replace("`", "")

        # 2. Remove first-person and fantasy roleplay prefixes
        prefixes_to_strip = [
            "I will ", "I am ", "Let me ", "My gaze pierces: ",
            "I weave the arcane threads: "
        ]
        for prefix in prefixes_to_strip:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):]
                break

        # 3. Capitalize first letter cleanly
        cleaned = cleaned.strip()
        return cleaned[0].upper() + cleaned[1:] if cleaned else ""
```

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-5)
### Step 3: Implement Tool Metadata Mapper (Lines 31–55)
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-5)
```python
    @classmethod
    def map_tool_call(cls, tool_name: str, parameters: dict) -> str:
        """Converts raw tool parameters into a concise spoken intent sentence."""
        action = parameters.get("toolAction", "").strip()
        summary = parameters.get("toolSummary", "").strip()
        desc = parameters.get("Description", "").strip()

        # Prefer structured action + summary pair
        if action and summary:
            phrase = f"{action}: {summary}"
        elif desc:
            phrase = desc
        else:
            friendly = tool_name.replace("_", " ").title()
            phrase = f"Executing {friendly}"

        return cls.clean_for_speech(phrase)
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-6)
## Why Order Matters in Speech Sanitization
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-6)

1. **Strip Quotes Before Trimming Whitespace**:
   - Punctuation removal must happen *before* calling `.strip()`. If you trim first and then remove a quote mark, leading and trailing spaces can be exposed, causing micro-delays in audio synthesis.
2. **Action Mapping Before Speech Synthesis**:
   - Map parameters into concise summaries *before* submitting text to the neural audio API. Submitting raw code chunks wastes speech quota and produces unlistenable audio.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-7)
## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-7)

Verify that your sanitizer cleans technical syntax and creates natural speech strings:

```bash
python3 -c "
from cinematic_tts import PhoneticSanitizer

# Test 1: Tool call with quotes and prefixes
params = {
    'toolAction': 'I will patch \"server.py\"',
    'toolSummary': '\`websocket\` keep-alive handler'
}
result = PhoneticSanitizer.map_tool_call('replace_file_content', params)
print('Synthesized Audio String:', result)
assert '\"' not in result and '\`' not in result
assert not result.startswith('I will')
print('[PASS] Speech string cleaned cleanly!')
"
```

**Expected Output**:
```text
Synthesized Audio String: Patch server.py: websocket keep-alive handler
[PASS] Speech string cleaned cleanly!
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-8)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-9)

### Q: Why do neural voices sound better when quotes are removed?
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-9)
**A:** When neural models see quotation marks, they try to modulate their pitch to imitate someone speaking dialogue. For technical software alerts, this sounds bizarre and unnatural. Stripping quotes produces an objective, narrator tone.

[//]: # (SECTION_ID: SIRA-ARCH-05_08-SEC-10)
### Q: What is the ideal word count for an audio developer alert?
[//]: # (SECTION_ID: SIRA-DOC-05_08-SEC-10)
**A:** Between 4 and 8 words. This allows the phrase to be spoken in under 1.5 seconds, ensuring the blind developer is informed without breaking their mental train of thought.
