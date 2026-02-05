# Main menu options
main_menu = ["CREATE_CHARACTER", "START_GAME", "PROFILES", "SETTINGS", "EXIT"]

# CREATE_CHARACTER tab definitions
email_type = "field"
email_items = ["enter your email"]
email_tab = {"type": email_type, "menu_itims": email_items}

name_type = "field"
name_items = ["enter your name"]
name_tab = {"type": name_type, "menu_itims": name_items}

password_type = "field"
password_items = ["enter your password"]
password_tab = {"type": password_type, "menu_itims": password_items}

confirm_password_type = "field"
confirm_password_items = ["confirm your password"]
confirm_password_tab = {"type": confirm_password_type, "menu_itims": confirm_password_items}

back_type = "action"
back_items = ["Return to main menu"]
back_tab = {"type": back_type, "menu_itims": back_items}

start_game_type = "action"
start_game_items = ["START_GAME"]
start_game_tab = {"type": start_game_type, "menu_itims": start_game_items}

create_character_tabs = {
    "EMAIL": email_tab,
    "NAME": name_tab,
    "PASSWORD": password_tab,
    "CONFIRM_PASSWORD": confirm_password_tab,
    "BACK": back_tab,
    "START_GAME": start_game_tab,
}

create_character = {
    "tab_list": list(create_character_tabs.keys()),
    "tabs": create_character_tabs,
}

# PROFILES menu definition
profiles_back_type = "action"
profiles_back_items = ["BACK"]
profiles_back_tab = {"type": profiles_back_type, "menu_itims": profiles_back_items}

profiles_exit_type = "action"
profiles_exit_items = ["EXIT"]
profiles_exit_tab = {"type": profiles_exit_type, "menu_itims": profiles_exit_items}

profiles_tabs = {
    "BACK": profiles_back_tab,
    "EXIT": profiles_exit_tab,
}

profiles_menu = {
    "tab_list": list(profiles_tabs.keys()),
    "tabs": profiles_tabs,
}




        # settings menu definition
settings_back_type = "action"
settings_back_items = ["BACK"]
settings_back_tab = {"type": settings_back_type, "menu_itims": settings_back_items}

settings_exit_type = "action"
settings_exit_items = ["EXIT"]
settings_exit_tab = {"type": settings_exit_type, "menu_itims": settings_exit_items}

settings_tabs = {
    "BACK": settings_back_tab,
    "EXIT": settings_exit_tab,
}

settings_menu = {
    "tab_list": list(settings_tabs.keys()),
    "tabs": settings_tabs,
}



# QUIT menu definition
quit_type = "action"
quit_items = ["BACK", "EXIT"]
quit_back_exit = {"type": quit_type, "menu_itims": quit_items}

quit_tabs = {
    "BACK": quit_back_exit,
    "EXIT": quit_back_exit}

quit_menu = {
    "tab_list": list(quit_tabs.keys()),
    "tabs": quit_tabs,}

# Final menus dictionary
menus = {
    "MAIN_MENU": main_menu,
    "CREATE_CHARACTER": create_character,
    "PROFILES": profiles_menu ,
    "SETTINGS": settings_menu,
    "QUIT": quit_menu,
}
