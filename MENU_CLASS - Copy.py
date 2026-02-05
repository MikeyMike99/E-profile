import pygame
import pyperclip
from NVDA import nvda_speak
from menu_config import menus

class Menu:
    def __init__(self):
        self.menu_active=False
        self.edit = False
        self.input_text = [""]
        self.selection_start = 0# Start position of selection
        self.selection_end = 0# End position of selection
        self.selecting = False  # Tracks if selection mode is active
        self.cursor = max(len(self.input_text[0]) - 1, 0)
        self.selected_character = ""
        self.right_selection=False
        self.left_selection=False
        self.menu_items = []
        self.selected_index = 0
        self.current_menu = None
        self.tab_list = []
        self.tab_dict = None
        self.tab_menu=None
        self.tab_index = 0
        self.selected_tab = None
        self.action = None
        self.menus = menus
        self.edit_fields={}
        self.previous_menu = []
        self.validation = {
            "EMAIL": lambda email: self.validate_email(email),
            "NAME": lambda name: self.validate_name(name)}
        self.input_data = {}
        self.key_actions = {
            pygame.K_UP: lambda: self.navigate(-1),
            pygame.K_DOWN: lambda: self.navigate(1),
            pygame.K_LEFT: lambda: self.move_cursor("left"),
            pygame.K_RIGHT: lambda: self.move_cursor("right"),
            pygame.K_ESCAPE: lambda: self.excecute("BACK"),
            pygame.K_RETURN: lambda: self.select_menu_item("enter"),
            pygame.K_SPACE: lambda: self.select_menu_item(None),
            pygame.K_TAB: self.switch_tab,
            pygame.K_BACKSPACE: lambda: self.delete_character("delete_left"),
            pygame.K_DELETE: lambda: self.delete_character("delete_right"),
            }

    def handle_key_press(self, event):
        """Processes key presses dynamically using a mapping system."""
        # If editing, handle text input 
        
        if self.edit and event.unicode.isprintable() and event.unicode != "":
            if self.selecting:
                self.delete_character()
            self.input_text[0] = (
            self.input_text[0][:self.cursor]  # Text before cursor
            + event.unicode                    # Insert new character
            + self.input_text[0][self.cursor:]  # Text after cursor
            )
            self.update_input_text()
            self.cursor += 1  # Move cursor forward after insertion
            if event.unicode == " ":
                nvda_speak("Space")
            else:
                nvda_speak(event.unicode)

        # Detect Ctrl+V for Clipboard Pasting
        if event.key == pygame.K_v and event.mod & pygame.KMOD_CTRL and self.edit:
            clipboard_text = pygame.scrap.get("text/plain;charset=utf-8")
            if clipboard_text:
                # Decode to remove unnecessary null bytes
                clipboard_text = clipboard_text.decode("utf-16").strip()
                clipboard_text = clipboard_text.replace("\x00", "").strip()
                self.input_text[0] = (
                        self.input_text[0][:self.cursor]  # Text before cursor
                        + clipboard_text                   # Insert clipboard text
                        + self.input_text[0][self.cursor:] # Text after cursor
                    )
                self.cursor += len(clipboard_text)  # Move cursor forward after pasting
                nvda_speak(f"Pasted: {clipboard_text}")

                return
            else:
                nvda_speak("No text found in clipboard.")

        if event.key == pygame.K_c and event.mod & pygame.KMOD_CTRL:
            if self.selecting and self.selection_start != self.selection_end:
                selected_text = self.input_text[0][self.selection_start:self.selection_end]
                pyperclip.copy(selected_text)
                nvda_speak(f"Copied  {selected_text}")

        if event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self.selection_start = 0
            self.selection_end = len(self.input_text[0])
            self.selecting=True
            nvda_speak(self.input_text[0][self.selection_start:self.selection_end])

        # Execute mapped function if the key exists
        if event.key in self.key_actions:
            self.key_actions[event.key]()  # Calls the corresponding function


    def update_input_text(self):
        words = self.input_text[0].split()  
        self.menu_items = [' '.join(words[i:i + 10]) for i in range(0, len(words), 10)]

    def navigate(self, direction):
        """Handles menu navigation."""
        if not self.menu_items:
            nvda_speak("empty!")
            return
        self.selected_index = (self.selected_index + direction) % len(self.menu_items)
        nvda_speak(f"{self.menu_items[self.selected_index]}")

    def move_cursor(self, direction):
        """Moves the cursor left or right, supporting word selection."""
        
        if not self.input_text or not self.input_text[0]:
            return

        move_direction = -1 if direction == "left" else 1

        mods = pygame.key.get_mods()
        selecting = mods & pygame.KMOD_CTRL and mods & pygame.KMOD_SHIFT
        if not selecting:
            cursor_boundry= len(self.input_text[0])  # Allow one position beyond last character
            if self.cursor > cursor_boundry:
                self.cursor = cursor_boundry# Keep it at the one-space limit
            elif self.cursor < 0:  
                self.cursor = 0  # Prevent moving before the start
            else:
                # Adjust cursor position within limits
                self.cursor = max(0, min(len(self.input_text[0]), self.cursor + move_direction))

        if selecting:
            self.selecting=True
        else:
            self.selecting=False
            self.left_selection=False
            self.right_selection=False
            self.selection_start=0
            self.selection_end=0
            self.selected_character = self.input_text[0][self.cursor] if self.cursor < len(self.input_text[0]) else ""
            # Announce the character, replacing space with "Space"
            nvda_speak("Space" if self.selected_character == " " else self.selected_character)

        if self.selecting and direction== "left" and self.selection_start - self.selection_end ==0 :
            self.left_selection=True
            self.right_selection=False

        if self.left_selection  and selecting and direction == "left":
                # Step 1: Skip spaces
                while self.cursor> 0 and self.input_text[0][self.cursor- 1] == " ":
                    self.cursor-= 1  # Move left past spaces

                # Step 2: Move left until start of word or beginning of field
                while self.cursor> 0 and self.input_text[0][self.cursor- 1] != " ":
                    self.cursor-= 1  # Move left until reaching a space or field start

                #  update selection start
                self.selection_start=self.cursor
                # Step 1: Move right until a space is encountered or reach the end of the field
                while self.cursor< len(self.input_text[0]) - 1 and self.input_text[0][self.cursor] != " ":
                    self.cursor+= 1  # Move right until the end of the word

                # Step 2: If there's a space, move to it
                if self.cursor < len(self.input_text[0]) - 1:
                    if self.input_text[0][self.cursor] == " ":
                        self.cursor += 1  # Stop at the first space after the word
                else:
                    self.cursor = len(self.input_text[0])  # Stop at last character if no space exists

                # update selection end. only once
                if self.selection_end == None or self.selection_end == 0:
                    self.selection_end=self.cursor
                #  set the curser at the beginning of the word for further expantion
                self.cursor=self.selection_start
                self.selected_character = self.input_text[0][self.cursor] if self.cursor < len(self.input_text[0]) else ""

        #  deselect words if words is selected to the right
        if self.right_selection and selecting and direction == "left":
            while self.cursor> 0 and self.input_text[0][self.cursor- 1] == " ":
                self.cursor-= 1  # Move left past spaces

            # Step 2: Move left until start of word or beginning of field
            while self.cursor> 0 and self.input_text[0][self.cursor- 1] != " ":
                self.cursor-= 1  # Move left until reaching a space or field start

            # update selection end. 
            self.selection_end=self.cursor

        #  anounce the selected text
        if selecting and direction == "left":
            nvda_speak(self.input_text[0][self.selection_start:self.selection_end])

        # selecting to the right
        if selecting and direction== "right" and self.selection_start - self.selection_end == 0:
            self.right_selection=True
            self.left_selection=False
            
        if self.right_selection and selecting  and direction =="right":
            while self.cursor < len(self.input_text[0]) - 1 and self.input_text[0][self.cursor] == " ":
                self.cursor += 1  # Move right past spaces
            # Step 2: Move left until reaching the start of the current word
            while self.cursor > 0 and self.input_text[0][self.cursor - 1] != " ":
                self.cursor -= 1  # Move left to the beginning of the word
            # Update selection start only once
            if self.selection_end == None or self.selection_end == 0:
                self.selection_start = self.cursor

            # Step 3: Move right until the end of the word
            while self.cursor< len(self.input_text[0]) and self.input_text[0][self.cursor] != " ":
                self.cursor += 1  # Move99999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999990000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000 right until reaching a space or the end of the field
            if self.cursor < len(self.input_text[0]) and self.input_text[0][self.cursor] == " ":
                self.cursor += 1  # Stop at the first space after the word

            # Update selection end

            self.selection_end = self.cursor

        #  deselect words if words is selected to the left
        if self.left_selection and selecting and direction == "right":
            while self.cursor < len(self.input_text[0]) - 1 and self.input_text[0][self.cursor] == " ":
                self.cursor += 1  # Move right past spaces
            # Step 2: Move left until reaching the start of the current word
            while self.cursor > 0 and self.input_text[0][self.cursor - 1] != " ":
                self.cursor -= 1  # Move left to the beginning of the word
            # Step 3: Move right until the end of the word
            while self.cursor< len(self.input_text[0]) and self.input_text[0][self.cursor] != " ":
                self.cursor += 1  # Move right until reaching a space or the end of the field
            if self.cursor < len(self.input_text[0]) and self.input_text[0][self.cursor] == " ":
                self.cursor += 1  # Stop at the first space after the word

            # update selection start. 
            self.selection_start=self.cursor

        if selecting and direction =="right":
            nvda_speak(self.input_text[0][self.selection_start:self.selection_end])

    def delete_character(self, delete_action):
        if self.cursor >= len(self.input_text[0]) and self.cursor > 0 and not self.selecting:
            self.cursor -= 1

        """Deletes selected text or a single character at cursor position."""
        if self.edit and self.selecting:
            # Remove the selected text
            self.input_text[0] = (self.input_text[0][:self.selection_start] +
                                self.input_text[0][self.selection_end:])

            # Move cursor back to selection start position
            self.cursor = self.selection_start
        
            # Reset selection state
            self.selecting = False
            nvda_speak("Selected text deleted")
            return

        # Normal single-character deletion when no selection exists
        if self.edit and self.input_text[0] and delete_action == "delete_left":
            if self.cursor < len(self.input_text[0]):
                deleted_character = self.input_text[0][self.cursor]
                self.input_text[0] = (
                    self.input_text[0][:self.cursor] + self.input_text[0][self.cursor + 1:]
                )
        if self.edit and self.input_text[0] and self.cursor < len(self.input_text[0]) and delete_action == "delete_right":
            deleted_character = self.input_text[0][self.cursor]
            self.input_text[0] = (
                self.input_text[0][:self.cursor] + self.input_text[0][self.cursor + 1:]
            )

            nvda_speak(f"Deleted {'Space' if deleted_character == ' ' else deleted_character}")
            nvda_speak(f"{self.cursor}")
        self.update_input_text()

    def select_menu_item(self, key_pressed):
        """Handles selection when pressing Enter or Space."""
        if not self.edit:
            # Select menu item in main menu
            self.action = self.menu_items[self.selected_index]
            nvda_speak(f"{self.action} selected")
            if self.action == "QUIT":
                self.action="MAIN_MENU"
            self.excecute(self.action)

        elif self.edit and key_pressed == "enter":
            self.switch_tab()

    def switch_tab(self):
        """Handles tab switching."""
        if not self.tab_list:
            return

        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            self.selected_index = 0
            self.tab_index = (self.tab_index - 1) % len(self.tab_list)

        else:
            self.tab_index = (self.tab_index + 1) % len(self.tab_list)

        if self.edit:
            user_input = self.input_text[0].strip()
            self.input_data[self.selected_tab] = user_input
            nvda_speak(f"{self.selected_tab} saved: {user_input}")

        self.selected_tab = self.tab_list[self.tab_index]
        self.load_tab_data()


    def load_tab_data(self):
        
        self.tab_dict=None
        self.tab_menu=None

        if self.current_menu:
            self.tab_dict = self.menus.get(self.current_menu)
            if not self.tab_dict or "tabs" not in self.tab_dict:
                return  # Exit early if current menu doesn't use tabs
        if self.tab_dict and "tab_list" in self.tab_dict:
            self.tab_list = self.tab_dict["tab_list"]
            self.selected_tab = self.tab_list[self.tab_index]
            nvda_speak(f"{self.selected_tab}")
            nvda_speak(f"Found tab_list: {self.tab_list}")
        if self.selected_tab:
            self.tab_menu= self.tab_dict["tabs"].get(self.selected_tab)
        
        if self.tab_menu and "menu_itims" in self.tab_menu:  #  load the menu itims for the selected tab
            self.menu_items = self.tab_menu["menu_itims"]

        self.Lload_tabfunctions()  #   set verubales and determain actions based on context.
        self.load_edit_fields()  #  if self.edit load excisting data if any

    def load_edit_fields(self):
        if self.selected_tab in self.input_data :
            self.input_text = [self.input_data[self.selected_tab]]
            self.cursor = len(self.input_text[0])  # Optional: place cursor at end
            nvda_speak(f"{self.input_text}")
        else:
            self.input_text = [""]
            if self.input_text == [""]:
                self.cursor = 0
                if self.edit:
                    nvda_speak(f"No saved input for {self.selected_tab}")

    def Lload_tabfunctions(self):
        if self.tab_menu and "type" in self.tab_menu and self.tab_menu["type"] == "field":  
            self.edit=True

        if self.tab_menu and "type" in self.tab_menu and self.tab_menu["type"] == "action":  
            self.edit=False
            if self.selected_tab =="BACK":
                self.menu_items=["BACK"]

    def load_menus(self, menu_name):
        nvda_speak("menu loaded")
        pygame.time.delay(100)
        
        self.selected_index = 0
        self.tab_index=0
        self.menu_active=True
        self.tab_list=None
        self.current_menu=menu_name

        self.menu_items = self.menus.get(self.current_menu, [])

        self.load_tab_data()  #  load tabs if any

        if self.current_menu not in self.previous_menu :
            self.previous_menu.append(self.current_menu)

    def excecute(self, action):
        nvda_speak(F"{action}")
        """Executes actions based on menu context."""
        
        if action == "BACK" and self.menu_active:
            action=None
            self.edit=False
            if len(self.previous_menu) > 1:
                self.previous_menu.pop()  # Remove current menu
                self.current_menu = self.previous_menu[-1]  # Go back to previous
                nvda_speak(f"Returning to {self.current_menu}")
                self.load_menus(self.current_menu)
            else:
                nvda_speak("You can't do that!")

        if action  != None :
            self.current_menu=action
            self.load_menus(self.current_menu)



            

    def validate_email(self, email):
        nvda_speak("email validated")
        return True  # Just returns True for testing

    def validate_name(self, name):
        nvda_speak("name validated")
        return True  # Just returns True for testing