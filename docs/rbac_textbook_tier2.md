# Chapter 4: Tier 2 - The Guest / Client (Plugin Creator)

## Introduction: The "Black Box" Modder
Picture a passionate gamer or a third-party corporate client. They want to build an incredible plugin for your platform. They are enthusiastic, creative, and completely external to your company. 

If you hand an external party your proprietary SDK, or let them see your core function calls, your intellectual property will be on a torrent site within 24 hours. Furthermore, if you allow them to write raw code that directly interfaces with your engine, a single typo on their end could crash your live servers.

Tier 2 solves this by creating a highly privileged, yet completely blind, creative environment. The Client is given a massive amount of AI power to build applications on their *local* machine, but when it comes to the core server, they operate through an impenetrable "Black Box."

## Section 1: The Disconnected Payload
Unlike the Tier 3 Developer who requires a constant, highly monitored tether, the Tier 2 Guest operates primarily offline.

* **Stateless Operations:** The Guest is handed an EXE containing a localized Agent. Unless they are utilizing a paid, premium cloud model, there is no active WebSocket connection. The EXE only connects to the central server asynchronously when it needs to compile a plugin or fetch documentation.
* **Local God Mode, Server Peasant:** On their own local host machine, the Guest has immense privilege. They can use the Agent to generate their own local applications, write scripts, and build UI elements. However, their privilege ends at their local network card. They have absolutely zero administrative access to the central server.

## Section 2: Semantic Abstraction (Coding in the Dark)
How does a Client build a plugin for an engine if they aren't allowed to see the engine? 

* **The "Wolf" Mechanism:** If a Guest wants to spawn a wolf in the game, they do not write `core_engine.entities.spawn(wolf, [x,y])`. They never see that code. Instead, they interact with the Agent via a chat prompt or a button: *"Spawn a wolf."* 
* **Background Binding:** The Guest provides the attributes (e.g., speed, health). In the background, the server captures their logic and safely binds it to the proprietary C/Python code. The Guest gets a working wolf in their testing environment, but the actual syntax of the proprietary function call is permanently hidden from them. The Agent only has access to sanitized `readme` files describing what the functions do, not the source code itself.

## Section 3: Sanitized Debugging (The Button Fallback)
When a Guest writes broken logic, traditional IDEs throw a massive stack trace. Stack traces are incredibly dangerous because they reveal directory paths, variable names, and internal API structures.

* **Abstract Error Reporting:** If the Guest's wolf fails to spawn because their logic is corrupted, the Agent intercepts the backend crash. It completely strips away the raw error logs. 
* **Dynamic Resolution Buttons:** The Agent returns a human-readable, sanitized overview: *"The wolf is not spawning correctly because the speed attribute is missing."* The Agent then presents dynamically generated buttons to fix the issue: *"Do you want the wolf to walk fast, walk in circles, or run away?"* The Guest clicks a button, and the Agent safely repairs the hidden backend code on their behalf.

## Section 4: The Security Risks & Defenses
Operating a Black Box environment mitigates IP theft, but it introduces unique security risks that the architecture must defend against.

### 1. Blind Prompt Injection (The Trojan Wolf)
* **The Risk:** Because the Client uses semantic prompts and buttons to generate backend code, they might try to craft malicious attributes. For example, naming the wolf `"wolf_1'); DROP DATABASE;--"`.
* **The Defense:** The backend parser must treat all incoming variables from Tier 2 as violently untrusted. Before the Agent binds the Client's variables to the hidden core code, it must pass through aggressive type-checking and sanitization filters.

### 2. Side-Channel API Mapping
* **The Risk:** Even if you hide the stack trace, a clever attacker can map out your entire hidden engine by intentionally causing hundreds of errors and studying the Agent's sanitized responses (e.g., *"Oh, the Agent complained about a missing 'velocity' integer, so I know how their physics engine handles movement"*).
* **The Defense:** The Agent's error-reporting LLM is strictly prompted to never leak internal schema names. It must generalize errors (e.g., *"Movement data is invalid"* rather than *"Vector3 'velocity' expected"*). 

### 3. Resource Exhaustion (The Infinite Loop)
* **The Risk:** Since the backend handles the actual code execution, a Guest could write a script that clicks the "Spawn Wolf" button 10,000 times a second, crashing the testing server.
* **The Defense:** The Tier 2 API endpoints are heavily rate-limited. The architecture restricts how much computational power a single Tier 2 EXE can request from the backend testing servers, immediately shutting down any localized DoS attacks.
