[//]: # (DOC_ID: SIRA-DEV-01_43 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 01.43: Problems Encountered: Token Burst, Premature Rollover & Mid-Task Reset Traps

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-1)
## Overview & Context
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-1)
Long-running agentic conversations naturally accumulate dozens or hundreds of conversational turns. In large enterprise workflows, sessions reaching 200+ turns can consume hundreds of thousands of input tokens per turn, degrading responsiveness and driving up API costs. To address this, developers often attempt to automate session resets. However, naive rollover implementations introduce severe architectural pitfalls: premature resets triggered by beneficial prompt caching, mid-conversation context wipes during steering, and indiscriminate process kills that terminate active background tasks.

```
Naive Session Reset Pipeline (Vulnerable):
[Active Multi-Step Task] ──► [Turn reaches cache threshold (75k)] ──► [Hard Reset to New Conv ID]
                                                                                │
                                                            Task Aborted & Memory Wiped Mid-Turn!

Protected Invariant Pipeline (Resilient):
[Active Multi-Step Task] ──► [Is Task Ongoing / Steered / Queued?] ──(YES)──► [Suppress Rollover & Log SIEM]
                                         │ (NO - Idle & >= 80 turns)
                                         ▼
                            [Distill Briefing & Seamless Rollover]
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-1)
## 1. The Token Burst & Session Rollover Traps
[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-2)

### The 200-Turn Token Inflation Spike
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-2)
- **What Happened**: Analysis of previous sessions revealed sessions accumulating over 209 turns (`8a26ea19...`). Each subsequent turn retransmitted the entire accumulated chat history, tool outputs, and code diffs, consuming over 80,000 to 120,000 tokens on every single prompt.
- **Root Cause**: Without an automated distillation and rollover mechanism, the transcript grew monotonically. Users were forced to manually remember to start a new session, or suffer latency and token exhaustion.

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-3)
### The Cached Token Trap (`last_cache >= 75000`)
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-3)
- **What Happened**: A naive rollover rule was introduced to automatically archive sessions when `last_cache >= 75000` tokens. Instead of solving the issue, the agent repeatedly reset every 2–3 turns in an endless loop.
- **Root Cause**: In modern LLMs (such as Gemini with context caching), `last_cache` represents prompt cache hits. Cache hits are beneficial—they reduce latency and cost 75% less. Treating 75k cached prompt tokens as "token bloat" triggered resets on standard system prompt and tool definitions.

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-4)
### The Mid-Task Steering Collision
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-4)
- **What Happened**: When a user interrupted an active turn to provide a course-correction (e.g. typing a steering update or queuing a prompt), the engine restarted the execution loop and immediately evaluated the rollover check. The session was archived mid-flight, cutting off the agent from the files it had just inspected and abandoning subagents.
- **Root Cause**: The rollover check failed to inspect execution origin (`_from_steer_or_queue`) or pipeline queues (`queued_prompts`), treating an in-flight course-correction as a fresh idle turn.

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-5)
### The Blanket Subprocess Reaping Trap (`pkill -9 -f agy`)
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-5)
- **What Happened**: Upon exiting every turn, background tasks and subagents were terminated unexpectedly with notice: `[Notice] All your subagents and background tasks have been stopped due to server restart`.
- **Root Cause**: A cleanup routine in the `finally` block of `execution_mixin.py` executed an unconditional system-wide `pkill -9 -f agy`, killing active processes across the operating system instead of targeting only cancelled child tasks.

---

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-2)
## 2. Invariant Rules for Session Lifecycle Management
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-2)
1. **Never Rollover Mid-Conversation**: If a turn originates from steering (`_from_steer_or_queue=True`) or follow-up prompts are queued, session rollover must be strictly prohibited.
2. **Never Treat Prompt Cache Hits as Bloat**: Cached tokens accelerate inference and do not represent memory leaks. Gating rollovers on `last_cache` is anti-pattern.
3. **Rollover Must Be In-Memory & Silent**: When rollover triggers between tasks, working directory, active project, and recent goals must transfer silently via `<SESSION_CONTINUATION_CONTEXT>`.
4. **Subprocess Cleanup Must Be Targeted**: Never run system-wide `pkill` in normal turn cleanup routines. Only terminate specific child PIDs during explicit user task cancellations.

---

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-3)
## 3. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-6)

### Why did the session keep resetting every couple of turns?
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-6)
Because the engine was configured to reset whenever `last_cache >= 75000`. Once your tools and files were loaded into memory, the prompt cache was already near 75k tokens, causing every new message to trigger an automatic reset.

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-7)
### How does the system now know not to reset while I'm actively steering?
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-7)
The execution engine now tracks `_from_steer_or_queue` and inspects `queued_prompts`. If you type a message while a task is running, the engine marks the turn as `is_ongoing_midconversation=True`, which completely disables the rollover check.

---

[//]: # (SECTION_ID: SIRA-DEV-01_43-SEC-4)
## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-01_43-SEC-4)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_39_SESSION_ROLLOVER_DISTILLATION_AND_GUARD_EVIDENCE.md`](/docs/devlog/02_39_SESSION_ROLLOVER_DISTILLATION_AND_GUARD_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_36_SESSION_ROLLOVER_GUARD_AND_AUDIT_LOGS.md`](/docs/devlog/03_36_SESSION_ROLLOVER_GUARD_AND_AUDIT_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_39_AUTOMATED_SILENT_SESSION_ROLLOVER_AND_GUARD_ARCHITECTURE.md`](/docs/devlog/04_39_AUTOMATED_SILENT_SESSION_ROLLOVER_AND_GUARD_ARCHITECTURE)
- **From-Scratch Creation Guide**: [`05_FROM_SCRATCH_CREATION_GUIDES/05_42_SESSION_ROLLOVER_AND_GUARD_FROM_SCRATCH.md`](/docs/devlog/05_42_SESSION_ROLLOVER_AND_GUARD_FROM_SCRATCH)
