[//]: # (DOC_ID: ECHO-CORE-MENU | VERSION: v1.2 | SCOPE: Echoes of the World (Audio Game))

# 🧭 Menu Configuration Guide

This document defines the expected structure and behavior of the `menus` dictionary used to drive the application's dynamic, tab-based interface.

## 🔹 Overview
[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-1)

Each top-level key in the `menus` dictionary is a dynamic menu identifier (e.g. `"MAIN_MENU"`, `"CREATE_CHARACTER"`).

- Menus may or may not define tabs.
- If a menu includes `tab_list` and `tabs`, it's considered a **tabbed menu**.

## 🔹 Menu Types
[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-2)

### 1. Simple Menus
[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-1)
Menus that don't contain tabs. Used for general selection or root navigation.  
They do not define `tab_list` or `tabs`.

### 2. Tabbed, Menus
[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-2)
Contain two required entries:

- `tab_list`: A list of strings, defining the order of tabs (e.g. `["EMAIL", "NAME", "SUBMIT"]`)
- `tabs`: A dictionary containing one config object per tab.

These keys must always appear together. If one is missing, the config is considered invalid.

## 🔹 Tab Entry Structure
[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-3)

Each entry inside `tabs` must define:

- `type`: Defines the tab’s behavior. Accepted values:
  - `"field"` → Sets `self.edit = True`
  - `"action"` → Sets `self.edit = False`, triggers internal handler
- `menu_itims`: Required. A list of display/speech items associated with the tab.

No additional flags (like `"edit"`) are required. All behavior is inferred from `type`.

## 🔹 Example
[//]: # (SECTION_ID: ECHO-CORE-MENU-SEC-4)

```python
menus = {
    "CREATE_CHARACTER": {
        "tab_list": ["EMAIL", "NAME", "PASSWORD", "BACK"],
        "tabs": {
            "EMAIL": {
                "type": "field",
                "menu_itims": ["Enter your email"]
            },
            "BACK": {
                "type": "action",
                "menu_itims": ["Return to main menu"]
            }
        }
    }
}
```

---

<details>
<summary>🔽 Related Engine Architectures & Audio Systems (Click to Expand)</summary>

* **Echoes of the World — Class & World Architecture**:
  * Complete game loop, spatial audio grid, and player state dispatch.
* **JOSHY Audio Playback Suite**:
  * *00A Primer*: Screen reader accessibility, speech synthesizer abstraction, and menu auditory cues.
* **The Developer Manifesto**:
  * *Chapter 2 — The Echoes Architecture*: Genesis of the procedural menu state machine and NVDA DLL ctypes integration.

</details>
