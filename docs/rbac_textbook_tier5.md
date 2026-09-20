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

## Section 6: Defeating Race Conditions (TOCTOU & Symlink Armor)
At the root level, the architecture must defend against Time-Of-Check to Time-Of-Use (TOCTOU) vulnerabilities. Attackers love "Race Conditions." They will attempt to swap a safe file for a malicious symbolic link in the exact millisecond between when the Security Manager *checks* the file path and when the system actually *opens* the file descriptor.

* **The Mechanism (O_NOFOLLOW):** When the core engine opens any file for reading or writing, it utilizes the `os.O_NOFOLLOW` flag at the kernel level.
* **The Result:** If an attacker successfully executes a race condition and swaps the target file with a symlink pointing to `/etc/shadow` or a core `.env` file, the Linux kernel violently rejects the operation. The file descriptor guarantees that the system only opens hard, verified file inodes, completely immunizing the architecture against symlink spoofing.
