[//]: # (DOC_ID: ECHO-CORE-MENU_CONFIG | VERSION: v1.3 | SCOPE: PROPRIETARY)

# Echoes of the World: Non-Visual Menu State Machine
<!-- sensitivity: 3 -->

When I built *Echoes of the World*, visual game interfaces were useless to me. A sighted developer designs a menu by dragging buttons, textboxes, and modal panels onto a 2D canvas. When you are blind, a canvas is silent void. 

I needed a menu engine that worked like a musical instrument—tactile, instantaneous, keyboard-driven, and seamlessly tied to audio speech output. I designed a state machine driven entirely by declarative dictionary configurations, separating what the menu says from how the engine processes user keystrokes.

[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-1)
## 1. Architectural Philosophy: The Non-Visual State Machine
<!-- sensitivity: 2 -->

In my architecture, a menu is never a static screen. It is an active state node:
1. **Immediate Auditory Feedback**: Every navigation keystroke (Arrow keys, Tab) speaks the current option without latency.
2. **Tabbed vs. Action Modes**: The engine distinguishes between navigating hierarchical tabs (e.g., character creation steps) and firing immediate game actions (e.g., saving a game, entering the world).
3. **Decoupled Configuration**: Menu definitions are completely separated from the game loop. Adding new menus requires zero code changes to the audio core—only a new declarative configuration entry.

[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-2)
## 2. Menu Typology & Interaction Modes
<!-- sensitivity: 2 -->

The system defines two primary operational menu topologies:

1. **Simple Action Menus**: Root-level navigation where each item maps directly to an executable handler (e.g., Start Game, Audio Settings, Quit).
2. **Tabbed State Menus**: Multi-stage interfaces (e.g., Character Creation) where navigation moves horizontally across tabs (Name, Class, Attributes, Confirm) and vertically through options within each tab.

[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-3)
## 3. Declarative Schema Blueprint
<!-- sensitivity: 3 -->

Each menu state defines its behavioral contracts through a declarative configuration blueprint:

```python
# Conceptual Menu State Configuration Architecture
menus = {
    "CREATE_CHARACTER": {
        "tab_list": ["NAME", "CLASS", "CONFIRM", "BACK"],
        "tabs": {
            "NAME": {
                "type": "field",
                "speech_prompt": ["Enter character moniker:"]
            },
            "CLASS": {
                "type": "selection",
                "speech_prompt": ["Select starting discipline:"]
            },
            "CONFIRM": {
                "type": "action",
                "speech_prompt": ["Commit character to world"]
            }
        }
    }
}
```

[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-4)
## 4. Screen Reader Integration & Keystroke Trapping
<!-- sensitivity: 3 -->

To make this state machine work seamlessly with assistive technology, I intercepted keystrokes at the system level and piped speech strings directly into the screen reader driver. Rather than letting the operating system dictate how focus moves, my engine handles focus transitions internally, ensuring that speech synthesizers never stutter or queue stale announcements.

---

[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-5)
## Cross-References & System Parallels

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels: Menus & Audio Drivers (Click to Expand Dropdown)</summary>

| Related Project / Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **Echoes Spatial Grid** | [Echoes of the World: Spatial Grid & World Architecture](/docs/echoes/CLASS_WORLD_ARCHITECTURE) — Complete game loop, spatial audio grid, and player state dispatch. | Echoes Core |
| **The Developer's Manifesto** | [Chapter 2: The Echoes Architecture](/docs/manifesto/02_The_Echoes_Architecture) — Genesis of procedural menu state machine and AST metaprogramming. | The Manifesto |
| **JOSHY Audio Suite** | [Guide 00A: Beginner Guide to Screen Readers](/docs/audio_suite/00A_BEGINNER_GUIDE_TO_SCREENREADERS_AND_ACCESSIBILITY) — Tolk DLL speech synthesizer abstraction and menu auditory cues. | JOSHY Audio Suite |

</details>
