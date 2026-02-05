# editing
import pygame
from NVDA import nvda_speak

class World:

    def __init__(self):
        self.world_objects = {}
        self.boxes = {}
        self.dug_holes = {}  # key: (x, y), value: list of (bz, tz) tuples

        self.surfaces = {
            "ground": [(0, 99, 0, 99, 16, 28)],
            "gravel": [(0, 99, 0, 99, 0, 8)]
        }

        self.obj_counter = 0

    def __str__(self):
        return f"World with {len(self.world_objects)} objects, {len(self.boxes)} boxes, and {len(self.dug_holes)} holes"

    def add_world_objects(self, object_id, obj):
        self.world_objects[object_id] = obj

    def is_collision_at(self, x, y, bz, tz):
        def overlaps(coords):
            if not coords or len(coords) < 6:
                return False
            box_lx, box_rx, box_ly, box_ry, box_bz, box_tz = coords

            horizontal = box_lx <= x <= box_rx and box_ly <= y <= box_ry

            # ✅ Allow standing directly on top — don't block
                        # ❌ Block if player overlaps box body
            vertical = not (tz <= box_bz or bz >= box_tz)
            return horizontal and vertical
        for source in [self.boxes, self.world_objects]:
            for obj in source.values():
                if isinstance(obj, dict) and "box_cords" in obj:
                    for coords in obj["box_cords"].values():
                        try:
                            if overlaps(coords):
                                nvda_speak(f"Blocked by object at ({x}, {y})")
                                return True
                        except Exception as e:
                            nvda_speak(f"Collision error: {str(e)}")
                            continue
        return False

    def is_blocked(self, x, y, bz, tz, height=3):
        surface_z = self.get_highest_surface(x, y, bz)

        # Check for collisions
        if self.is_collision_at(x, y, bz, tz):
            surface_name = self.get_surface_name_at(x, y, bz)
            name = surface_name if surface_name else "unknown surface"
            nvda_speak(f"Blocked by {name} at ({x}, {y})")
            return True

        return False
    def get_highest_surface(self, x, y, current_z=None):
        surfaces = []
        for value in self.world_objects.values():
            if isinstance(value, dict) and "box_cords" in value:
                for coords in value["box_cords"].values():
                    if len(coords) < 6:
                        continue
                    lx, rx, ly, ry, bz, tz = coords
                    if lx <= x <= rx and ly <= y <= ry:
                        surfaces.append((bz, tz))

        for region_list in self.surfaces.values():
            for lx, rx, ly, ry, bz, tz in region_list:
                if lx <= x <= rx and ly <= y <= ry:
                    surfaces.append((bz, tz))

        surfaces.sort(key=lambda s: s[1], reverse=True)

        holes = []
        for hole_data in self.dug_holes.values():
            for coords in hole_data.get("box_cords", {}).values():
                lx, rx, ly, ry, hole_bz, hole_tz = coords
                if lx <= x <= rx and ly <= y <= ry:
                    holes.append((hole_bz, hole_tz))

        # Step 3: Subtract holes from surfaces
        for surface_bz, surface_tz in surfaces:
            remaining_segments = [(surface_bz, surface_tz)]

            for hole_bz, hole_tz in holes:
                new_segments = []
                for seg_bz, seg_tz in remaining_segments:
                    # No overlap
                    if hole_tz <= seg_bz or hole_bz >= seg_tz:
                        new_segments.append((seg_bz, seg_tz))
                    else:
                        # Clip out the hole area
                        if hole_bz > seg_bz:
                            new_segments.append((seg_bz, hole_bz))
                        if hole_tz < seg_tz:
                            new_segments.append((hole_tz, seg_tz))
                remaining_segments = new_segments

            # Step 4: Return top-most surface segment under current_z
            if remaining_segments:
                for seg_bz, seg_tz in sorted(remaining_segments, key=lambda s: s[1], reverse=True):
                    if current_z is None or seg_tz <= current_z:
                        return seg_tz

        return -100

    def get_surface_name_at(self, x, y, z):
        for key, value in self.world_objects.items():
            if isinstance(value, dict) and "box_cords" in value:
                for coords in value["box_cords"].values():
                    if len(coords) >= 6:
                        lx, rx, ly, ry, bz, tz = coords
                        if lx <= x <= rx and ly <= y <= ry and bz <= z <= tz:
                            return key

        for name, regions in self.surfaces.items():
            for lx, rx, ly, ry, bz, tz in regions:
                if lx <= x <= rx and ly <= y <= ry and bz <= z <= tz:
                    return name
        return None

    def remove_full_box(self, x, y, z):
        for box_id, box in list(self.boxes.items()):
            for coords in box.get("box_cords", {}).values():
                if not coords or len(coords) < 6:
                    continue

                box_lx, box_rx, box_ly, box_ry, box_bz, box_tz = coords

                if (
                    box_lx <= x <= box_rx and
                    box_ly <= y <= box_ry and
                    box_bz <= z <= box_tz and
                    (box_rx - box_lx + 1) == 4 and
                    (box_ry - box_ly + 1) == 4 and
                    (box_tz - box_bz) == 4
                ):
                    del self.boxes[box_id]
                    if box_id in self.world_objects:
                        del self.world_objects[box_id]
                    nvda_speak(f"Full box removed at {x}, {y}, Z {z}")
                    return True
        return False
