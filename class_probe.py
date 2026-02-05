from NVDA import nvda_speak

class FocusProbe:
    def __init__(self, move, world, max_distance=12):
        self.move = move
        self.world = world
        self.max_distance = max_distance
        self.focus_position = None        # Final (x, y, z) location
        self.focus_object = None          # Object key from world_objects
        self.placement_orientation = "horizontal"  # Can be "horizontal" or "vertical"

