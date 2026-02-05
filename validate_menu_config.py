from menu_config import menus
from NVDA import nvda_speak

def validate_menu_config(menu, nvda_speak):
    allowed_types = {"field", "action"}
    all_valid = True  # Will track if we found any issues

    for menu_name, menu_config in menus.items():
        if "tab_list" in menu_config and "tabs" in menu_config:
            tab_list = menu_config["tab_list"]
            tabs = menu_config["tabs"]

            # Validate all tab_list entries
            for tab_id in tab_list:
                if tab_id not in tabs:
                    nvda_speak(f"In menu {menu_name}, tab '{tab_id}' is listed but not defined.")
                    all_valid = False

            # Validate each tab config
            for tab_name, tab_data in tabs.items():
                if "type" not in tab_data:
                    nvda_speak(f"In menu {menu_name}, tab '{tab_name}' is missing a 'type'.")
                    all_valid = False
                elif tab_data["type"] not in allowed_types:
                    nvda_speak(f"In menu {menu_name}, tab '{tab_name}' has an invalid type '{tab_data['type']}'.")
                    all_valid = False

                if "menu_itims" not in tab_data:
                    nvda_speak(f"In menu {menu_name}, tab '{tab_name}' is missing 'menu_itims'.")
                    all_valid = False
        elif "tab_list" in menu_config or "tabs" in menu_config:
            nvda_speak(f"Menu {menu_name} is missing either 'tab_list' or 'tabs'. Both are required together.")
            all_valid = False

    if all_valid:
        nvda_speak("Menu config validation passed.")
    else:
        nvda_speak("One or more errors found in the menu config.")
