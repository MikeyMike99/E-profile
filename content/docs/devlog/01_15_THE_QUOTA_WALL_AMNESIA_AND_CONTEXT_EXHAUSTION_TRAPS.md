# Chapter 01_15: The Quota Wall, Amnesia & Context Exhaustion Traps

As development sessions grow in complexity, autonomous coding agents accumulate vast histories of tool calls, terminal traces, and subagent transcripts. This chapter examines the twin crises of the **Quota Wall** and **Agent Amnesia**, and how semantic compaction prevents context exhaustion without sacrificing system recall.

---

## What Happened

During prolonged multi-step refactoring sessions spanning hours of continuous work, the orchestrator experienced severe cognitive and operational failures:
- **The Amnesia Crisis**: Around turn 25–30, the agent began "forgetting" fundamental rules established in turn 1. It attempted to recreate already existing files, reverted established architectural decisions, and asked questions that had been answered an hour earlier.
- **The Hard Quota Wall**: Autonomous loops suddenly crashed with upstream API errors: `HTTP 429: Resource Quota Exceeded` or `ContextWindowExceededError: Maximum token limit reached`.
- **The Artificial Panic**: As the agent sensed token exhaustion approaching, its reasoning degraded. It began skipping unit tests, truncating explanations, and making hasty code edits in an attempt to terminate before running out of memory.

---

## Why It Happened

The root causes stem from the linear, append-only nature of conversational context windows:
- **Unbounded Context Inflation**: Reading a 500-line file into memory consumes ~4,000 tokens. Doing this ten times across multiple subagents rapidly exhausts a 128K or 200K token budget.
- **Stateless Re-Evaluation**: Every turn of an LLM agent resends the entire preceding conversation history. Without active pruning, redundant terminal outputs and intermediate lint errors are repeatedly processed at immense financial and compute cost.
- **Naive History Truncation**: Simply slicing off the top of the history (`messages = messages[-10:]`) cures token exhaustion but introduces immediate amnesia, discarding the user's initial requirements and architectural constraints.

```
Linear History (Unbounded):
[User Prompt] + [Turn 1 (5K)] + [Turn 2 (20K)] + ... + [Turn 30 (180K)] ===> QUOTA WALL COLLAPSE!

Semantic Compaction:
[System Prompt] + [Session State JSON] + [Recent 5 Turns] + [Compacted Milestones] ===> STABLE 25K TOKENS
```

---

## The "Why Order Matters" Principle

Preserving intelligence across long horizons requires a strict order of memory hierarchy:
1. **Preserve System Rules & Tiers First**: Security rules, RBAC tiers, and active workspace paths must reside at the very top of the prompt buffer and must *never* be evicted or truncated.
2. **Compact Middle Turns Before Deletion**: Intermediate tool outputs (such as directory listings or build outputs) must be summarized into compact key-value milestones before older messages are pruned.
3. **Keep Most Recent Turns Raw**: The last 3 to 5 conversational turns must be preserved verbatim so the agent maintains immediate conversational continuity and short-term working memory.

---

## Beginner Coder Q&A

### What is "Semantic Compaction"?
Instead of keeping 50 pages of raw terminal outputs, a background routine extracts only the essential conclusions (e.g., "Step 4: Hot-patch compiler verified clean syntax; backup saved to core/backups/server.py") and discards the raw bytes.

### Why not just use a larger context model (e.g., 1M tokens)?
Larger context windows increase latency significantly (longer time to first token) and introduce the "Needle In A Haystack" problem, where the model misses crucial instructions buried in hundreds of thousands of words.

### Where does Siraugga store persistent memory?
Long-term context is stored outside the LLM in structured JSON files (`session_ownership.json`, `project_manager` metadata, and Raugus VFS AST maps). The agent queries these on demand rather than keeping everything in active memory.

---

## Next Steps & Related Chapters
- To see how the server buffers and manages event streams without overflowing memory, read [`04_SOLUTIONS_AND_ARCHITECTURE/04_08_IN_MEMORY_EXECUTION_AND_CLEAN_WORKSPACE_PROTOCOL.md`](/docs/devlog/04_08_IN_MEMORY_EXECUTION_AND_CLEAN_WORKSPACE_PROTOCOL).
- To examine diagnostic logs showing token usage before and after semantic compaction, visit [`03_DIAGNOSTIC_TESTS/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS.md`](/docs/devlog/03_01_STREAMING_RESILIENCE_AND_RECONNECT_LOGS).
- To build an asynchronous deque buffer from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH.md`](/docs/devlog/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH).
