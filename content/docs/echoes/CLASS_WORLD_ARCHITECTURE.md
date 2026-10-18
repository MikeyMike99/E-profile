[//]: # (DOC_ID: ECHO-DEV-CLASS_WORLD_ARCHIT | VERSION: v1.3 | SCOPE: DEV)

# Echoes of the World: Class & World Architecture

The World class is responsible for managing players, objects, surface zones, and chunk coordinates across the audio world grid. It dynamically manages player movement between spatial chunks while pruning stale entities from prior zones to preserve audio spatial accuracy.
I also implemented a chunking system and a data frame that will store the player’s current chunk for faster lookups, reducing long for loops to simple .get() calls.
1. The objects and players are all stored in a specific way. Players, objects, and surfaces are stored in nested dictionaries. We have 1.1. 1.1. identifiers, which are the first key in the dictionary. The first key is the chunk_key, which indicates the chunk of the layer or object. 
1.2 The second key is (chunk_x, chunk_y, z, identifier), stored as a tuple.

The identifiers are as follows: 
dug_Holes = -1
ground = 0\
ground Blocks = 1
1.3. The value stored for each object is (lx, rx, ly, ry, bz, tz). allso stored as Tupples

2. We have the following attributes in the clas:

self.world_obj={}# This is kjust a sorting dictionary to make lookups and queries easier later on
        self.Characters= {}# stores all the players
        self.boxes={}# stores all the boxes
        self.ground_blocks= {}{# stores all the ground blocks
        self.dug_holes {}# stores all the voids/ pits/holes, what ever you may call it.
        self.surfaces={}#stores all surface types
        # all objects
        self.world_dict = {# just a refrence dictionary to make lookups easier and is used to build the data_frame
    "Characters": self.Characters,
    "ground_blocks": self.ground_blocks,
    "boxes": self.boxes,
    "dug_holes": self.dug_holes,
    "surfaces": self.surfaces
}
        # query scope
        #check if the chunk has changed
        self.same_chunk=True# keeps track if the chunk has changed, usefull when lookin gfor data in difrent chunks

3. We have the str method, that converts data in radable text usefull for debugging.

    def __str__(self):
        total_charactrs= sum(len(chunk) for chunk in self.Characters.values())
        total_boxes = sum(len(chunk) for chunk in self.boxes.values())
        total_holes = sum(len(chunk) for chunk in self.dug_holes.values())
        return f"World with {total_charactrs} Players at {self.Characters}, {total_boxes} boxes, and {total_holes} holes"
4. This will add the character to the world:
    def add_obj_to_chunk(self,chunk,  ID=None, cords=None, type=None, debth=None):
        if cords is not  None :
            lx, rx, ly, ry, bz, tz=cords
        else:
            screenreader_speak("The cords you provided is not valid")
            return
        chunk_key=self.get_chunk_key(lx, ly, bz)

        if type == "player":
            if chunk != chunk_key:
                self.same_chunk=False
                if chunk in self.Characters:
                    self.Characters[chunk].pop(ID, None)  
            if chunk_key not in self.Characters:
                self.Characters[chunk_key] = {}
            self.Characters[chunk_key][ID] = (cords)
            if self.same_chunk ==False:
                data_frame=self.build_data_frame(lx, ly, bz)
                self.same_chunk=True
                return data_frame


3. How `add_obj_to_chunk` Places a Player Into the World
This method updates which chunk the player belongs to and stores the player’s current bounding-box coordinates in the `Characters` dictionary. It is used for movement, collision, and loading chunk-based world data.
3.1 Required Inputs

The following inputs must be valid for the method to add the player correctly.

3.1.1 `cords` (6-value tuple)
The method only continues if `cords` is valid.
It must contain the following six values in order:
(lx, rx, ly, ry, bz, tz)
lx = left X
rx = right X
ly = left Y
ry = right Y
bz = bottom Z
tz = top Z
If `cords` is `None`, the method stops immediately.

3.1.2 `ID`
A unique identifier for the player.
Used as the key inside the chunk.
3.1.3 `type`
Must be `"player"` for this logic to run.
3.1.4 A valid chunk key
`get_chunk_key(lx, ly, bz)` must return the correct chunk this player belongs to.
3.2 How the Player Is Stored Internally
The `Characters` dictionary is structured like this:
Characters = {
    chunk_key: {
        ID: (lx, rx, ly, ry, bz, tz)}}
Example:
Characters[(0,0,0)] = {
    "player_1": (12, 14, 8, 10, -2, 0)}
3.3 What the Method Does
3.3.1 Determine the correct chunk

The chunk is calculated using the bounding box:
chunk_key = get_chunk_key(lx, ly, bz)
3.3.2 Check if the player changed chunks
If the input `chunk` does not match the newly calculated `chunk_key`, the player has moved to a new chunk.
The method will remove the player from the old chunk and mark that a chunk update is needed.
3.3.3 Create the new chunk entry if missing
If `chunk_key` does not yet exist inside `Characters`, it is created as an empty dictionary.
3.3.4 Add or update the player

The player is stored using their `ID` as the key and their bounding box as the value:

Characters[chunk_key][ID] = cords
3.3.5 Rebuild world data when chunk changes

If the player moved to a different chunk, the method calls:

build_data_frame(lx, ly, bz)
This refreshes surfaces, holes, and collision data for the new chunk.

3.4 Debugging: Reasons a Player May Not Be Added
3.4.1 `cords` does not contain six values

Any missing or extra value will cause the method to skip storing the player.

3.4.2 `ID` is `Non

Without a valid ID, the player cannot be stored.

3.4.3 `type` is not `"player"`
The entire block of logic is skipped.
3.4.4 `get_chunk_key` returns the wrong chunk
Incorrect chunk calculations will place the player in an unexpected location.
3.4.5 The old chunk does not exist

If the method tries to remove the player from a non-existent chunk, the removal silently fails.
3.4.6 `Characters` was changed or cleared elsewhere
If the dictionary is overwritten or reset, the player will not appear.
3.5 Debugging Checks to Print or Log

3.5.1 Print the incoming `cords`
Confirms the values and their order.
3.5.2 Print the calculated `chunk_key`

Shows where the system thinks the player should be.

3.5.3 Print the incoming `chunk` (old chunk)

Helps confirm whether the player is actually changing chunks.
3.5.4 Print when removal happens
Useful when the player moves between chunks.
3.5.5 Print when a new chunk dictionary is created
Confirms that the system is building chunk entries dynamically.
3.5.6 Print the final state of `Characters[chunk_key]`
Confirms whether the player was successfully added to the world.


[//]: # (SECTION_ID: ECHO-DEV-CLASS_WORLD_ARCHIT-SEC-1)
## Cross-References & System Parallels
[//]: # (SECTION_ID: ECHO-CORE-WORLD-SEC-1)

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels: Spatial Coordinates & Audio Drivers (Click to Expand Dropdown)</summary>

| Related Project / Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **The Developer's Manifesto** | [Chapter 1: Echoes in the Void (The True Origin)](/docs/manifesto/01_Echoes_in_the_Void) — First-person audio movement engine, `(x, y, z)` grid, four-corner bounding box rotation, and chunk boundary design. | The Manifesto |
| **Origin Architecture Blueprint** | [04_26 The Origin Architecture: Echoes of the World](/docs/devlog/04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD) — Genesis architectural decisions, state isolation, and rejecting terminal speech silence. | Devlog Suite |
| **JOSHY Audio Suite** | [Guide 00A: Beginner Guide to Screen Readers](/docs/audio_suite/00A_BEGINNER_GUIDE_TO_SCREENREADERS_AND_ACCESSIBILITY) — Universal screen reader detection, `accessible_output2`, and `nvdaControllerClient64.dll` integration. | JOSHY Audio Suite |
| **E-Profile Portfolio Portal** | [E-Profile Devlog: Chapter 5](/docs/eprofile/DEVLOG#chapter-5-screen-reader-accessibility-as-an-operational-physical-access-point-secops--wcag-synergy) — Accessibility as the physical operational access point and non-visual feedback design. | E-Profile Devlog |
| **Siraugga Developer Manifesto** | [Chapter 4: The Forge of Sovereignty](/docs/manifesto/DEVELOPERS_MANIFESTO#chapter-4-the-forge-of-sovereignty) — The origin of Echoes of the World, spatial audio gaming for the blind, and building without visual crutches. | The Manifesto |
</details>
