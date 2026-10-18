[//]: # (DOC_ID: SIRA-DEV-01_01 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 01.1: Problems Encountered: Terminal Tearing & Headless Traps

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Primer**: [`../00_PRIMERS/00B_BEGINNER_GUIDE_TO_ACCESSIBLE_WEBSOCKET_STREAMING.md`](/docs/devlog/00B_BEGINNER_GUIDE_TO_ACCESSIBLE_WEBSOCKET_STREAMING)
- **Next Problem Chapter**: [`01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES.md`](/docs/devlog/01_02_WEBSOCKET_DROPOUTS_AND_REFRESH_CRASHES)

---

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-1)

In the earliest iterations of the Siraugga project, development was attempted directly inside the Linux terminal. As documented in the developmental chatlogs (Chapters 3 and 5), this resulted in two severe technical roadblocks: **Console Tearing** and **Interactive Security Prompts**.

This chapter details what happened, why it happened, and how the architectural pivot to an accessible headless web portal permanently solved these traps.

---

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-2)
## Issue 1: Console Tearing & Input Corruption
[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-3)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-3)
When testing interactive agent loops in the Linux console, the terminal screen became completely unreadable. While the developer was typing a prompt, background threads began printing incoming AI tokens directly across the typing cursor.

Screen reader speech synthesizers read both typing echoes and AI responses simultaneously, producing unintelligible audio gibberish.

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-4)
### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-4)
Standard Linux terminal emulators share a single standard output (`stdout`) and standard input (`stdin`) stream per terminal session. 

When a multi-threaded application prints to `stdout` from a worker thread without an event-driven terminal buffer (like curses), the stream directly overwrites the active terminal cursor position, corrupting the prompt buffer.

```text
[User Typing]: Add an NPC que---
[AI Thread Output]: Analyzing file src/game.py...
[Scrambled Result]: Add an NPC queAnalyzing st/game.py...
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-5)
## Issue 2: The Interactive Security Prompt Freeze
[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-6)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-6)
After replacing early mock scripts with the genuine AI agent CLI binary, the backend suddenly locked up. Terminal execution froze indefinitely with 0% CPU activity, and the web portal became unresponsive.

Upon inspecting background logs, the CLI was stuck waiting on an interactive question:
```text
? Do you trust the authors of this workspace? [Y/n]
```

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-7)
### Why It Happened
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-7)
Because the developer relies entirely on a screen reader, navigation through terminal interfaces depends on virtual cursor review keys. 

1. **Key Interception**: When a CLI renders a custom cursor menu (requiring arrow keys to highlight "Yes"), the screen reader intercepts those arrow keys to read adjacent text on the screen. The keystrokes never reach the underlying terminal process.
2. **Subprocess Deadlock**: When launched via Python `subprocess.Popen(..., stdin=subprocess.PIPE)`, the CLI expected an interactive TTY (teletypewriter) session. Because no human could press Enter, the process hung in an uninterruptible sleep state waiting for `stdin`.

---

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-8)
## The Architectural Solution
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-8)

To eliminate terminal tearing and interactive deadlocks forever, the team implemented two foundational changes:

1. **Decoupled Web Architecture**: Dropped the terminal interface completely. All inputs are submitted via HTML form controls; all agent responses are streamed over WebSockets.
2. **Automated Headless Flags**: Configured `agent_manager.py` to always invoke the agent binary with explicit automation flags:
   ```bash
   agy --trust --headless --stream-json
   ```
   - `--trust`: Pre-authorizes the workspace, bypassing the interactive security prompt.
   - `--headless`: Tells the CLI to run without an interactive pseudo-terminal.
   - `--stream-json`: Formats every event as machine-readable JSON rather than terminal ANSI escape codes.

---

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-9)
## Why Order Matters in Headless Execution
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-9)

1. **Flag Ordering in CLI Invocation**:
   - The `--trust` and `--headless` flags must be passed as CLI arguments *at the moment of process instantiation*. If you launch the process first and attempt to answer prompts over `stdin`, timing mismatches can deadlock the process before the answer is received.
2. **JSON Stream Parsers Before UI Dispatch**:
   - The server must read and validate the JSON event structure *before* forwarding chunks to the web client. If raw, unparsed stderr logs reach the browser, HTML rendering breaks.

---

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-10)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-11)

### Q: Why didn't a simple `echo "Y" | agy` command work?
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-11)
**A:** Modern CLI applications inspect their input source using Linux system calls like `isatty()`. If they detect that input is coming from a pipe instead of a real keyboard, many CLIs immediately reject the input or prompt again for security reasons.

[//]: # (SECTION_ID: SIRA-DEV-01_01-SEC-12)
### Q: What is an ANSI escape code?
[//]: # (SECTION_ID: SIRA-DOC-01_01-SEC-12)
**A:** These are invisible character codes (like `\033[31m`) that tell the terminal to change colors or move the cursor. Screen readers often read these codes literally ("backslash zero three three bracket three one"), creating immense audio clutter.
