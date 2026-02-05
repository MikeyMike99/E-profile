import pygame
import threading
import time
from NVDA import nvda_speak

class Move:

    def __init__(self, lx, rx, ly, ry, bz, tz, direction, world, probe_active=False):
        self.lx = lx
        self.rx = rx
        self.ly = ly
        self.ry = ry
        self.bz = bz
        self.tz = tz 
        self.facing = direction
        self.boundry = 100
        self.world = world
        self.chunk_size= 45
        self.walking_speed = 1
        self.player_height = 2
        self.jumping = False
        self.probe_active = probe_active
        self.directions = {
            "NORTH": 0, "NORTH EAST": 45, "EAST": 90, "SOUTH EAST": 135,
            "SOUTH": 180, "SOUTH WEST": 225, "WEST": 270, "NORTH WEST": 315
        }

    def __str__(self):
        return f"position({self.lx}, {self.rx}, {self.ly}, {self.ry}, {self.bz} , {self.tz}), {self.facing}"

    def speed(self):
        time_ticks = pygame.time.get_ticks()
        running = True
        while running:
            ticks = pygame.time.get_ticks() - time_ticks
            if self.walking_speed == 1 and ticks > 200:
                running = False
            if self.walking_speed == 2 and ticks > 600:
                running = False
            if self.walking_speed == 3 and ticks > 1500:
                running = False
            if self.walking_speed == 4 and ticks > 2000:
                running = False

    def FACING(self, direction):
        self.speed()
        if direction == "right":
            self.facing += 45
        elif direction == "left":
            self.facing -= 45
        elif direction == 180:
            self.facing = (self.facing + 180) % 360
        self.facing = (self.facing + 360) % 360
        for key, value in self.directions.items():
            if value == self.facing:
                nvda_speak(f"{key}")

    def apply_gravity(self):
        surface_z = -100
        if self.jumping:
            pygame.time.delay(400)
           
            return
        for x in range(self.lx, self.rx + 1):
            for y in range(self.ly, self.ry + 1):
                tile_surface = self.world.get_highest_surface(x, y, self.bz)
                if tile_surface > surface_z:
                    surface_z = tile_surface

        if self.bz > surface_z:
            self.bz -= 1
            self.tz = self.bz + self.player_height
            nvda_speak(f"Falling to {self.bz}")

    def get_offset(self, direction):
        offsets = {
            "forward": {
                0: (0, 1), 45: (1, 1), 90: (1, 0), 135: (1, -1),
                180: (0, -1), 225: (-1, -1), 270: (-1, 0), 315: (-1, 1)
            },
            "backward": {
                0: (0, -1), 45: (-1, -1), 90: (-1, 0), 135: (-1, 1),
                180: (0, 1), 225: (1, 1), 270: (1, 0), 315: (1, -1)
            },
            "left": {
                0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)
            },
            "right": {
                0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)
            }
        }
        return offsets.get(direction, {}).get(self.facing, (0, 0))

    def attempt_move(self, dx, dy):
        new_lx = self.lx + dx
        new_rx = self.rx + dx
        new_ly = self.ly + dy
        new_ry = self.ry + dy

        if 0 <= new_lx <= self.boundry and 0 <= new_rx <= self.boundry and \
           0 <= new_ly <= self.boundry and 0 <= new_ry <= self.boundry:
            if not self.jumping:
                surface_z = self.world.get_highest_surface(new_lx+1, new_ly+1, self.bz+5)
                nvda_speak(f"next solid surface at: {surface_z}")
                step_up = surface_z - self.bz

                if 0 < step_up <= 4:
                    self.bz = surface_z
                    self.tz = self.bz + self.player_height
                    nvda_speak(f"Stepped up to {self.bz}")

                # Now check blockage with updated height
                for x in range(new_lx, new_rx + 1):
                    for y in range(new_ly, new_ry + 1):
                        if self.world.is_blocked(x, y, self.bz, self.tz) and not self.probe_active:
                            nvda_speak("the world says it is blocked!")
                            return

                self.lx = new_lx
                self.rx = new_rx
                self.ly = new_ly
                self.ry = new_ry
                nvda_speak(f"LX {self.lx}, LY {self.ly}")
                #  Identify the chunk the player is currently in
                chunk_x = self.lx// self.chunk_size
                chunk_y = self.ly // self.chunk_size
                chunk_key = (chunk_x, chunk_y)
                nvda_speak(f"you ar in chunk : {chunk_key }")


            else:
                self.lx = new_lx
                self.rx = new_rx
                self.ly = new_ly
                self.ry = new_ry
                surface_z = self.world.get_highest_surface(new_lx, new_ly, self.bz)
                self.bz = surface_z
                self.tz = self.bz + self.player_height
                
    def move_forward(self):
        self.speed()
        dx, dy = self.get_offset("forward")
        self.attempt_move(dx, dy)

    def move_backward(self):
        self.speed()
        dx, dy = self.get_offset("backward")
        self.attempt_move(dx, dy)

    def move_left(self):
        self.speed()
        dx, dy = self.get_offset("left")
        self.attempt_move(dx, dy)

    def move_right(self):
        self.speed()
        dx, dy = self.get_offset("right")
        self.attempt_move(dx, dy)

    def jump_Thread(self):
        if not self.jumping:
            self.jumping = True
            threading.Thread(target=self.jump_logic).start()

    def jump_logic(self):
        nvda_speak("Jump started")
        time_ticks = pygame.time.get_ticks()
        level = 0
        jump_peak = self.bz + 8
        while self.jumping:
            ticks = pygame.time.get_ticks() - time_ticks

            if ticks > 500 and level == 0:
                ground_z = self.world.get_highest_surface(self.lx, self.ly, jump_peak)
                nvda_speak(f"At jump peak {jump_peak}, terrain surface is {ground_z}")

                self.bz = jump_peak              # Elevate bottom Z
                self.tz = self.bz + 2            # Update top Z based on height
                nvda_speak(f"Jumping to {self.bz}")
                time_ticks = pygame.time.get_ticks()
                level += 1

            elif ticks > 300 and level == 1:
                surface_z = self.world.get_highest_surface(self.lx, self.ly, self.bz)

                if self.bz > surface_z:
                    self.bz -= 1
                    self.tz = self.bz + 2
                    nvda_speak(f"{self.bz}")
                    time_ticks = pygame.time.get_ticks()
                else:
                    nvda_speak(f"Landed at {self.bz}")
                    self.jumping = False
