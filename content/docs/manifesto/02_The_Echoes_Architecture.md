[//]: # (DOC_ID: ECHO-MAN-02_THE_ECHOES_ARCH | VERSION: v1.4 | SCOPE: MAN)

# Chapter 2: The Echoes Architecture (Building the Engine From Bare Metal)

> [!NOTE]
> **Documentation Scope & Status: Incomplete Architectural Snapshot**  
> The game engine architecture for *Echoes of the World* remains an active, evolving, and incomplete project. The specifications described here reflect foundational milestones and architectural patterns rather than an exhaustive, finalized production manual.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-1)
## 1. Breaking the Flat Void: 3D Bounding Boxes, Room Physics, and Collision Detection

I was stuck on pure `x, y, z` coordinates, and I quickly hit the absolute limit of that math. The breaking point came when I tried to actually manipulate the world—when I tried to dig a hole and place a physical box. You can't stand on a box if you don't know how big it is. You can't fall into a hole if you only exist as a single geometric point. An `x, y, z` coordinate has no mass and no volume. If this was going to be a real universe, I needed physics. I needed walls that actually stopped you and floors that caught you. To make that happen, I had to completely abandon the simple grid and dig into full bounding box architecture and collision detection—a mechanical beast entirely on its own.

If you read the blogs, you would know shortly after I decided to start building a game, I hit a turning point in my personal life. I turned back to Optima College. Time was limited to actually work on the game and learn Python so I did what I could, explored what I could when I had the time. I was shaping the bounding box the player was occupying. It was a big challenge because when the player is turning all four corners should turn with it. I literally walked up and down in my room to get the math straight and to actually understand what is happening in what I am building. I walked into the wall then turned partially, then tried to walk and see if I can walk while touching the wall with my shoulder at an angle facing the wall still. I was trying to get the math working to do what I want it to do. I set a boundary as the wall and tried that the player's bounding box coords could update without crossing the border and that the player will not lose parts of itself while moving and turning. Once I mastered this I declared victory. But that was not enough, I had to define how am I going to set up objects in the world. I settled on the Minecraft layout, the whole world should be divided into blocks. So I hard coded a box coords into the system. I then tried to locate it and tested all sides to see if the player will respect the box boundaries. It was a disaster, I could not understand how can I define a boundary at the outer layer of the void. But I cannot seem to detect the box. Either I get the box but I cannot seem to bump or get limited by it. Or I would just go through it or detect it but did not get blocked by it. This is one of the harder and longer parts which I experimented with. Remember the player can jump so I needed a way for the player to be able to jump onto the box and respect that the bounding box has a top layer which is actually solid. My movement system was working I could bump into the box but not yet jump on it, I had to think of something. When I jump the player is unable to move forward during a jump. The player will simply jump up and fall down in place. I had to restructure and rebuild my gravity function. To solve the jumping in one place problem I tried multiple things but I settled on using threads. When the player jumps it will invoke a jumping function, that function will invoke a thread and return and the player could gently go down and hit the intended surface. I had to hard code everything because I just wanted to see it work one box one player, when I could finally land on the box I decided I do not want a hard coded box I want to manually place and remove the box if I want to. That is how I decided to remove some of the hard coded constraints, but it brought so many more problems. The box placement would not respect the world and each other, I was fighting just to get the box on the ground so that the collision system could detect it. At this point the collision system was broken before it was hard coded but now it is dynamic. I had to think and rebuild. Finally when I rebuilt the system again from scratch using some of the logic I already struggled fixing, I could place and remove a box. The next thing I wanted to do is dig a hole. To dig a hole it should simply place a box in the surface below the player's feet. But I could not seem to get the logic right to actually drop into the hole. Just had to find a way so that the top layer and the surface should be ignored and the bottom part of the box is the hole's bottom. When I finally mastered that the inner boundaries, the hole's walls, was not respected, I was walking in solid space, this was a big no no. So my collision system was broken again. I had to rebuild and test it again and again and again. I fix one thing the other breaks. I could not understand, the box is behaving fine, the hole is basically an inverted box. With the world's boundaries as I defined firstly it is just shrunk down and the surface level has dropped. Simple as that you think. That is not as simple. I spent hours and days fighting the code and the collision system, when I fixed one thing the gravity will break or I will be walking in forbidden space. Or I was falling into a never ending void locking my CPU up with an uncapped thread. Restarting my whole PC with broken code forgetting what I was busy with. Fighting ChatGPT to declare victory. It was a never ending rabbit hole. Once it stabilised I thought I won.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-2)
## 2. Distributed Experiments: Flask, WebSockets, and Cloud Hosting

I was mistaken, there was so much more to do. I was a bit done with holes and boxes for now, so I started to play with Flask and WebSockets to try to understand how to make two different scripts talk to each other that sit on two different machines or two different parts of the world.

I learned during this stage that I cannot host on my own machine. I would be exposing my IP address to the internet. You all know that is not a very smart thing to do. So my new search for a solution started. I explored hosting platforms like Replit and many more. I learned that games will need WebSockets for a persistent connection between the client and server. I could not find one that was actually built with accessibility in mind. I then settled with a WSGI server on PythonAnywhere, as that was the best and most accessible way to host. I still had no clue how it worked. I just experimented and was amazed when I actually got it set up and my machine could talk to a server in the cloud.

So I played around with how to keep the server alive with a ping/pong. I also measured the packets and what was received and what was sent. I quickly silenced that to run in the background. I was also trying to measure how fast the responses were from the server. I realized it is instant, but then the question came: what if 100 players fired off "move forward" all at once? This is how I learned about race conditions, and that I need to have a queue to capture all incoming requests. This is why the server should be running at world-record speeds so that the last person should not be waiting for a response from the server. I had not found the correct solution at this point for it yet. I was still exploring and just learning how these things work. I was not really looking for a solution yet. The game was only a tiny script with no real logic behind it. The only thing that mattered was that it worked; I can always come back to it.

Once I was done experimenting with Flask and WebSockets, I had a basic idea of how to connect clients to a server and maintain a persistent state across the game. I had a starting point, but my knowledge was still limited.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-3)
## 3. World Architecture: Layering, Nested Chunk Dictionaries, and Highest Surface Detection

I turned back to the actual game. Digging a hole and placing a box was not enough—I needed to be able to remove placed boxes, as well as stack holes and boxes. My hole system broke again, and I had to rebuild everything just to get stacking to work. Once that stabilized, I thought: wait, Minecraft has different layers in the world. I have to layer my world as well. I needed an overworld, an underworld, and other layers in between.

This became the most challenging part. I started defining the surfaces, but guess what? It broke again. I spent hours figuring out how a hole bottom and a new surface would be detected once you dug through a layer, ensuring the player landed on the surface below rather than getting snagged on the hole's boundary walls. That happened constantly: I would dig down, drop to the second surface, but get blocked by the hole's collision boundaries. I had to completely rebuild my gravity system to accurately detect the highest surface directly beneath the player's feet.

Then I realized that loading every block individually would be extremely memory-intensive. I had two options: merge adjacent blocks into single entities and use clipping when digging, or implement chunks. I learned that I could use a nested dictionary to chunk objects, so I experimented with that for a while, limiting rendering to a radius around the player. Soon, I noticed that if I dug a hole that crossed a chunk boundary, the player would fall straight into oblivion. That was obviously not ideal. At the same time, I needed to keep memory usage minimal, meaning I couldn't just dump dozens of massive chunks into the buffer. I wanted an open world where the player could explore seamlessly without running into artificial limits. The solution was to make the chunks smaller, allowing me to load more of them into the buffer while keeping memory consumption low.

To be honest, I only finalized the method for calculating the highest surface toward the end of 2025. I tested several approaches to balance execution speed and precision, tying it directly into the chunking logic so the player could walk, jump, dig, and stack without noticeable glitches or stuttering chunk loads. The player never sees the heavy lifting happening in the background.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-4)
## 4. Custom Audio Pipeline: Screen-Reader Conflict Avoidance and Sound Engineering

Next, it was time to source sound effects for the game. I downloaded a massive collection of audio files and started listening to them one by one. I quickly realized this would take forever—using standard tools like Windows Media Player or VLC kept interrupting and silencing my screen reader. It was completely inefficient for previewing raw audio.

So, I built my own lightweight audio player. I created a sounds directory, organized all my subfolders and audio files there, and used a Python dictionary to load the files in chunks. With this tool, I could skip back and forth between tracks instantly, without screen reader conflicts. I could play or pause at will, and whenever I needed to check a track's name, I simply pressed Tab to have it read aloud. I even mapped F12 to copy the last spoken filename to the clipboard so I could instantly locate it in File Explorer for sorting or editing.

There was just one problem: I didn't have dedicated software to edit audio yet. After some searching, I discovered REAPER. With some initial setup and key adjustments, I was able to handle basic editing. I don't consider myself a professional sound engineer—I just go by ear. I layer effects together, pan them across the stereo field, adjust individual volume levels, and align their timing. Basic stuff, as I said.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-5)
## 5. Security & State Locking: The Hein Wagner Academy Slot Machine

As mentioned in previous posts, my path shifted again around this time. I walked away from the call centre course at Optima and threw myself into marketing at the Hein Wagner Academy. The end goal was always cybersecurity, but while I was there, I needed something to keep my hands in the code. I started messing with Flask again and decided to build a digital slot machine.

I ripped into the old menu system I'd built earlier. I hardwired some new logic to shoot emails directly from the client's device, or bounce them from the server straight to the client using my own address. I already knew how to siphon player data from my earlier experiments, but this time I locked it down tight—harder input validation, actual security. I wasn't just playing around anymore.

My original plan was to drop this thing live and let the students at the college lose their minds on it. But after digging into the legal side, I realized I'd need gambling and software licenses to make a single cent off it legally. Red tape everywhere. I didn't care. I kept building it anyway just to see if I could pull it off. It kept me sane between classes for a few solid weeks.

Building that slot machine forced me to actually understand loops and dictionaries. I figured out how to rig the gameplay with countdown timers so it wasn't a total cakewalk. I capped how often someone could hit a jackpot, but kept the dopamine hit just within reach so winning never felt impossible. To keep players hooked and avoid obvious patterns, I threw out all the hardcoded trash and randomized the payouts within strict mathematical ranges.

The bones of it were dead simple: a client-server Flask setup with state locked on the server so nobody could tamper with the client and cheat the system. You could grind for extra spins or burn through them completely. For a hot minute, I seriously considered fighting the system and turning it into a commercial product, but the legal nightmare shut that down real quick. Now it's just sitting on my hard drive gathering dust. But nothing is wasted. Once the core engine of the main game is done, I'll rip those mechanics out and repurpose them for minigames, loot boxes, or random prize drops.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-6)
## 6. Menu Dynamic Generation & AST Meta-Programming

Even with those updates, I wasn't satisfied with the menu system—it relied far too heavily on hardcoded values. Over the next few weeks, I rebuilt it from the ground up to be modular, dynamic, and easy to extend. At the same time, I spent substantial effort refining the collision and gravity mechanics.

As menus expanded, hardcoding every single menu option into sprawling `if/elif` ladders was unmanageable. If I wanted to add a new inventory category or setting, I had to manually wedge dozens of lines into the loop. In an experimental directory called `TEST`, I forced myself to learn Object-Oriented Programming (OOP) and meta-programming. I dug into Python's Abstract Syntax Tree (`ast`) module to write core generator scripts that could inspect, parse, and dynamically assemble Python code on the fly. That AST-driven menu experiment taught me how Python evaluates code under the hood—muscles that would later power the Raugus Map and the Zero-Downtime Hot-Patching compiler for Siraugga.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-7)
## 7. Authoritative Server Engine, Gravity Optimization, and Entity Synchronization

By mid-2025, the menu and collision systems were both stable, but gravity was still giving me headaches. I tested different gravity implementations using Pandas and NumPy, but they introduced too much overhead for real-time tick rates. I found that Python's built-in dictionary lookups and .get() calls were the fastest approach, though nesting them carelessly inside heavy loops quickly dragged performance down to a crawl. I optimized the logic around direct lookups and stuck with that. Around that time, my acceptance into the cybersecurity program came through, so my coding time took a backseat as coursework became my main priority. Progress slowed down considerably for a few months.

Fast-forward to December 2025: I finally dialed in a stable, scalable gravity engine fast enough to run authoritatively on the server. Next, I introduced an NPC to the world and began tackling how entity synchronization should function online versus offline.

I restructured the WebSocket networking so the server acts as the single source of truth. Whenever a client attempts an action, it must authenticate and request permission from the server: "May I perform this action?" The server validates the request and acknowledges it. The server handles NPC pathfinding and movement directly, treating clients essentially as display terminals and event repeaters. When a player moves, the input is sent to the server, validated, and broadcast to all connected clients, rendering just like any other entity in the simulation.

Getting that client-server authority model right was tricky. I had to determine priority: the players or the NPCs. The players naturally took precedence—if their inputs lag, the game feels unresponsive and unplayable. If an NPC's positional update arrives a few milliseconds late, the player won't even notice. In fact, that slight tolerance can even work in the player's favor during fast-paced combat.

---

[//]: # (SECTION_ID: ECHO-MAN-02_THE_ECHOES_ARCH-SEC-8)
## 8. Technical Cross-References & Realized Projects

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Technical Cross-References & Realized Projects (Click to Expand)</summary>

* **Echoes of the World — Class & World Architecture**:
  * [Spatial Audio & World Grid](/docs/echoes/CLASS_WORLD_ARCHITECTURE): The realization of the Pygame audio game loop with 8-way compass, audio trigonometry, and step tracking.
  * [Menu Configuration Guide](/docs/echoes/MENU_CONFIG): Tabbed menu architecture, dynamic action dispatch, and spoken item lists.
* **JOSHY Audio Playback Suite**:
  * [00A Primer on Screen Readers & Accessibility](/docs/audio_suite/00A_BEGINNER_GUIDE_TO_SCREENREADERS_AND_ACCESSIBILITY): The evolution of `ctypes` NVDA DLL bridging into `accessible_output2` and Tolk DLL speech synthesis.
* **E-Profile Architecture & Forensic Devlog**:
  * [Chapter 5 — Audio Engine & Screen Reader Integration](/docs/devlog/04_26_THE_ORIGIN_ARCHITECTURE_ECHOES_OF_THE_WORLD): Dual speech output architecture (Tolk DLL vs. Windows SAPI5) and accessibility standards.
* **Zero-Trust Cybersecurity & Network Authority**:
  * [Zero-Trust Textbook — Chapter 1: Introduction to Zero Trust](/docs/textbook/Chapter_01_Introduction_To_Zero_Trust): Client-server state locking, server-authoritative validation, and mitigating client-side tampering.

</details>
