# Pillar 01.5: Problems Encountered: Screen Reader Spam & Phantom Keystrokes

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_04_ZOMBIE_SUBAGENTS_AND_PROCESS_EXHAUSTION.md`](/docs/devlog/01_04_ZOMBIE_SUBAGENTS_AND_PROCESS_EXHAUSTION)
- **Next Problem Chapter**: [`01_06_THE_FRIENDLY_LEAK_AND_EGRESS_FIREWALL_TRAPS.md`](/docs/devlog/01_06_THE_FRIENDLY_LEAK_AND_EGRESS_FIREWALL_TRAPS)

---

## Overview

When developing software for blind and visually impaired engineers, user experience (UX) is mediated entirely through screen readers (NVDA, JAWS, VoiceOver). 

As documented in developmental chatlogs (Chapters 7 and 48), the early Siraugga interface suffered from two major accessibility blockers: **Screen Reader Speech Flooding** and **Heading Bloat**.

This chapter details why standard web designs fail screen readers and how Siraugga was re-engineered for auditory clarity.

---

## Issue 1: Speech Flooding & Raw Output Spam

### What Happened
In early web portal builds, when the AI agent executed a bash command (like `npm install` or `pip install`), the server streamed hundreds of lines of raw progress bars and compiler warnings directly into the chat container:

```text
[pip]: Downloading torch-2.1.0-cp310-cp310-manylinux1_x86_64.whl (775.5 MB)
[pip]: ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.2/775.5 MB 4.2 MB/s eta 0:03:04
```

Because the chat region was marked with `aria-live="polite"`, the screen reader attempted to speak every single percentage update and carriage return. The speech synthesizer talked non-stop for 10 minutes, freezing the user's ability to issue commands or hear system alerts.

### Why It Happened
Visual interfaces assume the human brain can visually ignore scrolling text in a log window. But screen readers convert text directly into sound sequentially. If a developer dumps raw terminal telemetry into an active speech buffer, it creates an auditory denial-of-service.

---

## Issue 2: Heading Bloat & Navigation Chaos

### What Happened
When the AI generated answers, it loved using deeply nested markdown headings:
```text
# Analysis (H1)
## Overview (H2)
### Frontend (H3)
  [Nested H4] Component
    [Nested H5] Button
      [Nested H6] State
```

When a screen reader user pressed `H` (the shortcut to jump to the next heading), they had to cycle through 20 meaningless subheadings just to find the start of the next conversational response. 

The administrator gave direct feedback:
> *"The responses in the UI is too much. It does not tell me what was completed... it should not expose logs and code directly in the UI. I am struggling to find where the message is actually starting because of all the headings."*

---

## The Architectural Solution

To restore auditory speed and navigation clarity, Siraugga instituted three strict UX rules:

### 1. The H2/H3 Heading Cap
All AI responses and system templates strictly cap headings at H2 (`##`) and H3 (`###`). Nesting H4–H6 is permanently banned across documentation and UI prompts.

### 2. Result-First Conciseness
Raw terminal output, JSON events, and compiler dumps are moved to background log files (`server_stdout.log`, `upgrade.log`). The web interface displays only concise, human-readable task summaries:
```text
[OK] Installed 14 dependencies successfully in 12s.
```

### 3. Native Form Controls (The Flip Card)
Instead of complex rich-text WYSIWYG editors (which trap screen reader cursors in nested `<div>` tags), interactive plan editing is performed using a native HTML `<textarea class="artifact-raw-editor">`. When flipped, the textarea is auto-focused immediately, allowing standard arrow key editing.

---

## Why Order Matters in Accessibility Rendering

1. **Auto-Focus Immediately on DOM Display**:
   - `rawEditor.focus()` must be called *after* removing `hidden` classes. Setting focus on an element with `display: none` fails silently, leaving the screen reader lost at the top of the webpage.
2. **Scrub Raw Terminal Escapes Before ARIA Dispatch**:
   - ANSI color codes (`\033[0m`) must be stripped by regular expressions *before* appending text to the `aria-live` region. Unstripped escape codes cause screen readers to read punctuation gibberish.

---

## Beginner Coder Q&A

### Q: Why do screen readers use heading shortcuts?
**A:** Sighted users scan a webpage by glancing at large text. Blind users scan a webpage by pressing `H` on their keyboard to quickly jump from section to section. If headings are bloated or missing, scanning is impossible.

### Q: What is an ARIA live region?
**A:** `aria-live` is an HTML attribute that tells the browser: "Whenever new text is inserted into this `<div>`, announce it through the user's speech synthesizer automatically without requiring them to move their cursor."
