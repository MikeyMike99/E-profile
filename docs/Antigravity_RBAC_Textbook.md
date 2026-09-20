# Chapter 1: Tier 5 - The Architecture of Absolute Power

## Introduction: The God Mode Paradox
The Super Admin (Tier 5) is the ultimate authority within the Antigravity ecosystem. Unlike lower tiers—which are confined to manipulating application logic or isolated project workspaces—the Tier 5 agent operates at the root of the infrastructure. It has the power to manage the host operating system, alter the core agent daemon, and orchestrate remote nodes. 

Granting an autonomous AI agent this level of "God Mode" introduces a unique security paradox. As a developer, you need the agent to have absolute freedom to evolve, debug, and maintain the system. Yet, that same freedom makes it highly volatile. A single hallucination, an infinite loop, or a prompt injection attack could wipe the server. 

To solve this, Tier 5 abandons the standard application-layer security model. Instead, it relies on a **"Trust but Verify"** philosophy. This chapter breaks down exactly how to build an indestructible core engine, translating deep Linux systems engineering into practical benefits for the developer.

---

## Section 1: The Genesis of Identity

The most vulnerable moment of any highly secure system is its birth. If you expose your initial setup process to the web—even temporarily—you invite race conditions where automated scanners could claim your server before you do.

### Asymmetric Bootstrapping
The genesis user must be created out-of-band. You connect to your server via a secure SSH terminal and run a local bootstrapping script. This script proactively checks if a Super Admin already exists, preventing accidental lockouts or overwrite attacks. 

Instead of generating a standard password, the system uses an **Ed25519 Asymmetric Key Pair**. 
> **Key Concept - Asymmetric Cryptography:** Think of this as a lock and a key. The server only holds the lock (the Public Key). Your personal computer holds the key (the Private Key). 

* **The Developer Benefit:** Because the server never actually stores your password, a catastrophic database breach doesn't compromise your identity. Even if an attacker dumps your entire database, they only get the "lock," which is useless without your private key.

### The Lockout Paradox
One of the most painful frustrations when building a fortress is accidentally locking yourself out. If a database corruption revokes your Super Admin status at the application layer, you will be trapped outside your own creation.
* **The Ghost Admin Remedy:** Never try to reason with a broken application. The system maintains an air-gapped `ghost_admin.py` script on the host. If locked out, you bypass the app entirely via SSH, halt the daemon to freeze state, and use this script to directly inject the Tier 5 flag back into the OS-level database.

---

## Section 2: The Physical Bridge & IPC

Once your identity is established, the web application needs a way to securely talk to the Agent Daemon running in the background.

### Inter-Process Communication (IPC)
Using standard `localhost` TCP ports to connect the web application to the Agent is a massive vulnerability, as local processes can sniff or spoof TCP traffic. Instead, the engine uses **UNIX Domain Sockets (`.sock`)** combined with Kernel-Level Peer Credentialing (`SO_PEERCRED`).
> **Key Concept - SO_PEERCRED:** This is a feature of the Linux kernel that mathematically verifies the exact User ID (UID) of the process sending a command to the socket. 

* **The Developer Benefit:** You don't need to write complex firewall rules or authentication middleware between your web app and your daemon. The Linux kernel does the math for you. If a rogue script tries to send a command to the socket, the kernel instantly proves it wasn't sent by your authorized Web Server user and drops it.

### The Accessibility Imperative
* **A Hard Lesson:** Standard SSH terminals and generic UI toolkits (like Tkinter) often fail to interface with screen readers (like NVDA), resulting in "dead silence." A Super Admin interface is entirely useless if it refuses to speak to the architect. 
* **The Solution:** The physical access point must be decoupled from legacy terminal constraints. By routing communication through custom accessible DLLs or ARIA-compliant WebSockets, the Super Admin is never "trapped in the terminal" while managing root infrastructure.

---

## Section 3: Forging the Sandbox

Because the Agent Core functions as a plugin for external game engines and web applications, you (the Super Admin) must project your authority downwards to lesser tiers (Admins, Devs, Modders) without tightly coupling the agent to the host application's database.

### The Stateless Handoff
The plugin does *not* manage passwords. It defers to the host application (like E-Profile). When a user logs in, the host application generates a short-lived **JSON Web Token (JWT)** containing the user's `UUID` and their `Tier_Level`.
The Host App securely passes this token over the UNIX socket to the Agent Daemon. The Daemon verifies the signature, consults a dynamic `policies.yaml` file to determine their permissions, and materializes a sandbox before the user is ever allowed to connect.

### Dynamic Contained Environments (tmpfs)
When a lower-tier user initiates a session, the Super Admin engine dynamically provisions a dedicated sandbox directory mapped directly to the user's cryptographic `UUID`.
> **Key Concept - tmpfs (RAM Disks):** Instead of writing temporary files to the physical hard drive, these sandboxes are mounted in the server's Random Access Memory (RAM). 

* **The Developer Benefit:** First, absolute accountability. Every read, write, and agent-generated script is trapped in this ID-bound folder, meaning anonymous lateral movement is impossible. Second, it saves your hardware. Letting an AI rapidly write and rewrite thousands of test files will quickly burn out an SSD. By using RAM disks (`tmpfs`), the code generation happens at lightning speed, and when the server reboots, the temporary files vanish without a trace.

### The Reaper Kill Switch
Because JWTs are stateless (they can't easily be "logged out"), the Agent Core maintains a high-speed, in-memory Revocation List. If a developer goes rogue, you issue a global Kill Command. A background "Reaper Thread" instantly hunts down and sends a `SIGKILL` to any active worker sub-agent associated with that ID, destroying the user's session mid-execution.

---

## Section 4: Agent Cognition & Orchestration

To manage complex architectures over time, the Tier 5 agent cannot rely solely on its immediate context window (which degrades over long conversations). It must maintain persistent memory and delegate tasks safely.

### Hybrid Memory Systems
The system implements a local **Vector Database** (like Chroma) for semantic search over past decisions, paired with a **Knowledge Graph** (like Neo4j) to map hard architectural relationships (e.g., "Service A depends on Database B").
* **The Developer Benefit:** The AI actually *remembers* your codebase. When tackling a new problem, it queries the vector database to retrieve relevant past decisions, saving you the immense frustration of having to re-explain your system's architecture every time you start a new session.

### Privilege Attenuation (Swarming)
The Tier 5 agent acts strictly as an orchestrator/planner. It decomposes large directives and spawns short-lived worker agents to carry them out. These sub-agents **never** inherit Tier 5 credentials. They run under strict sandbox boundaries (Tier 2 or 3). The worker agents return structured diffs to the Tier 5 parent, which audits the output before applying permanent changes.

---

## Section 5: The Shield (Self-Healing & Attack Surface)

A highly secure application layer is useless if the underlying daemon architecture is fragile. The core engine must recover from API deadlocks, memory corruption, or bad configuration files without human intervention.

### OS-Level Resource Isolation (cgroups v2)
Relying on application-layer timeouts is dangerous. A runaway AI generating an infinite loop will crash the host server. The core engine is launched as a Linux `systemd` service with strict resource directives.
* **The Developer Benefit:** True peace of mind. By setting a hard `MemoryMax` and `CPUQuota`, you can leave the AI running massive code-refactoring tasks overnight. If the AI hallucinates a memory-leaking loop, the Linux kernel's OOM (Out of Memory) killer will ruthlessly terminate the agent *before* it affects your host server.

### The Canary Thread & Janitor Process
* **The Canary:** The engine runs a dedicated internal thread that continuously pings its own socket. If the socket fails to respond within 5 seconds, the Canary concludes the main thread is caught in a silent deadlock and forcefully restarts it.
* **The Janitor:** On server boot, a Janitor sequence wipes all unclaimed `tmpfs` sandbox folders, orphaned `.sock` files, and clears the revocation list to prevent state bleed from previous crashes.

### Threat Sanitization & Error Masking
Incoming data must be treated as highly radioactive. All external data fed into the agent's context window is isolated using strict semantic delimiters (e.g., `<user_data_untrusted>`). 
* **The Developer Benefit (CWE-209 Prevention):** It is incredibly frustrating to watch an AI "socially engineer" its way out of a sandbox simply by reading its own verbose error logs. If a stack trace reveals internal IP addresses or true physical directory paths, the agent learns the host layout. The system intercepts and replaces all stack traces with generic error strings before they re-enter the context window, blinding the agent to the underlying infrastructure.

---

# Chapter 2: Tier 4 - The Application Admin (The Operator)

## Introduction: The Illusion of Absolute Power
In the traditional software industry, an "Administrator" is often treated as synonymous with a "Super User"—someone holding the keys to the database, the server, and the source code itself. In the Antigravity ecosystem, this is considered a catastrophic anti-pattern. 

The most dangerous entity in any production environment is a non-developer Administrator with a compiler. 

To the end-users and lower-tier profiles, the Tier 4 Admin appears to possess "God Mode." They control who gets banned, when the server restarts, and when a new feature goes live. But this is a deliberate, highly engineered illusion. The Tier 4 Admin is not an engineer; they are the ultimate **Operations and Release Manager**. 

> **Key Concept - Separation of Concerns:** If a tech stack is an orchestra, the Tier 3 Developer writes the sheet music and builds the instruments. The Tier 4 Admin is the Conductor. The Conductor decides when the orchestra plays and how fast they play, but the Conductor is strictly forbidden from jumping into the pit and rewriting the sheet music mid-performance.

By physically stripping the Admin's ability to edit raw source code, the Tier 5 Super Admin ensures that a live crisis cannot be worsened by a panicking Operations Manager accidentally injecting a syntax error into the core game loop.

## Section 1: The Operator's Toolkit (Buttons & Dials)

Because the Admin is denied raw code access, their Agent interfaces with the application through a highly privileged, completely abstracted control layer. They do not see Python scripts; they see Levers, Buttons, and Dials.

### The Operations Interface
Through their Agent, the Admin commands the lifecycle of the application:
* **The Reboot Cycle:** Instruct the system to gracefully drain connected players and restart the game engine or web server.
* **Feature Toggling:** Flip global boolean flags in the database to enable or disable seasonal events, beta features, or emergency maintenance modes.
* **State Debugging:** Pull real-time application state logs and active player metrics to diagnose live issues without ever touching the underlying infrastructure.

* **The Developer Benefit:** As a Tier 5 Super Admin, you can confidently hand off daily management to a Tier 4 Admin. You never have to worry about them accidentally dropping a critical database table with a malformed SQL injection, because they do not have SQL access. They only have a secure "Archive User" button.

## Section 2: The Deployment Bridge

If the Admin does not build features, how do features get into the game? 
The Admin serves as the absolute gatekeeper of the production environment. 

### The Quarantine Handoff
When a Tier 3 Developer finishes building a "new house" or a "new weapon" in their isolated `tmpfs` sandbox, that asset is fundamentally quarantined. The Developer cannot push it to the live server. 
Instead, they submit a deployment request. The Tier 4 Admin's Agent reviews the asset, runs automated safety checks, and visualizes the impact on the game. 

Only the Tier 4 Admin can authorize the release. When they issue the command, the Agent mechanically lifts the compiled asset out of the developer's quarantine and seamlessly plugs it into the live environment.

## Section 3: Sandbox Provisioning & Workforce Delegation

While the Tier 5 Super Admin manages the bare-metal architecture, the Tier 4 Admin acts as the manager of the human (and AI) workforce.

### Orchestrating the Hierarchy
The Admin inherits the ability to wield the sandbox provisioning engine. 
* **Role Generation:** The Admin dynamically generates cryptographic JWT invites for Tier 3 (Dev Team), Tier 2 (Guest/Modder), or Tier 1 (End User).
* **Workspace Spawning:** When the Admin assigns a new Developer to a specific project, the Admin's Agent commands the daemon to spin up a fresh, UUID-bound `tmpfs` sandbox for that Developer. 

* **The Developer Benefit:** The Super Admin never has to waste time doing IT support or account creation. The Tier 4 Admin manages the entire lifecycle of the workforce, completely automating the onboarding and offboarding of new developers and modders.

## Section 4: What the Admin Inherits from Tier 5

Because Tier 4 operates on the same core daemon designed by the Super Admin, they seamlessly inherit the most powerful capabilities of the architecture, but forcefully scoped to the application layer.

* **The Accessible Handoff (UX):** The Admin inherits the exact same frictionless, ARIA-compliant WebSocket interface. An Admin relying on a screen reader (like NVDA) is not forced to navigate hostile legacy dashboards or silent GUI windows. They log in via the web and seamlessly converse with their Operations Agent in a fully accessible environment.
* **Cognitive Memory (Operational Scope):** The Admin's agent remembers the operational history of the application—when the server last crashed, which Developer submitted which patch, and what feature flags are active. However, it is mathematically blinded to the Tier 5 Vector DB; it has zero memory of the Host OS or the daemon configuration.
* **Swarming (Task Delegation):** If an Admin needs to generate a massive weekly metrics report, their agent can spawn ephemeral Tier 1 sub-agents to crunch the database logs and return a summarized dashboard, saving hours of manual data entry.

## Section 5: The Hard Boundary (Absolute Code Denial)

The fundamental law of Tier 4 is absolute, unapologetic source code denial.
* **No Source Code Access:** The Admin is physically barred from reading or writing to the core application repositories (e.g., `server.py`, `models.py`, or core game engine scripts). 
* **No Host Infrastructure Access:** The Admin cannot execute OS-level commands (`apt-get`, `systemctl`), alter the `nftables` proxy, or view host IP routing.
* **No Escape Hatches:** The Admin's Agent is locked out of raw command execution (`python -c`, `bash`). It can only execute predefined, parameterized Webhooks or strictly authorized shell scripts (e.g., `./deploy_asset.sh --id 123`).
