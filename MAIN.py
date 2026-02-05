import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"

import pygame
import socketio
import multiprocessing
import time
import sys
from validate_menu_config import validate_menu_config
from MENU_CLASS import Menu
from class_box import Box
from class_world import World
from logger import LOGG
from NVDA import nvda_speak
from class_move import Move

# Ensure Windows uses "spawn" for multiprocessing
multiprocessing.set_start_method("spawn", force=True)

# Background Socket.IO Client Process
def run_socket_client(queue, stop_event):
    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.event
    def connect():
        LOGG("Connected to the server.")
        nvda_speak("connected to the server.")

    @sio.event
    def disconnect():
        LOGG("Disconnected from the server.")

    @sio.on("response")
    def on_response(data):
        LOGG(f"Response from server: {data}")
        nvda_speak(f"{data}")

    try:
        server_url = "http://localhost:12345"  # Change to your server URL
        sio.connect(server_url)
        LOGG("Connected successfully.")
    except Exception as e:
        LOGG(f"Failed to connect: {e}")
        nvda_speak("Failed to connect to the server!")
        return

    while not stop_event.is_set():  # Check for termination flag
        try:
            if not queue.empty():
                command = queue.get_nowait()
                LOGG(f"Sending command: {command}")
                sio.emit("message", {"action": command})
        except EOFError:
            LOGG("Queue closed unexpectedly.")
            break
        time.sleep(0.1)  # Prevent high CPU usage

    sio.disconnect()

# Pygame main window
def intro_screen(queue, stop_event):
    pygame.init()  # Initialize Pygame
    pygame.time.delay(1000)
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("ECHOES_OF_THE_WORLD")
    BLACK = (0, 0, 0)
    pygame.scrap.init()
    pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)
    pygame.time.delay(1200)
    menu=Menu()
    menu.load_menus("MAIN_MENU")

    validate_menu_config(menu, nvda_speak)
    skip = None
    world=World()
    position = Move(0, 1, 0, 1, 3, 0, 0, world)#  lx, rx, ly, ry, bz, tz, facing
    box_position=Box(position, world)
    world.world_objects["player"] = position

    probe_world=None
    G_pressed=False
    intro_active = True
    active=True
    clock = pygame.time.Clock()
    elapsed_time = 0
    position.apply_gravity()
    
    while active:
        screen.fill(BLACK)
        elapsed_time += clock.tick(30)
        if elapsed_time > 2000 and skip is None:
            skip = True
            LOGG("Player can now press Enter to skip. the intro!")
            nvda_speak("Press Enter to skip the intro.")
        events = pygame.event.get()
        for event in events:
            if hasattr(menu, "action") and menu.action == "EXIT":
                nvda_speak("Game is closing.")
                LOGG("Exit action triggered by menu.")
                time.sleep(0.5)
                stop_event.set()
                pygame.time.delay(500)
                pygame.quit()
                sys.exit()  # Ensure complete termination

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and not menu.menu_active:
                menu.menu_active=True
                menu.current_menu="QUIT"
                menu.load_tab_data()

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_b and not menu.menu_active:
                box_position.place_box("small")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and not menu.menu_active:
                box_position.place_box("hole")
               
            
            elif event.type == pygame.KEYDOWN and menu.menu_active and not intro_active:
                menu.handle_key_press(event)

            elif event.type == pygame.KEYDOWN and elapsed_time > 2000 and intro_active:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    LOGG("Player pressed Enter to skip the intro.")
                    nvda_speak("Skipping the intro.")
                    intro_active = False

        if elapsed_time >= 3300 and intro_active:
            LOGG("Automatically transitioning to the main menu.")
            nvda_speak("Intro finished. Transitioning to the main menu.")
            intro_active = False

        if not menu.menu_active:
            #position.apply_gravity()

            keys = pygame.key.get_pressed()
            probe_mode = keys[pygame.K_g]
            if probe_mode and not G_pressed:
                probe_world= Move(
                position.lx,
                position.rx,
                position.ly,
                position.ry,
                position.bz,
                position.tz,
                position.facing,
                position.world,
                probe_active=True)
                G_pressed = probe_mode


            if keys[pygame.K_UP]:
                if probe_mode:
                    nvda_speak(f"{probe_world}")
                    probe_world.move_forward()
                else:
                    position.move_forward()
                    G_pressed=False

            elif keys[pygame.K_DOWN]:
                position.move_backward()

            elif keys[pygame.K_RIGHT]:
                position.move_right()

            if keys[pygame.K_LEFT]:
                position.move_left()



            if keys[pygame.K_a]:
                position.FACING("left")
            if keys[pygame.K_d]:
                position.FACING("right")
            if keys[pygame.K_w]:
                position.FACING(180)
            if keys[pygame.K_s]:
                position.FACING(180)
            if keys[pygame.K_LSHIFT]:
                position.jump_Thread()
            if keys[pygame.K_x]:
                nvda_speak(f"{position}")
                
                pygame.time.delay(100)
        

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Required for Windows `.exe` packaging

    command_queue = multiprocessing.Queue()
    stop_event = multiprocessing.Event()  # Create a shared stop event

    # Start the Socket.IO client as a separate process
    client_process = multiprocessing.Process(target=run_socket_client, args=(command_queue, stop_event))
    client_process.start()

    # Run the Pygame window
    intro_screen(command_queue, stop_event)

    # After Pygame window closes, terminate the client process
    client_process.terminate()
    client_process.join()

    exit()  # Ensure the script exits after everything is done
