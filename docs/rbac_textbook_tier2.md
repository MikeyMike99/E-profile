# Chapter 4: Tier 2 - The Guest / Client (Plugin Creator)

## Introduction: The "Black Box" Modder
I wanted to invite passionate gamers and third-party clients to build incredible plugins for the platform. But I knew that if I handed an external party my proprietary SDK, my intellectual property would be on a torrent site within 24 hours. Furthermore, letting them write raw code that directly interfaces with my engine meant a single typo could crash my live servers.

To solve this, I created a highly privileged, yet completely blind, creative environment. The Client gets massive AI power to build on their local machine, but when it comes to the core server, they operate through an impenetrable "Black Box."

## Section 1: The Disconnected Payload
The Guest is handed an EXE containing a localized Agent. There is no active WebSocket tether (unless paid). On their own local host, the Guest has immense privilege, but they have absolutely zero administrative access to my central server.

## Section 2: Semantic Abstraction (Coding in the Dark)
How does a Client build a plugin for an engine if they aren't allowed to see the engine? 

* **The "Wolf" Mechanism:** I engineered it so that if a Guest wants to spawn a wolf in the game, they never write or see `core_engine.entities.spawn(wolf, [x,y])`. Instead, they click a button or prompt the Agent: *"Spawn a wolf."* 
* **Background Binding:** In the background, my server safely binds their logic to the proprietary C/Python code. They get a working wolf, but the actual syntax is permanently hidden. The Agent only has access to sanitized `readme` files.

## Section 3: Sanitized Debugging (The Button Fallback)
Stack traces are incredibly dangerous because they reveal internal API structures. 
If the Guest's wolf fails to spawn, my Agent intercepts the crash and completely strips away the raw error logs. It returns a sanitized overview: *"The wolf is not spawning correctly because the speed attribute is missing."* The Agent then presents dynamic buttons: *"Do you want the wolf to walk fast, walk in circles, or run away?"* The Guest clicks a button, and the Agent safely repairs the hidden backend code.

## Section 4: The Security Risks & Defenses
Operating this Black Box introduced unique security risks that I had to defend against.

### 1. Blind Prompt Injection (The Trojan Wolf)
Because the Client uses semantic prompts, they might try naming the wolf `"wolf_1'); DROP DATABASE;--"`. I forced all incoming variables from Tier 2 to pass through aggressive type-checking and sanitization filters before the Agent binds them to the core code.

### 2. Side-Channel API Mapping
If my Agent says, *"The Vector3_Velocity requires a Z axis,"* a clever hacker just reverse-engineered my physics engine. I strictly prompted the Agent's error-reporting LLM to generalize errors (e.g., *"Movement data is invalid"*) to prevent them from mapping my hidden API.

### 3. Resource Exhaustion (The Infinite Loop)
If a Guest writes a script to click the "Spawn Wolf" button 10,000 times a second, they could crash my testing server. I heavily rate-limited the Tier 2 API endpoints to immediately shut down any localized DoS attacks.
