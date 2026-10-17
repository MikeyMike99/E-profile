# Pillar 02.1: Source Evidence: Server & Agent Streaming Architecture

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`../01_PROBLEMS_ENCOUNTERED/01_03_PATH_TRAVERSAL_AND_PRIVILEGE_ESCALATION.md`](/docs/devlog/01_03_PATH_TRAVERSAL_AND_PRIVILEGE_ESCALATION)
- **Next Source Evidence**: [`02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE.md`](/docs/devlog/02_02_SECURITY_RBAC_AND_RAUGUS_VFS_EVIDENCE)

---

## Overview

This chapter presents primary source citations and Git forensic evidence proving how Siraugga's asynchronous WebSocket architecture and detached subprocess orchestration are implemented in the production codebase.

---

## Source 1: The ACK Protocol & Keep-Alive Loop

- **Source File**: `<project_root>/core/server.py`
- **Location**: Lines 458–521

```python
        # 1. Heartbeat Keep-Alive to survive WSL 30s TCP timeouts
        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})
            continue

        # 2. Resynchronize Missed Events upon Client Reconnection
        elif msg_type == "sync":
            last_seq = data.get("last_seq", 0)
            await agent_mgr.sync_client(client_queue, last_seq)
            continue

        # 3. Client Acknowledgment to Prune Server Memory
        elif msg_type == "ack":
            seq = data.get("seq")
            if seq is not None:
                agent_mgr.handle_ack(seq)
            continue
```

### What This Source Proves
1. **WSL Connection Survival**: Explicitly handles incoming 4-second `ping` frames and replies with `pong`, keeping the virtual network bridge alive.
2. **Reconnection Recovery**: The `sync` message queries `agent_mgr.sync_client` with `last_seq`, allowing the browser to catch up on dropped tokens.
3. **Memory Safety**: The `ack` handler notifies `agent_mgr.handle_ack(seq)`, safely pruning older events from the memory buffer.

---

## Source 2: Unbuffered Subprocess Execution & Environment Whitelist

- **Source File**: `<project_root>/agents/agent_manager.py` (Historical Git Commit `f6e3adf`)
- **Location**: Subprocess Execution Environment Setup

```python
            # Whitelist strictly safe system environment variables
            safe_env = {
                k: v for k, v in os.environ.items()
                if k in ("PATH", "HOME", "USER", "LANG", "TERM", "SHELL") or k.startswith("AGY_")
            }
            # Force unbuffered Python stdout to prevent event stream delay
            safe_env["PYTHONUNBUFFERED"] = "1"
            safe_env["PYTHONIOENCODING"] = "utf-8"
            
            # Secure Proxy Setup: Force traffic through local broker
            safe_env["GEMINI_BASE_URL"] = "http://127.0.0.1:5000/api/proxy"
```

### What This Source Proves
1. **Zero Buffer Lag**: Git commit `f6e3adf` injected `PYTHONUNBUFFERED = "1"`, eliminating Python's default 4KB stdout buffer and allowing immediate real-time token streaming.
2. **UTF-8 Integrity**: Hardcoding `PYTHONIOENCODING = "utf-8"` prevents process crashes when AI models emit emojis or non-ASCII characters.
3. **Environment Sanitization**: Only non-sensitive host variables (`PATH`, `HOME`, `USER`) are forwarded to the agent; secret API keys are never directly exposed.

---

## Source 3: Git Evolution: From Terminal Deadlock to Headless Flags

- **Source**: Historical Git commits vs Modern Subprocess Invocation

### Early Vulnerable Code (Git history)
```python
# FLAWED: Spawning agent with default interactive TTY prompt
cmd = ["agy", "start", "--prompt", user_prompt]
process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
# Froze on "Do you trust this project? [Y/n]"
```

### Hardened Production Code (`agents/agent_manager.py`)
```python
# HARDENED: Explicit automation and bypass flags
cmd = [
    "agy",
    "--trust",
    "--headless",
    "--stream-json",
    "--model", "gemini-2.5-pro",
    user_prompt
]
```

### What This Source Proves
Passing `--trust` and `--headless` at process startup removes the interactive prompt from the CLI, enabling seamless background execution for screen readers.

---

## Why Order Matters in Streaming Architecture

1. **Unbuffer Environment Before Process Spawn**:
   - Setting `PYTHONUNBUFFERED=1` must occur in the environment dictionary *before* calling `create_subprocess_exec`. You cannot unbuffer a subprocess stream after it has launched.
2. **Send Pong Before Next Async Iteration**:
   - The WebSocket must respond with `pong` immediately before awaiting subsequent user tasks. Delaying the reply starves client heartbeat monitors.

---

## Beginner Coder Q&A

### Q: Why does Python buffer output by default?
**A:** Python buffers output in memory chunks (typically 4,096 bytes) to reduce the number of system calls and speed up batch processing. For interactive AI chat, this is disastrous because you see nothing until 4,000 characters have finished generating.

### Q: Why do we whitelist environment variables instead of passing `os.environ`?
**A:** In shared operating systems, `os.environ` often contains cloud credentials, database connection strings, or private auth tokens. Passing `os.environ` blindly would allow an untrusted agent or prompt injection to leak system secrets.
