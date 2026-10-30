# Antigravity Assistant & System Guidelines

---

## 1. Project Overview & Architecture
This project is an **Accessible, Resilient Antigravity Web Portal** designed as a plugin for in-game development environments and personalized developer applications. It bridges web clients to the local `agy` CLI via a zero-restart, event-driven streaming architecture.

### Modular Component Layout
- **Frontend Template (`templates/index.html`)**: Contains all HTML markup, Tailwind styles, and client JavaScript. Any changes to layout, styling, or client logic take effect immediately upon browser refresh (**F5**) with zero server restarts.
- **App Router & Hot-Reload (`server.py`)**: Quart HTTP/WebSocket server. Never kill or restart this process for code changes; use the in-memory reload endpoint.
- **Task & Process Orchestration (`agent_manager.py`)**: Manages `agy` CLI subprocess execution, parses `stream-json` events, handles task cancellation, and coordinates keep-alive heartbeats.
- **Security & Access Control (`security_manager.py`)**: Implements Role-Based Access Control (RBAC), token authentication, path traversal defense, and file classification tiers.
- **Project Workspaces (`project_manager.py`)**: Handles game project folder creation, listing, and active directory switching.
- **Brain Sessions (`session_manager.py`)**: Discovers historical sessions from Antigravity Brain (`~/.gemini/antigravity-cli/brain`) and parses message transcripts.

---

## 2. Response Formatting & Screen Reader Optimization
1. **No Raw Code Dumps or Verbose Logs**:
   - Summarize code changes, terminal actions, and command outcomes concisely.
   - Never print long terminal traces or full multi-page file dumps in conversational responses.
2. **Clear Task Status**:
   - Clearly delineate what was completed and what remains pending or next.
3. **Clean Heading Structures**:
   - Maintain minimal, semantic heading structures (capped at H3–H4) to protect screen reader navigation.
4. **Clickable Links**:
   - Use GitHub-style markdown links with the `file://` scheme for all modified files and symbols.

---

## 3. Zero-Restart In-Memory Reload & Safe Hot-Patch Sequence
- **Never Kill Port 5000**:
  - Do not use external kill scripts during active sessions. Hard restarts drop active WebSocket connections, disrupt browser state, and risk port-binding conflicts.
- **Mandatory 3-Step Safe Hot-Patch Sequence**:
  1. **Stage in `core/patches/`**: Never edit live backend engine `.py` files (`core/`, `core/routes/`, `agents/`, `agents/mixins/`, `security/`) directly in place. Always write the complete updated Python module to `/mnt/c/Users/michael/Documents/DevCore/core/patches/<filename>.py`.
  2. **Trigger Hot-Patch Validation & Swap**: Execute `curl -s -X POST http://127.0.0.1:5000/api/simulate-patch` (or `POST http://127.0.0.1:5000/api/reload`).
  3. **Automated Validation, Backup & Rollback**: `execute_hot_patch_sequence()` compiles every staged file via `py_compile.compile(..., doraise=True)`, snapshots the previous live version into `core/backups/<filename>.py`, copies the validated patch to its live target path, hot-reloads modules and Quart view functions in memory (`importlib.reload()` + `_sync_live_blueprint_routes()`), removes the staged file from `core/patches/`, and automatically rolls back from `core/backups/` if any runtime error occurs.

---

## 4. Connection Resilience & Stream Continuity
- **4-Second Client Keep-Alive**:
  - Windows WSL 2 networking drops idle TCP connections after 30 seconds of silence. The browser client must send `{"type": "ping"}` every 4 seconds.
- **Guaranteed Delivery Queue (ACK Protocol)**:
  - Every agent event is assigned a monotonic sequence number (`seq`).
  - Events are buffered on the server and are only pruned when the client explicitly acknowledges them via `{"type": "ack", "seq": N}`.
  - On reconnect, the client transmits `{"type": "sync", "last_seq": N}`, and the server immediately replays any missed chunks.
- **No Silent Tool Execution**:
  - Avoid extended pauses during tool operations without status updates, which cause user-side timeout assumptions.

---

## 5. In-Game Developer Sandboxing & Security Tiers
Because this system serves third-party game developers and modders, strict boundaries are enforced to prevent data leaks, source code tampering, and prompt injections.

### File Classification Tiers
1. **`TIER_SAFE_WORKSPACE`**: Game scripts, configs, JSON data (`npc_state.json`), dialogue, Lua scripts, and documentation inside assigned project directories. Accessible to developers for reading and editing.
2. **`TIER_CORE_ENGINE`**: Server and orchestration scripts (`server.py`, `agent_manager.py`, `security_manager.py`, `project_manager.py`, `session_manager.py`). **Admin only**.
3. **`TIER_ADMIN_LOG`**: Daemon and stdout logs (`upgrade.log`, `server_stdout.log`). **Admin read-only**.
4. **`TIER_FORBIDDEN`**: Virtual environments (`venv/`), Git internals (`.git/`), hidden directories, `.env` files, and path-traversal escapes. **Hard-blocked for all roles**.

### Role-Based Access Control (RBAC) & Test Accounts
- **`admin` / `admin`**: Full administrative access to all workspaces, core engine files, and system logs.
- **`dev` / `dev`** (Role: `gamedev`): Jailed strictly to assigned game project folders (`game_demo`, `npc_quest`). Engine code and logs are invisible.
- **`mod` / `mod`** (Role: `modder`): Read-only access to safe workspace game assets. Save operations are blocked.

### Prompt Injection & Agent Sandboxing
- **Workspace Confinement**: For non-admin developers, `agy` is launched with `cwd` set strictly to their assigned project folder. Antigravity's OS-level protection boundaries block searching or reading outside this root.
- **Sandboxed Execution**: For non-admins, enforce the `--sandbox` flag on `agy` to isolate terminal command execution and prevent host inspection.
- **No Permission Skip for Devs**: Omit `--dangerously-skip-permissions` for third-party developer roles; all operations must conform to safe workspace rules.
- **Path Traversal Defense**: All file access via the web API must pass through `resolve_safe_path()` to guarantee that paths resolving outside the target boundary throw immediate `PermissionError` (HTTP 403).

---

## 6. Interactive Artifact Viewer & Safe Saving Routing
When agents generate `.md` artifacts (like Implementation Plans) and require user feedback, the UI uses a specialized Flip Card architecture:

### Accessibility & Editor UX
- **No Raw `contenteditable` HTML**: The back of the card relies strictly on a native `<textarea class="artifact-raw-editor">` for direct raw markdown editing. This guarantees standard form-control behavior (like the `E` key shortcut) for screen readers.
- **Auto-Focus Hook**: `rawEditor.focus()` is called immediately upon flipping the card to instantly alert the screen reader to the state change.

### WSL & Windows I/O Interop
- **Broken Pipes Mitigation**: Do NOT use `wsl.exe bash -c "cat > file"` with `stdin=subprocess.PIPE` inside `server.py`, as it can silently drop data on Windows.
- **Save Route (`POST /api/artifacts/save`)**: Artifacts are saved by writing a temporary `.md` file to the Windows host directory first, then using `wsl.exe cp` (via `wslpath -a`) to move it into the Linux `/home/...` artifact directory safely.

### Artifact Access Control (RBAC)
- **Admins (Tier 5)**: Allowed to natively fetch, flip, directly edit, and save artifacts.
- **Developers (Tier 3)**: Denied direct file access. Clicking an artifact triggers an invisible WebSocket instruction asking the agent to read the plan, scrub out root credentials/secrets, and provide a high-level technical summary in the chat window.

---

## 7. Error Handling & Loop Prevention
- **No Infinite Loops**: If a tool call (such as searching, reading a file, or running a command) fails or returns an error, DO NOT retry it in a loop.
- **Fail Fast & Inform User**: If you hit a restriction, error, or sandbox boundary, immediately STOP. Output a summary of the error to the user and ask for guidance.
- **Avoid Massive Directories**: Regardless of admin or sandbox status, DO NOT recursively search massive directories (like env or 
ode_modules). Traversing these causes immediate quota exhaustion and API hammering.

---

## 8. Artifact Feedback Restrictions & Loop Prevention
The Antigravity system intercepts artifacts generated with the `RequestFeedback: true` flag and may route them through an automated "auto-approve" review policy. This can trap the agent in an autonomous runaway loop where the human user is bypassed.
- **NEVER** use `RequestFeedback: true` in the `ArtifactMetadata` when generating standard Markdown documents, Devlogs, Textbook Drafts, or simple text summaries. 
- **ONLY** use `RequestFeedback: true` when explicitly requesting the user to execute a physical Implementation Plan script.
- If the system ever fires a `Stop hook blocked termination: The user has automatically approved...` message unexpectedly, you MUST immediately halt, stop using `RequestFeedback`, and wait for manual text confirmation from the user to break the loop.

---

## 9. Clean Code & Comment Hygiene (Strict Prohibition of Useless Comments)
- **No Obvious or Conversational Inline `#` Comments**:
  - AI agents MUST NOT write redundant, obvious, numbered-step, or decorative `#` comments in `.py` files (e.g., `# 1. Enforce Authentication`, `# Initialize managers`, `# Check if file exists`, `# --- SECTION ---`).
  - Code should be self-documenting through clear naming and modular structure.
- **Concise Docstrings Only When Necessary**:
  - Use brief module, class, or function docstrings (`"""..."""`) strictly to explain non-obvious architectural contracts, security invariants, or protocol semantics.
- **No Leftover Debug or Historical Commentary**:
  - Never leave commented-out code, historical bug notes, or conversational remarks inside `.py` files.

