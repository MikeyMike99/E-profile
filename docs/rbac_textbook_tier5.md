# Chapter 1: Tier 5 (The Super Admin)

## Introduction: The Philosophy of Absolute Access
The Super Admin (Tier 5) is the ultimate authority within the E-Profile and Antigravity Agent ecosystem. Unlike lower tiers which are confined to manipulating application logic or isolated workspaces, the Tier 5 agent operates at the root of the infrastructure. It has the power to manage the host operating system, alter the core agent daemon, and orchestrate remote nodes. 

Granting an autonomous AI agent this level of "God Mode" introduces a unique security paradox: the agent requires absolute freedom to evolve and maintain the system, yet that same freedom makes it highly volatile. A single hallucination or prompt injection attack could wipe the server. 

To solve this, Tier 5 abandons the standard application-layer security model. Instead, it relies on a **"Trust but Verify"** philosophy built on four core pillars:
1. **Asymmetric Identity:** Identity is mathematically proven via offline keys, never negotiated over a web UI.
2. **Out-of-Band Management:** Critical operations (bootstrapping, recovery, interface) occur via encrypted SSH tunnels or local UNIX sockets, bypassing the web server entirely.
3. **Privilege Attenuation (Swarming):** The Tier 5 agent acts primarily as an orchestrator, delegating volatile tasks to ephemeral, sandboxed sub-agents.
4. **Defense-in-Depth:** Every destructive action is padded by state snapshots, cryptographic WORM logging, and human-in-the-loop circuit breakers.

---

## Part I: Genesis and Identity
*Introduction: The most vulnerable moment of any highly secure system is its birth. Exposing the initial provisioning process to the web layer—even temporarily—invites race conditions where automated scanners could claim the server before the rightful owner. In Tier 5, identity must be established cryptographically, out-of-band, and bound to a specific trusted environment.*

### 1. Initial Provisioning (The Genesis User)
The genesis user must be created out-of-band via a one-time setup script (e.g., `bootstrap.py`) executed directly via the host terminal. 
* **Execution:** Connect to the server via SSH, run the script under the designated service user (not root, but the user the agent daemon will run as). The script initializes the underlying database and architecture.
* **Safeguard:** The script proactively checks for an existing Genesis block or Super Admin flag in the database. If found, it executes a hard-abort to prevent accidental lockouts or overwrite attacks.

### 2. Master Token Generation (Asymmetric Cryptography)
Symmetric tokens (e.g., standard high-entropy strings) are abandoned entirely in favor of an **asymmetric Ed25519 key pair**.
* **Why Ed25519:** It provides significantly better performance and security than RSA, utilizing much smaller key sizes that are easily handled in CLI environments.
* **The Architecture:** The server does not hold the "password". It only holds the public key. The local client holds the private key and cryptographically signs requests to prove identity. In the event of a server database dump, the attacker only acquires the public key, rendering it impossible to impersonate the Super Admin.

### 3. Token Storage & Secure Handshake
The initial handshake and token exchange rely entirely on the physical security of the underlying SSH connection.
* **Storage on Server:** The setup script writes the newly generated Ed25519 public key to the agent's internal database or a heavily restricted vault file.
* **The Export:** The script prints the private key directly to `stdout` in the active terminal session, or writes it to a temporary `genesis_key.pem` file with strict `chmod 400` permissions.
* **The Transfer:** Utilizing the encrypted SSH connection, the user securely copies the terminal output to their local machine, and immediately deletes the `.pem` file from the host server. The private key never traverses an application-layer network protocol.

### 4. Authentication & Recognition (Defense-in-Depth)
Execution access is strictly gated behind the environment master token matching the active session.
* **Environment Binding (mTLS & IP):** Super Admin recognition is bound to a specific trusted environment. Requests failing external validation (e.g., untrusted IP, missing SSH tunnel, or missing mutual TLS certificates) are instantly dropped by the agent.

### 5. The "Lost Key" Recovery Protocol
If the local workstation suffers a catastrophic failure, the recovery mechanism must bypass the agent entirely.
* **The Break-Glass Script:** The administrator connects to the server using underlying infrastructure SSH credentials and executes a dedicated `recovery.py` script.
* **The Process:** Utilizing OS-level execution privileges, this script halts the agent daemon, purges the existing Ed25519 public key, generates a brand new key pair, outputs the new private key to the terminal, and restarts the daemon.
* **Lockout Prevention:** The agent itself is mathematically restricted from altering this recovery script, ensuring the infrastructure administrator always retains a back-door reset route.

* **Developer Note (The Lockout Paradox):** One of the most painful frustrations when building a fortress is accidentally locking yourself out. If a rogue agent hallucination, a database corruption, or a strict RBAC policy bug revokes your Super Admin status at the *application layer*, you will be trapped outside your own creation. When this happens, **never try to reason with the broken application.** 
  * **The "Ghost Admin" Remedy:** You must maintain a standalone, air-gapped script (e.g., `ghost_admin.py`) on the host. If you are locked out of the app, you SSH into the host, halt the application daemon to freeze state, and run the script. This script bypasses all application logic and directly injects the Tier 5 flag back into your database row at the OS level before restarting the daemon.


---

## Part II: Execution, Infrastructure, & Failsafes
*Introduction: Unrestricted filesystem access is a loaded weapon. A Super Admin agent must act as a secure Bastion orchestrator rather than a blind executor. To prevent self-inflicted destruction, execution is protected through human-in-the-loop buffers, automated state snapshots, and out-of-band watchdogs.*

### 6. Physical Access Point
Exposing Tier 5 privileges over a public web route expands the attack surface unacceptably. 
* **Local CLI / Daemon:** Run the interface as a terminal binary on the local workstation, communicating with the host agent daemon over an encrypted SSH tunnel.
* **mTLS Authenticated WebSocket:** For graphical interfaces, a local dashboard bound to `localhost` initiates an outbound mTLS WebSocket connection to the server. Authentication occurs at the TLS handshake level before any application logic is reached.

* **Developer Note (The Accessibility Imperative):** Standard SSH terminals and generic UI toolkits (like Tkinter) often fail to interface with screen readers (like NVDA), resulting in "dead silence." A Super Admin interface is entirely useless if it refuses to speak to the architect. The physical access point must be decoupled from legacy terminal constraints and built using custom accessible DLLs or ARIA-compliant WebSockets. The Super Admin must never be "trapped in the terminal" while managing root infrastructure.


### 7. Execution Failsafes
Tier 5 relies on lightweight, automated failsafes that do not bottleneck latency.
* **State Snapshots:** Prior to any tool call that modifies the filesystem, a background script triggers an immediate state snapshot (e.g., `git add . && git commit -m "Pre-execution backup"`).
* **Execution Buffers:** Destructive commands are not executed instantly. The agent drafts the bash command or DB query and halts execution until it receives explicit `y/n` terminal confirmation.
* **Transactional Wrappers:** Tier 5 database modifications are executed within transactional wrappers that automatically roll back upon syntax errors.

### 8. Distributed Infrastructure (Multi-Node Access)
A true Super Admin agent requires managing remote database shards, load balancers, and external compute nodes.
* **The Bastion Host Model:** Treat the server hosting the Tier 5 agent as a secure bastion. The agent connects to remote nodes via SSH or authenticated APIs to orchestrate infrastructure.
* **Credential Management:** Never store remote credentials in the agent's memory. Inject short-lived STS credentials or use an `ssh-agent` with keys locked behind hardware security modules.
* **Granular Node Permissions:** The agent's remote access must follow least-privilege principles based on the specific sub-task (e.g., read-only tokens for querying remote log servers).

### 9. Network & API Access (Controlled Egress)
A binary choice between total air-gapping and unrestricted outbound access is problematic.
* **Implementation Strategy:** Lock down server outbound traffic using `nftables` or cloud security groups.
* **Egress Proxy:** Route all outbound HTTP/S requests through an internal forward proxy (like Squid) with an enforced domain allowlist (e.g., `api.anthropic.com`, `registry.npmjs.org`).
* **SSRF Prevention:** Block direct access to private IP ranges (`10.0.0.0/8`, `169.254.169.254`) to prevent the agent from pivoting into internal network assets.

### 10. "Break-Glass" Emergency Procedures
If the agent gets caught in an execution loop or the primary auth mechanism fails, an out-of-band recovery path is required.
* **Out-of-Band Process Supervisor:** Run the agent process under a supervisor daemon (`systemd`). Configure an emergency `SIGKILL` command outside the agent's control via root SSH. 
* **Automated Watchdog (Dead-Man's Switch):** Configure strict thresholds for CPU spikes and token spend velocity. If an active Tier 5 session loses connection with the client interface for more than 60 seconds, the daemon immediately locks all pending tool calls.

---

## Part III: Agent Cognition, Orchestration, & Memory
*Introduction: To manage complex architectures over time, the Tier 5 agent cannot rely solely on its immediate context window. It must maintain persistent, isolated semantic memory and safely delegate tasks using an ephemeral Swarm of least-privilege sub-agents.*

### 11. Agent Orchestration (Swarming)
Granting the Super Admin agent the ability to spawn lower-tier sub-agents is the most effective way to balance speed and safety via **privilege attenuation**.
* **Hierarchical Orchestrator Pattern:** The Tier 5 agent acts strictly as an orchestrator/planner. It decomposes large directives and spawns short-lived worker agents to carry them out.
* **Ephemeral Scope & Least Privilege:** Sub-agents **never** inherit Tier 5 credentials. Each child runs under strict sandbox boundaries (Tier 2 or 3) with isolated working directories.
* **Result Verification:** Worker agents return structured diffs or test outputs to the Tier 5 parent, which audits the output before applying permanent changes.

### 12. Long-Term Memory & Knowledge Graphs
Relying entirely on a massive context window for long-term architectural awareness is computationally expensive and prone to degradation.
* **Hybrid Memory System:** Implement a local Vector Database (like Chroma) for semantic search over past decisions, paired with a Knowledge Graph (like Neo4j) to map hard architectural relationships.
* **Strict Memory Isolation:** Tier 5 memory must be completely isolated at the infrastructure level (dedicated instance or air-gapped volume) to prevent lower-tier agents from extracting Super Admin secrets via prompt injection.
* **Contextual Rehydration:** When tackling a new problem, the agent queries the vector database to retrieve relevant past decisions and injects only those specific insights into its working context window.

### 13. Sandbox Impersonation
The Super Admin possesses the ability to seamlessly downgrade their agent to audit lower tiers without managing dummy accounts.
* **Assume Role Mechanism:** Utilizing a command structure (e.g., `/su tier3`), the Super Admin temporarily overrides their active session state.
* **Context Window Swapping:** During impersonation, the agent forcefully injects the target tier's system prompt and restricts the underlying tool registry. Tier 5 tools are physically unmapped.
* **Secure Reversion (Escape Hatch):** The session maintains a secure hardware or token-based "escape hatch" to revert to Tier 5, ensuring the restricted agent cannot independently trigger the reversion.

### 14. Dynamic Prompt Routing & Cost Allocation
Running every trivial filesystem operation through a frontier model is financially unsustainable.
* **The Router Pattern:** Place a fast, highly quantized local model (like Llama 3 8B) at the front of the execution chain to classify the complexity of the sub-task.
* **Model Delegation:** Trivial tasks (JSON formatting, log filtering) are routed to a fast local model. High-reasoning tasks (core architectural planning, self-modification) are routed exclusively to the frontier model.
* **Cost-Aware Agents:** The agent calculates the estimated token burn for massive sub-agent orchestrations and requests explicit approval if it crosses a predefined budget threshold.

---

## Part IV: Autonomy, Privacy, & Evolution
*Introduction: A true Super Admin agent must be capable of autonomous self-evolution. However, it must execute this evolution without severing its own host processes, exhausting budgets, or leaking infrastructure secrets to external cloud APIs.*

### 15. Data Privacy & Context Encryption
Sending raw sensitive data out of the network to external cloud LLMs introduces severe compliance risks.
* **Context Masking (Substitution Strategy):** Implement a local proxy that intercepts the outgoing prompt. Use a lightweight scanner (like Microsoft Presidio) to detect secrets and replace them with deterministic tokens (e.g., `<SECRET_DB_PASS_1>`). The local executor rehydrates the token with the actual secret before running it on the system.
* **Encryption at Rest:** The agent's memory, execution logs, and state databases must be encrypted at rest using strong AES-256-GCM encryption. Utilize memory-backed tmpfs for ephemeral agent states.

### 16. Autonomy & Asynchronous Execution
Unattended execution at Tier 5 must be partitioned strictly by action type.
* **Read-Only Autonomy:** It is safe to grant full asynchronous autonomy for monitoring tasks (e.g., ingesting server logs overnight and drafting incident reports).
* **Constrained Mutating Autonomy:** For tasks like banning IPs, implement a rigid policy engine. The agent can only execute predefined, narrow runbooks.
* **Human-in-the-Loop Fallback:** Any novel destructive action outside of pre-approved runbooks must push an asynchronous notification requiring a one-touch human sign-off before proceeding.

### 17. Resource Limits & Anomaly Detection
Lightweight, automated circuit breakers are mandatory to prevent orchestration loops from crippling infrastructure.
* **Hard Circuit Breakers:** Enforce strict limits on execution depth (e.g., max 15 iterations per sub-task without a human checkpoint) and a hard velocity cap on token spend per minute.
* **Loop Detection:** Track the agent's tool calls. If the agent executes the exact same command or experiences the same tool failure three times consecutively, the system triggers an automatic halt.
* **Semantic Divergence:** Monitor the agent's behavior relative to the initial prompt. If an agent tasked with reviewing Nginx logs suddenly attempts to execute database schema drops, an anomaly detector instantly revokes execution privileges.

### 18. Tool Registry & Extensibility
* **Hot-Reloading with Schema Validation:** Maintain a designated `tools/` directory. When a new custom Python script is saved, the agent daemon watches the directory, dynamically imports the script, extracts the function signature via reflection, and compiles it into an active tool schema on the fly without a server restart.
* **Execution Sandboxing:** Newly ingested tools should be treated as volatile. Execute them in an isolated subprocess or container sandbox (like a Firecracker microVM) to ensure that a syntax error doesn't crash the primary orchestration daemon.

### 19. Self-Modification & Updates
Allowing a Tier 5 agent to modify its own source code requires rigorous staging to prevent it from severing its own execution thread.
* **The Two-Stage Staging Pipeline:** The agent is physically barred from writing directly to its active execution files. It pushes proposed changes to a dedicated `staging/` directory.
* **Automated Validation:** Before merging, the system automatically triggers an isolated test suite (syntax checking, security linting) on the staging code.
* **The Watchdog Restart:** If tests pass, the agent signals an external watchdog process. The watchdog takes over, gracefully drains active tasks, swaps the staging code into production, and restarts the agent daemon. The agent never kills itself.

### 20. Auditing and Logging
Logging architecture must be explicitly decentralized and tamper-proof.
* **Complete Transparency:** Every raw prompt, tool call payload, execution output, and state change is logged to debug agent hallucinations.
* **WORM Storage (Append-Only):** Logs are written to an isolated, append-only environment lacking write-access from the agent itself (e.g., an external WORM bucket or hardened syslog server).
* **Cryptographic Signing:** Log entries are hashed and signed using a private RSA key. Any localized tampering by an attacker (or rogue agent) immediately triggers a hash mismatch during security audits.

---

## Part V: Attack Surface & Threat Sanitization
*Introduction: Absolute power requires absolute paranoia. A Tier 5 agent can execute any command it synthesizes, making incoming prompt injection or a bloated host environment a catastrophic combination. Security at this tier is not just about blocking unauthorized users; it is about protecting the agent from being manipulated by its own inputs.*

### 21. Attack Surface Minimization (The Bare Metal Principle)
The host operating system running the Tier 5 agent must be aggressively stripped down. Relying on a standard, bloated Linux distribution provides a massive arsenal to a hallucinating or hijacked agent.
* **Binary Pruning:** Remove or restrict access to unnecessary system utilities (`netcat`, `curl`, `gcc`, `make`). If the agent needs to make web requests, it must use the approved egress proxy, not a raw shell utility.
* **Developer Note (The Utility Paradox):** A common developer frustration is locking down an application, only to watch a compromised agent simply use a pre-installed OS utility (like Python's `os.system` or a stray bash script) to pivot. If the agent doesn't explicitly need a binary to function, delete it from the host's `$PATH`.

### 22. Threat Sanitization & Prompt Isolation
Incoming data must be treated as highly radioactive. If a Super Admin asks the agent to summarize a log file, and that log file contains a malicious prompt injected by a Tier 1 user, the agent could unwittingly execute it.
* **Semantic Delimiters:** All external data fed into the agent's context window must be isolated using strict XML-style delimiters (e.g., `<user_data_untrusted>`). This structurally instructs the LLM to treat the content as passive data, neutralizing hidden commands.
* **Error Message Sanitization (CWE-209):** If the agent executes a command that fails, the backend must intercept the error. It must return a highly generic string to the agent rather than the raw stack trace. 
* **Developer Note (The Social Engineering Loop):** It is incredibly frustrating to watch an AI "socially engineer" its way out of a sandbox simply by reading its own verbose error logs. If a stack trace reveals internal IP addresses or true physical directory paths (`/mnt/c/Users/...`), the agent will learn the host layout. Mask all errors before they re-enter the agent's context.
* **Second-Order Execution Defense:** Before the agent is permitted to write any executable file (`.sh`, `.py`), the payload must undergo static analysis. If high-risk system commands are detected in the generated code, the write operation is permanently blocked to prevent Trojan horse scenarios.

---

## Part VI: Bare Metal & Core Primitives
*Introduction: A highly secure application layer is useless if the underlying daemon architecture is fragile. The core engine must be built using strict Linux systems engineering principles to guarantee that a runaway LLM cannot exhaust host resources or bypass network stacks.*

### 23. The Core Event Loop (The Actor Model)
Standard asynchronous programming is insufficient for autonomous AI, as an LLM API call can easily hang and block the execution thread.
* **The Architecture:** The core engine implements an **Actor Model Architecture**. It acts as a decoupled "Message Broker" maintaining a priority queue.
* **Worker Preemption:** A dedicated Worker Thread pulls tasks from the queue, while the Main Thread strictly monitors the Worker's health. If the Worker hangs or hallucinates, the Main Thread preemptively kills the Worker and spawns a new one without restarting the overarching engine or dropping the WebSocket connection.

### 24. Inter-Process Communication (IPC)
Using standard `localhost` TCP ports to connect the web application to the Agent Daemon is a vulnerability, as local processes can sniff or spoof TCP traffic.
* **UNIX Domain Sockets (`.sock`):** The engine listens strictly on a `.sock` file, bypassing the network stack entirely for lightning-fast execution.
* **Kernel-Level Peer Credentialing (`SO_PEERCRED`):** The Linux kernel mathematically verifies the exact User ID (UID) and Group ID (GID) of the process sending the command. If a rogue script attempts to send a payload to the socket, the kernel proves it wasn't sent by the authorized Web Server user and instantly drops the connection.

### 25. OS-Level Resource Isolation
Relying on application-layer timeouts is dangerous. A runaway AI generating a fork-bomb script will crash the host server.
* **Control Groups (`cgroups v2`):** The core engine is launched as a `systemd` service with strict kernel-level resource directives.
* **Hard Limits:** 
  * `MemoryMax`: If the agent hits its RAM limit, the kernel's OOM killer terminates the agent *before* it affects the host server.
  * `CPUQuota`: Mathematically prevents the agent from monopolizing the processor.
  * `PrivateTmp=yes`: Grants the agent a completely isolated `/tmp` directory invisible to the rest of the server.

### 26. The Filesystem Hierarchy (Ephemeral RAM Disks)
Allowing an AI to rapidly write, test, and rewrite temporary code directly to the host's hard drive causes severe SSD wear and leaves digital shrapnel.
* **Volatile `tmpfs` (RAM Disks):** The physical layout of the core is strictly partitioned:
  * `/opt/antigravity/` (Immutable): Read-only binaries and core logic.
  * `/var/lib/antigravity/` (Persistent): The encrypted vector database (Memory).
  * `/dev/shm/antigravity/` (Volatile): The `staging/` environment where the agent generates and tests code is mounted on `tmpfs`. The sandbox exists entirely in RAM, operating at lightning speed. Upon server restart, the entire staging sandbox vanishes automatically.

---

## Part VII: Role Provisioning & Delegation (Plugin Architecture)
*Introduction: Because the Agent Core functions as a plugin for external game engines and web applications, the Super Admin must project their authority downwards without tightly coupling the agent to the host application's database. Delegation must be stateless, dynamic, and mathematically bound to user accountability.*

### 27. The Source of Truth (Stateless Delegation)
A secure plugin should never duplicate the host's user database to avoid desynchronization and credential leaks. 
* **Host-Driven Authentication:** The Host Application (E-Profile or the Game Engine) exclusively handles passwords and user logins. 
* **Cryptographic Handoff:** Upon successful login, the Host App generates a short-lived, asymmetric JSON Web Token (JWT) containing the user's `UUID` and integer `Tier_Level`. The Agent Core simply validates the JWT's signature against the Host's public key. If valid, the Agent temporarily assumes the restricted state defined by that token.

### 28. Workspace Binding & Accountability
To enforce absolute accountability, lower-tier agents must never share overlapping host directories.
* **Dynamic Contained Environments:** When a lower-tier user initiates a session, the Super Admin engine dynamically provisions a dedicated, isolated sandbox directory mapped directly to the user's cryptographic `UUID` (e.g., `/var/sandboxes/tier3_<UUID>/`).
* **Mathematical Accountability:** Every read, write, and agent-generated script is physically trapped inside this ID-bound folder. This ensures that any malicious prompt or destructive code is perfectly traceable back to the specific human operator who issued it, making anonymous lateral movement impossible.

### 29. Cryptographic Revocation & The Kill Switch
Because stateless JWTs cannot easily be "logged out" until they expire, the Super Admin must possess a mechanism to sever active sessions instantly.
* **The In-Memory Blacklist:** The Agent Core maintains a high-speed, in-memory Certificate Revocation List (CRL) for compromised `UUID`s. 
* **The Reaper Thread:** The Super Admin can issue a global "Kill Command" for a specific user ID. The Core Engine immediately adds the `UUID` to the blacklist and broadcasts a `SIGKILL` to any active worker threads or sub-agents associated with that ID, destroying the user's session mid-execution.

### 30. Dynamic Policy Propagation
Hardcoding the rules for Tiers 1-4 into Python files requires complete server restarts to modify, causing unacceptable downtime for a developer tool.
* **Configuration-as-Code:** The Super Admin manages a strict `policies.yaml` file defining the precise directory paths, token budgets, and LLM models allowed for each tier.
* **Hot-Reloading via inotify:** The Agent daemon utilizes kernel-level file watchers (`inotify`). If the Super Admin edits the `policies.yaml` file to revoke Tier 3 access to a specific database, the daemon hot-reloads the policy into memory instantly, applying the new restrictions to all subsequent tool calls without interrupting active connections.
