[//]: # (DOC_ID: SIRA-DEV-04_17 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 04_17: Game Engine Plugin Integration Architecture

An architectural guide to integrating Siraugga into third-party game engines (Godot, Unreal Engine, Unity) as an out-of-process, zero-trust **Headless AI Daemon**.

---

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-1)
## Architectural Overview & Topology
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-1)

Embedding generative AI into video games traditionally risks freezing game frame rates and exposing game source code to hallucinating agents.

Siraugga enforces an **Out-of-Process Game Plugin Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                 HOST APPLICATION / GAME ENGINE              │
│                     (Unity, Unreal, Godot)                  │
│                                                             │
│   • 60 FPS Game Loop (Physics, Rendering, Input)            │
│   • Spawns background daemon with --windows-disable-console │
│   • Injects environmental context (player_health, location) │
└──────────────────────────────┬──────────────────────────────┘
                               │
               Local WebSocket IPC (ws://127.0.0.1:5000)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 SIRAUGGA HEADLESS BACKEND DAEMON            │
│                 (Compiled Standalone Binary)                │
│                                                             │
│   • Runs asynchronously on separate OS process              │
│   • Consumes 0% of the game's main thread frame budget      │
│   • Streams NDJSON dialogue and NPC thoughts in real time   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                Filesystem Operations Jailed by RBAC
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 CONFINED SANDBOX DIRECTORY                  │
│                (e.g., C:\Game\Player_Mods\)                 │
│                                                             │
│   • Modders write dynamic dialogue, quests, and Lua scripts │
│   • C++/C# Game Engine Source Code is 100% INVISIBLE        │
│   • Path traversal (../../src/) blocked with HTTP 403       │
└─────────────────────────────────────────────────────────────┘
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-2)
## The Two UI Rendering Methodologies
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-2)

1. **In-Game Web View Overlay (Chromium Embedded Framework - CEF)**:
   - The game engine renders an internal web browser overlay targeting `http://localhost:5000`.
   - Displays the fully accessible HTML5/Tailwind chat UI directly on a virtual in-game computer screen or HUD.
2. **Native Game Engine UI Parsing**:
   - The game connects directly to the WebSocket and parses the raw JSON stream.
   - Incoming AI text dynamically populates traditional RPG dialogue boxes, floating nameplates, or NPC speech bubbles.

---

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-3)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-3)

In game engine daemon lifecycle management, sequencing prevents orphaned processes:
1. **Spawn Daemon in Engine Initialization**: Start the headless `.exe` during game engine bootstrap so socket ports are bound before the title screen appears.
2. **Inject Environmental State Before Forwarding Speech**: Send game context JSON (`{"location": "Dungeon"}`) before the player speaks so the NPC responds with world awareness.
3. **Kill Daemon in `OnApplicationQuit`**: The game engine must send `SIGTERM` to the background PID when quitting to prevent background battery drain.

---

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-4)
## Reusable Integration Recipe (GDScript / Godot Example)
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-4)

```gdscript
extends Node

var client = WebSocketClient.new()

func _ready():
    # Step 1: Connect to local Siraugga daemon
    client.connect_to_url("ws://127.0.0.1:5000/ws")

func send_player_message(player_text):
    # Step 2: Inject real-time game context with prompt
    var payload = {
        "prompt": player_text,
        "context": {
            "player_health": 75,
            "current_zone": "Whispering Forest"
        }
    }
    client.get_peer(1).put_packet(JSON.print(payload).to_utf8())
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-5)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-6)

### Why can't the AI modify the game's C++ source code?
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-6)
The game engine starts the agent with its root directory set strictly to `C:\Game\Player_Mods\`. Any tool call attempting to navigate backwards (`../../`) is intercepted and blocked by the Security Manager.

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-7)
### Does running the agent slow down my game's FPS?
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-7)
No. Because the agent runs as a separate operating system process, all AI calculations occur on background CPU cores without interrupting the game's 60 FPS rendering loop.

---

[//]: # (SECTION_ID: SIRA-DEV-04_17-SEC-8)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_17-SEC-8)
- To understand why desktop window wrapping and game plugins required headless compilation, read [`01_PROBLEMS_ENCOUNTERED/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS.md`](/docs/devlog/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS).
- To inspect primary source citations of the game integration spec, view [`02_SOURCE_EVIDENCE/02_18_GAME_ENGINE_HEADLESS_DAEMON_EVIDENCE.md`](/docs/devlog/02_18_GAME_ENGINE_HEADLESS_DAEMON_EVIDENCE).
- To write a lightweight game engine WebSocket bridge script from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_19_GAME_ENGINE_WEBSOCKET_BRIDGE_FROM_SCRATCH.md`](/docs/devlog/05_19_GAME_ENGINE_WEBSOCKET_BRIDGE_FROM_SCRATCH).
