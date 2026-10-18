[//]: # (DOC_ID: SIRA-DEV-02_18 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 02_18: Game Engine Headless Daemon Evidence

Primary source evidence from the Siraugga Game Engine Integration specification demonstrating how the autonomous agent operates as a headless background daemon, exchanges JSON RPC events with game loops, and enforces zero-trust source code protection.

---

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-1)
## Source Citation 1: The Headless Subprocess Daemon (`docs/architecture/game_engine_integration.md`)
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-1)

This excerpt details how parent game engines (Unity, Unreal, Godot) spawn and bind the agent backend:

```markdown
# Location: <project_root>/docs/architecture/game_engine_integration.md
# Section 1 & 2

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-1)
## 1. The Headless Daemon (Boot Sequence)
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-1)
The agent is explicitly designed NOT to function as a traditional desktop application when deployed as a plugin. 
Instead, the entire Python backend (Quart server, Agent Manager, Security Manager) is compiled into a single, native machine-code executable using a C-compiler (e.g., Nuitka).
* Execution: The parent Game Engine triggers this executable as a background subprocess.
* Visibility: The executable is compiled with terminal-suppression flags (--windows-disable-console). It runs completely invisibly.
* Binding: Upon launch, it instantly binds to http://localhost:5000 (and ws://localhost:5000) on the host machine.

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-2)
## 2. The WebSocket Bridge (Communication)
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-2)
The Game Engine and the Agent do not share memory; they communicate exclusively over a local WebSocket.
* State Injection: Game Engines can silently feed real-time environmental context to the agent behind the scenes via hidden JSON payloads (e.g., {"player_health": 40, "location": "Dark Forest"}).
* Event Streaming: The agent streams its thought processes, tool executions, and final text back to the Game Engine chunk-by-chunk via stream-json NDJSON formatting.
```

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-2)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-2)
- **Decoupled Process Isolation**: The game engine does not link Python into its game loop thread; it runs the agent as an out-of-process daemon, preventing AI crashes from crashing the game frame rate.
- **Context Injection Channel**: Game engines inject real-time game world state (`{"player_health": 40, ...}`) across the local loopback WebSocket without user awareness.

---

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-3)
## Source Citation 2: Protecting Host Engine Source Code (`docs/architecture/game_engine_integration.md`)
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-3)

This excerpt documents how the Access Control Module prevents the AI from touching the game developer's proprietary C++/C# engine files:

```markdown
# Location: <project_root>/docs/architecture/game_engine_integration.md
# Section 5

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-5)
## 5. Protecting Host Source Code (Zero-Trust Injection)
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-5)
A critical requirement of plugging this agent into third-party projects is guaranteeing that the AI cannot accidentally (or maliciously) modify the parent application's proprietary source code.
* Workspace Confinement: When the parent application starts the daemon, it designates a strictly confined directory (e.g., C:\MyGame\Player_Mods\). 
* Path Traversal Defense: The internal Access Control Module uses strict os.path.realpath boundary checks. If the agent attempts to use directory traversal (e.g., reading ../../src/main_engine.cpp) to look at the host application's source code, the backend intercepts the filesystem call, instantly blocks the execution, and returns a PermissionError.
* The Guarantee: The parent application's source code, host OS files, and intellectual property remain 100% invisible and physically inaccessible to the AI agent.
```

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-4)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-4)
- **Proprietary Code Armor**: Path traversal tricks (`../../src/main_engine.cpp`) are intercepted at the filesystem layer by `resolve_safe_path()`, throwing immediate `PermissionError` (HTTP 403).
- **Safe Sandboxing for Modders**: Community players can write dialogue, Lua scripts, or item configs in their designated mod folders without risking tampering with core engine binaries.

---

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-5)

In game engine subprocess management, boot sequence prevents socket connection failures:
1. **Launch Daemon Subprocess First**: The game engine must start the headless executable and wait for Port 5000 to respond before rendering the in-game UI overlay.
2. **Inject Environmental State Before User Prompts**: Send game context JSON (`player_location`) *before* forwarding the player's speech input so the AI responds with full situational awareness.
3. **Terminate Daemon in Game Engine Shutdown Hook**: The game engine's `_exit_tree()` or `OnApplicationQuit()` handler must terminate the background process to prevent orphaned daemons.

---

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-7)

### What does `--windows-disable-console` do?
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-7)
When compiling a Python script to an `.exe`, Windows usually opens a black command prompt box. This flag hides the console window entirely, letting the agent run invisibly in the background.

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-8)
### What is CEF (Chromium Embedded Framework)?
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-8)
CEF is a lightweight browser engine that game developers embed inside 3D games (like Unity or Unreal) to display HTML5 web interfaces on virtual computer screens or HUDs.

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-9)
### How does the game engine know when the AI finished talking?
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-9)
The agent streams JSON chunks over the WebSocket. When the final chunk has `"done": true`, the game engine triggers the character's speaking animation or closes the dialogue box.

---

[//]: # (SECTION_ID: SIRA-DEV-02_18-SEC-10)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-02_18-SEC-10)
- To understand why desktop window wrapping and game plugins required headless compilation, read [`01_PROBLEMS_ENCOUNTERED/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS.md`](/docs/devlog/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS).
- To view the complete game engine architecture blueprint, visit [`04_SOLUTIONS_AND_ARCHITECTURE/04_17_GAME_ENGINE_PLUGIN_INTEGRATION_ARCHITECTURE.md`](/docs/devlog/04_17_GAME_ENGINE_PLUGIN_INTEGRATION_ARCHITECTURE).
- To write a lightweight game engine WebSocket bridge script from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_19_GAME_ENGINE_WEBSOCKET_BRIDGE_FROM_SCRATCH.md`](/docs/devlog/05_19_GAME_ENGINE_WEBSOCKET_BRIDGE_FROM_SCRATCH).
