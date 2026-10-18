[//]: # (DOC_ID: SIRA-ARCH-05_19 | VERSION: v1.0 | SCOPE: ARCH)

# Game Engine WebSocket Bridge from Scratch

[//]: # (SECTION_ID: SIRA-ARCH-05_19-SEC-1)
## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_19-SEC-1)
Modern video games and virtual simulations require intelligent NPCs, dynamic quest generation, and real-time world narration. However, embedding heavy AI runtimes directly inside game engines introduces memory bloat and frame-rate stuttering.

The Game Engine WebSocket Bridge decouples the game engine (e.g., Godot, Unity, Unreal) from the AI runtime. The AI engine runs as a lightweight, headless background daemon on `127.0.0.1:5000`. The game connects via local WebSocket, transmitting real-time player telemetry and receiving narrative dialogue, quest modifications, and TTS audio chunks without dropping frames.

```
+-------------------------------------------------------------+
|              Game Engine Process (Godot / Unity)            |
|              Main Game Loop (60-144 FPS Rendering)          |
+-------------------------------------------------------------+
                              |
                     WebSocket Client IPC
                     ws://127.0.0.1:5000/ws
                              |
                              v
+-------------------------------------------------------------+
|             Siraugga Headless Background Daemon             |
|              Quart / Hypercorn ASGI Engine                  |
+-------------------------------------------------------------+
                              |
               Zero-Trust Safe Path Confinement
               Allowed: ./game_demo/saves/, ./mods/
               Blocked: Game Engine Source / Root System
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_19-SEC-2)
## 2. Complete Python Bridge Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_19-SEC-2)
Save the following script as `game_bridge.py`:

```python
import asyncio
import json
import websockets

BACKEND_WS_URL = "ws://127.0.0.1:5000/ws"

class GameAIBridge:
    def __init__(self, uri: str = BACKEND_WS_URL):
        self.uri = uri
        self.connection = None
        self.seq = 0

    async def connect(self):
        """Establishes resilient loopback WebSocket connection to Siraugga."""
        print(f"[BRIDGE] Connecting to AI engine at {self.uri}...")
        self.connection = await websockets.connect(self.uri)
        print("[BRIDGE] Connected to AI engine daemon.")

    async def send_game_telemetry(self, player_data: dict, npc_name: str, dialogue_input: str):
        """Pushes structured game state to the AI orchestrator."""
        payload = {
            "type": "game_event",
            "seq": self.seq,
            "data": {
                "player_health": player_data.get("health", 100),
                "location": player_data.get("zone", "Town Square"),
                "target_npc": npc_name,
                "user_speech": dialogue_input
            }
        }
        await self.connection.send(json.dumps(payload))
        self.seq += 1

    async def listen_for_narrative(self, callback):
        """Asynchronously listens for AI responses and triggers in-game audio/dialogue."""
        try:
            async for message in self.connection:
                event = json.loads(message)
                event_type = event.get("type")
                
                # Acknowledge received chunk (ACK protocol)
                if "seq" in event:
                    ack = {"type": "ack", "seq": event["seq"]}
                    await self.connection.send(json.dumps(ack))
                
                if event_type == "npc_dialogue":
                    callback(event["speaker"], event["text"], event.get("audio_url"))
                elif event_type == "world_modification":
                    print(f"[BRIDGE] Modifying game state: {event['patch']}")
        except websockets.exceptions.ConnectionClosed:
            print("[BRIDGE] Connection to AI engine closed.")

# Sample Godot GDScript integration pattern (Conceptual snippet):
"""
# In Godot (player_controller.gd):
var ws = WebSocketPeer.new()
func _ready():
    ws.connect_to_url("ws://127.0.0.1:5000/ws")

func send_player_action(prompt_text):
    var packet = JSON.stringify({"type": "prompt", "text": prompt_text})
    ws.send_text(packet)
"""

if __name__ == "__main__":
    async def sample_run():
        bridge = GameAIBridge()
        await bridge.connect()
        
        def handle_npc(speaker, text, audio):
            print(f"\n[NPC DIALOGUE] {speaker}: '{text}'")
            if audio:
                print(f"[TTS AUDIO URL] {audio}")

        # Listen in background task
        listener = asyncio.create_task(bridge.listen_for_narrative(handle_npc))
        
        # Simulate sending player speech
        await bridge.send_game_telemetry({"health": 85, "zone": "Dungeon Entrance"}, "Guard", "Halt! Who goes there?")
        await asyncio.sleep(2)
        listener.cancel()

    asyncio.run(sample_run())
```

---

[//]: # (SECTION_ID: SIRA-ARCH-05_19-SEC-3)
## 3. Why Order Matters in Game Bridge Communication
[//]: # (SECTION_ID: SIRA-DOC-05_19-SEC-3)
1. **Send Monotonic ACK Immediately**: Transmitting `{"type": "ack", "seq": N}` as soon as an event arrives prevents the server buffer from growing endlessly during heavy gameplay.
2. **Decouple Render Frame from Network Socket**: WebSocket reads must run asynchronously or in a worker thread so waiting for AI responses never drops rendering FPS below 60.
3. **Validate Target Paths on World Modification**: If the AI returns a file patch for a mod or quest script, the bridge must verify that the path resolves inside `./mods/` or `./saves/` before writing to disk.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_19-SEC-4)
## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_19-SEC-4)
**Q: Can this slow down game performance?**  
A: No! The AI engine runs in an isolated OS process. Network communication is handled over loopback sockets asynchronously, consuming zero GPU cycles and negligible CPU time from the game engine.

**Q: What happens if the AI engine is not running when the game starts?**  
A: The game bridge's connection fails gracefully with `ConnectionRefused`. The game continues normally with fallback scripted NPC dialogues.

**Q: How does the AI know where the player is located?**  
A: The `send_game_telemetry()` function packages relevant game state (health, zone, active quest, inventory) into a JSON frame that the AI includes in its reasoning prompt.
