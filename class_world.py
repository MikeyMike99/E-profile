import pygame
import numpy as np
from NVDA import nvda_speak

class World:

    def __init__(self):
        self.world_objects = {}
        self.boxes = {
            (0, 0): {  # chunk range (0,45)
                "box1": np.array([0, 4, 0, 4, 0, 4])
            },
            (0, 1): {  # chunk range (45,90)
                "box2": np.array([50, 54, 5, 9, 0, 12])
            }
        }

        self.dug_holes = {}

        self.surfaces = {
            "ground": [(0, 99, 0, 99, -8, 0)],
            "gravel": [(0, 99, 0, 99, -28, -20)]
        }

        self.obj_counter = 0

    def __str__(self):
        total_boxes = sum(len(chunk) for chunk in self.boxes.values())
        total_holes = sum(len(chunk) for chunk in self.dug_holes.values())
        total_objects = len(self.world_objects)
        return f"World with {total_objects} objects, {total_boxes} boxes, and {total_holes} holes"

    def add_obj_to_chunk(self, chunk_key, item_ID, box_cords, box_type=None):
        """
        Adds an object to a chunk. Determines if it's a box or hole based on box_type.
        item_ID is passed in as (lxly,)
        """
        if box_type is None:
            nvda_speak("no box type was provided")
            return

        if box_type == "small":
            target_dict = self.boxes
            type_val = 0   # box identifier
            obj_type = "box"
        elif box_type == "hole":
            target_dict = self.dug_holes
            type_val = -1  # hole identifier
            obj_type = "hole"
        else:
            nvda_speak(f"unknown box_type {box_type}, defaulting to box")
            target_dict = self.boxes
        # Expand ID: (84,) → (84, 0) or (84, -1)
            type_val = 0
            obj_type = "box"

        item_ID = (item_ID[0], type_val)

        if chunk_key not in target_dict:
            target_dict[chunk_key] = {}

        if item_ID in target_dict[chunk_key]:
            nvda_speak(f"{obj_type} {item_ID} already exists in chunk {chunk_key}. skipping.")
            return

        target_dict[chunk_key][item_ID] = np.array(box_cords)
        nvda_speak(f"{obj_type} {item_ID} added to chunk {chunk_key}.")

    def is_blocked(self, x, y, bz, tz, height=3):
        nvda_speak(f"checking blocking at x={x}, y={y}, bz={bz}, tz={tz}, height={height}")
        return False

    def get_highest_surface(self, x, y, current_z=None):
        nvda_speak("getting the highest surface")
        return 28

    def get_surface_name_at(self, x, y, z):
        nvda_speak("checking the surface name")
        return "unknown"

    def remove_full_box(self, x, y, z):
        nvda_speak(f"removing box at x={x}, y={y}, z={z}")
        return False
