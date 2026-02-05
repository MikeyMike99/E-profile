`````````````````````````````````````````````````````````# 🧭 Menu Configuration Guide

This document defines the expected structure and behavior of the `menus` dictionary used to drive the application's dynamic, tab-based interface.

## 🔹 Overview

Each top-level key in the `menus` dictionary is a dynamic menu identifier (e.g. `"MAIN_MENU"`, `"CREATE_CHARACTER"`).

- Menus may or may not define tabs.
- If a menu includes `tab_list` and `tabs`, it's considered a **tabbed menu**.

## 🔹 Menu Types

### 1. Simple Menus
Menus that don't contain tabs. Used for general selection or root navigation.  
They do not define `tab_list` or `tabs`.

### 2. Tabbed, Menus
Contain two required entries:

- `tab_list`: A list of strings, defining the order of tabs (e.g. `["EMAIL", "NAME", "SUBMIT"]`)
- `tabs`: A dictionary containing one config object per tab.

These keys must always appear together. If one is missing, the config is considered invalid.

## 🔹 Tab Entry Structure

Each entry inside `tabs` must define:

- `type`: Defines the tab’s behavior. Accepted values:
  - `"field"` → Sets `self.edit = True`
  - `"action"` → Sets `self.edit = False`, triggers internal handler
- `menu_itims`: Required. A list of display/speech items associated with the tab.

No additional flags (like `"edit"`) are required. All behavior is inferred from `type`.

## 🔹 Example

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
