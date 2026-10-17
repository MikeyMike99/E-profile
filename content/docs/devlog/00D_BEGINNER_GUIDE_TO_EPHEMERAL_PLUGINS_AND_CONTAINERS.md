# Pillar 00D: Beginner Guide to Ephemeral Plugins & Zero-Modification Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Primer**: [`00C_BEGINNER_GUIDE_TO_OPAQUE_VFS_AND_RAUGUS_MAP.md`](/docs/devlog/00C_BEGINNER_GUIDE_TO_OPAQUE_VFS_AND_RAUGUS_MAP)
- **Next: Problems Encountered**: [`../01_PROBLEMS_ENCOUNTERED/01_01_TERMINAL_TEARING_AND_HEADLESS_BYPASS_TRAPS.md`](/docs/devlog/01_01_TERMINAL_TEARING_AND_HEADLESS_BYPASS_TRAPS)

---

## What is an Ephemeral Plugin?

In traditional web applications, adding an interactive tool (like a quiz generator or video player) requires modifying frontend JavaScript, adding database tables, and hardcoding new UI layouts.

In the Siraugga platform, interactive tools are **Ephemeral Plugins**:
- They leave zero permanent footprint in the database.
- They execute inside isolated sandboxes.
- Their UI exists only for the duration of the developer's session.

---

## The Zero-Modification Blueprint Architecture

A common beginner trap when using AI agents is allowing the AI to directly edit frontend HTML, CSS, or JavaScript files to "add new features." This leads to:
1. **Broken Keyboard Shortcuts**: Hacking JavaScript often breaks screen reader accessibility keys.
2. **Upgrade Disasters**: When the core platform is upgraded, all customized HTML files are overwritten or fail to compile.
3. **Security Vulnerabilities**: Injected JavaScript can contain Cross-Site Scripting (XSS) bugs.

Siraugga mandates the **Zero-Modification Architecture**:
- The HTML template (`exam_application.html`, `media_player.html`) is a **permanent, immutable blueprint**.
- The AI is **strictly forbidden** from editing the HTML or JS files.
- The entire application's behavior, layout, questions, timers, and media tracks are controlled *indirectly* by injecting a temporary JSON payload schema (`exam_temp.json`).

```text
+-------------------------------------------------------------------------------+
|                       AI Agent / Backend Generation                           |
|      Agent generates structured payload: "exam_temp.json"                     |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                         Format Normalization Script                           |
|      format_exam.py validates schema compliance, timers, and scoring rules    |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                     Immutable Blueprint Template (UI Iframe)                  |
|  - exam_application.html fetches exam_temp.json dynamically                  |
|  - Zero modifications to core HTML, JavaScript, or CSS                        |
+-------------------------------------------------------------------------------+
```

---

## Plain-English Glossary

- **Ephemeral**: Short-lived, temporary, or existing only for the duration of a task.
- **Blueprint Pattern**: A fixed template that never changes its structure, but dynamically alters its display based on the data fed into it.
- **Payload Schema**: A strict JSON structure that defines required fields (e.g., question text, answer options, time limits).
- **Format Normalizer**: A validation script (`format_exam.py`) that checks incoming JSON data to guarantee it adheres to the schema before rendering.

---

## Why Order Matters in Ephemeral Plugins

1. **Schema Validation Before Iframe Mounting**:
   - The JSON data must be validated by `format_exam.py` *before* the web portal mounts the iframe. If an invalid JSON file is loaded, the client JavaScript crashes silently, leaving the user with an empty screen.
2. **Atomic JSON Write Before State Dispatch**:
   - The payload must finish writing to disk and close its file descriptor before sending the launch event over the WebSocket. If the client fetches the payload while the write is still buffered, it reads an incomplete file.

---

## Beginner Coder Q&A

### Q: If the HTML never changes, how do I change the quiz timer or add a question?
**A:** You simply include `"time_limit_minutes": 10` or add a new question dictionary in the JSON payload! The immutable JavaScript reads the JSON values and sets the countdown timer automatically.

### Q: Why is this approach safer for screen reader users?
**A:** The base blueprint has been rigorously tested and optimized for NVDA and JAWS screen readers (proper ARIA attributes, semantic headings, logical tab stops). If an AI modified the HTML dynamically, it would accidentally strip those accessibility tags.
