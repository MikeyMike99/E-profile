from NVDA import nvda_speak

class Box:

    def __init__(self, move_ref, world_ref, ):
        self.move_ref = move_ref
        self.world_ref = world_ref

        self.width = 4
        self.depth = 4
        self.height = 4
        self.count=0
        self.box_count = 0  
        self._count=0

    def get_chunk(self, lx, ly):
        chunk_size =  45
        chunk_x = lx // chunk_size
        chunk_y = ly // chunk_size
        chunk_key = (chunk_x, chunk_y)
        return chunk_key


    def normalize_facing(self, facing):
        if facing in [0, 360]:
            return 0
        elif 0 < facing < 90:
            return 45
        elif facing == 90:
            return 90
        elif 90 < facing < 180:
            return 135
        elif facing == 180:
            return 180
        elif 180 < facing < 270:
            return 225
        elif facing == 270:
            return 270
        elif 270 < facing < 360:
            return 315
        return 0

    def place_box(self, box_type=None):
        x = self.move_ref.lx
        y = self.move_ref.ly

        facing = self.normalize_facing(self.move_ref.facing)

        direction_offsets = {
            0:   (0, 1), 45:  (1, 1), 90:  (1, 0), 135: (1, -1),
            180: (0, -1), 225: (-1, -1), 270: (-1, 0), 315: (-1, 1)
        }

        dx, dy = direction_offsets[facing]
        w, d = self.width, self.depth
        if box_type != "": # not a hoe
            target_x = ((x + dx * 4) // 4) * 4
            target_y = ((y + dy * 4) // 4) * 4
            target_surface = self.world_ref.get_highest_surface(target_x, target_y, self.move_ref.tz)
            player_surface = self.world_ref.get_highest_surface(x, y, self.move_ref.tz)

        if box_type == "":
            target_x = ((x + dx * 4) // 4) 
            target_y = ((y + dy * 4) // 4) 
            target_surface = self.world_ref.get_highest_surface(target_x, target_y, self.move_ref.tz)
            player_surface = self.world_ref.get_highest_surface(x, y, self.move_ref.tz)
            nvda_speak(f"Player surface: {player_surface}, Target surface: {target_surface}")

            target_surface =target_surface - self.height
            nvda_speak(f"Digging a : {self.height} units deep")

        if target_surface > player_surface + 5:
            nvda_speak("Cannot place box — surface is too high.")
            return

        if player_surface - target_surface > self.height*2:
            nvda_speak("Cannot place box — surface is too low.")
            return

        lx = target_x
        rx = lx + self.width - 1
        ly = target_y
        ry = ly + self.depth - 1
        bz = (target_surface // 4) * 4
        tz = bz + self.height

        chunk_key=self.get_chunk(lx, ly)
        box_id = (int(f"{lx}{ly}"),)

        if box_type !="": # if not 
            coords_str = f"Box {box_id} placed at X {lx} to {rx}, Y {ly} to {ry}, Z {bz} to {tz}"
            self.world_ref.add_obj_to_chunk(chunk_key, box_id, (lx, rx, ly, ry, bz, tz), box_type)
            nvda_speak(coords_str)
            self.box_count += 2 #  Boxes holds even numbers
        else:
            _id = (int(f"{lx}{ly}"),)
            coords_str = f" dug: {_id} at X {lx} to {rx}, Y {ly} to {ry}, Z {bz} to {tz}"
            self.world_ref.add_obj_to_chunk(chunk_key, _id, (lx, rx, ly, ry, bz, tz), box_type)
            nvda_speak(coords_str)
            self._count +=1 # s is using uneven numbers

        nvda_speak(f"{self.world_ref}")
        nvda_speak(str(self.world_ref.world_objects))

        self.count += 1
