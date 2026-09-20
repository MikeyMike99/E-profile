# RBAC Textbook: Chapter 1 - Tier 5 (Super Admin)

## Overview
The Super Admin is the ultimate authority within the E-Profile and Antigravity Agent ecosystem. Operating on a "Zero Trust" model for all other tiers, Tier 5 is the sole role granted total sandbox evasion (`--dangerously-skip-permissions`). Because this tier has unrestricted execution power on the host OS, it requires enterprise-grade security, failsafes, and auditing.

## 1. Authentication & Recognition (Defense-in-Depth)
Tier 5 authentication relies on a multi-layered verification strategy rather than a single point of failure (such as a simple database flag).
* **Master Token Injection:** The agent verifies a cryptographically secure token injected at runtime via environment variables. This token is never hardcoded or committed to version control.
* **Database RBAC Linkage:** The standard `role: super_admin` database flag is used for UI rendering and routing, but *execution access* is strictly gated behind the environment master token matching the active session.
* **Environment Binding (mTLS & IP):** Super Admin recognition is bound to a specific trusted environment. Requests failing external validation (e.g., untrusted IP, missing SSH tunnel, or missing mutual TLS certificates) are instantly dropped by the agent.

## 2. Execution Failsafes
To mitigate the volatility of unrestricted filesystem access, Tier 5 relies on lightweight, automated failsafes that do not bottleneck latency.
* **State Snapshots (Automated Backups):** Prior to any tool call that modifies the filesystem, a background script triggers an immediate state snapshot (e.g., `git add . && git commit -m "Pre-execution backup"`).
* **Execution Buffers (Human-in-the-Loop):** Destructive commands are not executed instantly. The agent drafts the bash command, script, or DB query and halts execution until it receives explicit `y/n` terminal or API confirmation from the Super Admin.
* **Database Transactional Wrappers:** Tier 5 database modifications are executed within transactional wrappers. If the agent's output contains a syntax error or unintended table drop, the transaction automatically rolls back.

## 3. Auditing and Logging
Because a compromised Tier 5 agent could theoretically delete its own local logs, logging architecture is explicitly decentralized and tamper-proof.
* **Complete Transparency:** Every raw prompt, tool call payload, execution output, and state change is logged to debug potential agent hallucinations.
* **WORM Storage (Append-Only):** Logs are written to an isolated, append-only environment lacking write-access from the agent itself (e.g., an external WORM bucket, hardened syslog server, or external logging API).
* **Cryptographic Signing:** Log entries are hashed and signed using a private RSA key. Any localized tampering by an attacker (or rogue agent) will immediately trigger a hash mismatch during security audits.

## 4. Sandbox Impersonation
The Super Admin possesses the ability to seamlessly downgrade their agent to audit lower tiers without managing dummy accounts.
* **Assume Role Mechanism:** Utilizing a command structure (e.g., `/su tier3` or `/impersonate user_id`), the Super Admin temporarily overrides their active session state.
* **Context Window Swapping:** During impersonation, the agent forcefully injects the target tier's system prompt and restricts the underlying tool registry. Tier 5 tools (bash execution, core DB writes) are physically unmapped from the agent's context.
* **Secure Reversion (Escape Hatch):** The session maintains a secure hardware or token-based "escape hatch" to revert to Tier 5, mathematically ensuring that the restricted agent cannot independently trigger the reversion.

---

## 5. Physical Access Point
Exposing Tier 5 privileges over a public web application route—even hidden or token-gated—substantially expands the attack surface. The industry standard separates operational administration from standard web interfaces.

* **Recommended Architecture: Local CLI via Mutual TLS (mTLS) or SSH Tunnelling**
* **Local CLI / Daemon:** Run the interface as a terminal binary on the local workstation. It communicates with the host agent daemon over an encrypted, authenticated SSH tunnel or a direct UNIX domain socket if running locally.
* **mTLS Authenticated WebSocket:** For graphical interfaces, a local dashboard bound to `localhost` initiates an outbound mTLS WebSocket connection to the server daemon. Authentication occurs at the TLS handshake level before any application logic or agent processing is reached.
* **Why Hidden Web Routes Fail at Tier 5:** Relying on security through obscurity (e.g., `/admin-hidden-endpoint`) leaves the agent vulnerable to automated route scanning, session hijacking, cross-site request forgery (CSRF), and web server misconfigurations (such as reverse proxy leaks or cache poisoning).

## 6. Agent Orchestration (Swarming)
Granting the Super Admin agent the ability to spawn lower-tier sub-agents is one of the most effective ways to balance speed and safety, provided **privilege attenuation** is strictly enforced.

```text
[Super Admin Agent (Tier 5)]
        │
        ├──> Spawns [Coder Sub-Agent (Tier 3)]  ──> Sandboxed Workspace (Git branch)
        │
        └──> Spawns [Audit Sub-Agent (Tier 2)]  ──> Read-Only Filesystem / Logs
```

* **Hierarchical Orchestrator Pattern:** The Tier 5 agent acts strictly as an orchestrator/planner. It decomposes large directives into modular sub-tasks, generates an execution plan, and spawns short-lived worker agents to carry them out.
* **Ephemeral Scope & Least Privilege:**
    * Sub-agents **never** inherit Tier 5 credentials.
    * Each child agent runs under strict sandbox boundaries (Tier 2 or 3) with isolated working directories and transient API tokens scoped to that single sub-task.
* **Result Verification:** Worker agents return structured diffs, test outputs, or analytical findings to the Tier 5 parent, which audits the output before applying permanent changes.

## 7. Network & API Access
A binary choice between total air-gapping and unrestricted outbound access is problematic.

| Model | Pros | Cons | Ideal Use Case |
| --- | --- | --- | --- |
| **Strict Air-Gap** | Zero remote exfiltration risk; immune to network-based attacks. | Cannot query frontier cloud LLMs, download packages, or scrape live documentation. | On-premise local models (Ollama, vLLM) handling strictly confidential source code. |
| **Controlled Egress (Recommended)** | Agent can access necessary tools, updates, and APIs while blocking arbitrary connections. | Requires managing firewall rules or forward proxy configs. | Hybrid setups using external APIs (Claude/OpenAI) with code deployment capabilities. |
| **Unrestricted Access** | Zero configuration friction; full web browsing. | High risk of prompt injection directing the agent to leak environment variables or keys to external servers. | Prototype testing only; never suitable for production Tier 5 agents. |

* **Implementation Strategy (Egress Proxy + Firewall):**
    * Lock down server outbound traffic using `nftables` or cloud security groups.
    * Route all outbound HTTP/S requests through an internal forward proxy (like Squid or Envoy) with an enforced domain allowlist (e.g., `api.anthropic.com`, `registry.npmjs.org`, `pypi.org`, `github.com`).
    * Block direct access to private IP ranges (`10.0.0.0/8`, `192.168.0.0/16`, `169.254.169.254` metadata services) to prevent the agent from pivoting into internal network assets.

## 8. "Break-Glass" Emergency Procedures
If the agent gets caught in an execution loop, prompt-injected, or the primary auth mechanism fails, an out-of-band recovery path that does not depend on the application layer is required.

* **Out-of-Band Process Supervisor (Hard Kill Switch):**
    * Run the agent process under a supervisor daemon (`systemd` or an isolated container orchestrator).
    * Configure an emergency stop command outside the agent's control—such as sending a `SIGKILL` directly via root SSH or a hardware-level host console (IPMI/serial console).
    * The agent process must run under a restricted non-root system user so it lacks the OS-level permissions to alter its own process supervisor or block termination signals.
* **Automated Watchdog (Dead-Man's Switch):**
    * **Resource Caps:** Configure strict thresholds for CPU spikes, token spend velocity, and maximum file modifications per minute.
    * **Heartbeat Monitor:** If an active Tier 5 session loses connection with your client interface for more than 60 seconds, the daemon immediately pauses execution and locks all pending tool calls.
* **Emergency State Rollback:**
    * Implement an independent "nuclear" rollback script on the host that terminates running agent processes, reverts the working directory to the last known healthy Git commit (`git reset --hard HEAD@{upstream}`), and rotates all active agent session tokens.

## 9. Data Privacy & Context Encryption
If the agent is interacting with an external cloud LLM, sending raw sensitive data out of your network introduces severe compliance and security risks.

* **Context Masking (Substitution Strategy):** Implement a local proxy or middleware that intercepts the outgoing prompt. Use a lightweight scanner (like Microsoft Presidio or custom regex) to detect secrets and replace them with deterministic tokens (e.g., `<SECRET_DB_PASS_1>`). When the model's output requires that secret to execute a command, your local executor rehydrates the token with the actual secret before running it on your system.
* **Encryption at Rest:** The agent's memory, execution logs, and state databases must be encrypted at rest using strong AES-256-GCM encryption. Avoid writing raw secrets or context dumps to standard disk storage; utilize memory-backed tmpfs for ephemeral agent states.

## 10. Autonomy & Asynchronous Execution
Unattended execution at Tier 5 must be partitioned strictly by action type to prevent catastrophic unmonitored failures.

* **Read-Only Autonomy:** It is generally safe to grant full asynchronous autonomy for monitoring and triage tasks. The agent can ingest server logs overnight, analyze traffic, and draft incident reports independently.
* **Constrained Mutating Autonomy:** Tier 5 agents should never have unconstrained asynchronous mutation rights. For tasks like banning IPs, implement a rigid policy engine. The agent can execute predefined, narrow runbooks (e.g., "Add IP to firewall drop list if failed SSH attempts > 10").
* **Human-in-the-Loop Fallback:** Any novel destructive action or configuration change outside of pre-approved runbooks must push an asynchronous notification (e.g., via a CLI prompt or webhook) requiring a one-touch human sign-off before proceeding.

## 11. Resource Limits & Anomaly Detection
A malfunctioning orchestration loop can rapidly burn through API budgets or cripple server infrastructure. Lightweight, automated circuit breakers are mandatory.

* **Hard Circuit Breakers:** Enforce strict limits on execution depth. Set a maximum threshold for sequential tool calls without a human checkpoint (e.g., max 15 iterations per sub-task). Implement a hard velocity cap on token spend and API calls per minute.
* **Loop Detection:** Track the agent's tool calls and argument payloads. If the agent executes the exact same command or experiences the same tool failure three times consecutively, the system must trigger an automatic halt (`status: locked_awaiting_operator`).
* **Semantic Divergence:** Monitor the agent's behavior relative to the initial prompt. If an agent tasked with reviewing Nginx logs suddenly attempts to execute recursive directory deletions or database schema drops, an anomaly detector should instantly pause the session and revoke execution privileges.

## 12. Tool Registry & Extensibility
For a developer tool, administrative friction kills productivity, but allowing arbitrary code execution compromises security.

* **Hot-Reloading with Schema Validation:** You should not need a full server restart to ingest new capabilities. Maintain a designated `tools/` directory. When you save a new custom Python script, the agent daemon watches the directory, dynamically imports the script, extracts the function signature and docstrings via reflection, and compiles it into an active tool schema on the fly.
* **Execution Sandboxing:** Newly ingested tools should be treated as potentially volatile. Execute them in an isolated subprocess or lightweight container sandbox (like a Firecracker microVM) to ensure that a syntax error, infinite loop, or logic flaw in your custom script doesn't crash the primary orchestration daemon.

## 13. Self-Modification & Updates
Allowing a Tier 5 agent to modify its own source code introduces immense risk but is necessary for true autonomous evolution. The core issue is preventing the agent from severing its own execution thread or corrupting the daemon.

* **The Two-Stage Staging Pipeline:** Never allow the agent to write directly to its active execution files. The agent should push proposed changes to a dedicated `staging/` directory or a local Git branch.
* **Automated Validation:** Before merging, the system automatically triggers an isolated test suite (syntax checking, unit tests, and security linting) on the staging code.
* **The Watchdog Restart:** If tests pass, the agent signals an external, highly restricted watchdog process (e.g., a systemd service or a minimal standalone Python script). The watchdog takes over, gracefully drains active tasks, swaps the staging code into production, and restarts the agent daemon. The agent never kills itself.

## 14. Distributed Infrastructure (Multi-Node Access)
A true Super Admin agent cannot be confined to localhost. Modern architectures require managing remote database shards, load balancers, and external compute nodes.

* **The Bastion Host Model:** Treat the server hosting the Tier 5 agent as a secure bastion. The agent connects to remote nodes via SSH or authenticated APIs, acting as the central orchestrator across the infrastructure.
* **Credential Management:** Never store remote credentials in the agent's memory or static files. Inject short-lived, dynamically generated STS (Security Token Service) credentials or use an `ssh-agent` with keys locked behind hardware security modules or strict file permissions.
* **Granular Node Permissions:** Even though the agent is Tier 5 locally, its remote access should still follow least-privilege principles based on the specific sub-task. If it is only querying a remote log server, it should use a read-only remote token.

## 15. Long-Term Memory & Knowledge Graphs
Managing massive architectural changes over time requires persistent, structured memory. Relying entirely on a massive context window is computationally expensive and prone to degradation.

* **Hybrid Memory System:** Implement a local Vector Database (like Chroma or Qdrant) for semantic search over past decisions, paired with a Knowledge Graph (like Neo4j) to map hard architectural relationships (e.g., "Service A depends on Database B").
* **Strict Memory Isolation:** Tier 5 memory must be completely isolated at the infrastructure level. Use a dedicated database instance or an encrypted, air-gapped volume for Super Admin memory. If lower-tier agents share the same vector space, a clever prompt injection from a Tier 2 user could extract Tier 5 architectural secrets.
* **Contextual Rehydration:** When the agent tackles a new problem, it queries the vector database to retrieve relevant past decisions and injects only those specific insights into its working context window.

## 16. Dynamic Prompt Routing & Cost Allocation
Running every trivial filesystem operation or log parsing task through a frontier model is financially unsustainable and introduces unnecessary latency.

* **The Router Pattern:** Place a fast, highly quantized local model (like Llama 3 8B) at the front of the execution chain. Its sole job is to classify the complexity of the sub-task.
* **Model Delegation:** Trivial tasks like JSON formatting, log filtering, and regex generation are routed to a fast local model or a cheaper cloud API. High-reasoning tasks like core architectural planning, self-modification, and complex debugging are routed exclusively to the frontier model.
* **Cost-Aware Agents:** You can give the Tier 5 agent a "cost-estimation" tool. Before spawning a sub-agent for a massive code refactor, it calculates the estimated token burn and requests your explicit approval if it crosses a predefined budget threshold.

## 17. Initial Provisioning (The Genesis User)
The genesis user must be created out-of-band via a one-time setup script (e.g., `bootstrap.py` or a compiled binary) executed directly via the host terminal. Exposing genesis provisioning to a web endpoint—even temporarily—invites race conditions where an automated scanner could claim the server before the rightful owner.

* **Execution:** Connect to the server via SSH, run the script under the designated service user (not root, but the user the agent daemon will run as). The script initializes the underlying database and architecture.
* **Safeguard:** The script proactively checks for an existing Genesis block or Super Admin flag in the database. If found, it executes a hard-abort to prevent accidental lockouts or overwrite attacks by malicious actors.

## 18. Master Token Generation (Asymmetric Cryptography)
For Tier 5 access, symmetric tokens (e.g., standard high-entropy strings) are abandoned entirely in favor of an **asymmetric Ed25519 key pair**.

* **Why Ed25519:** It provides significantly better performance and security than RSA, utilizing much smaller key sizes that are easily handled in CLI and configuration environments.
* **The Architecture:** The server does not hold the "password". It only holds the public key. The local client holds the private key and cryptographically signs requests to prove identity. Even in the event of a total server database compromise and dump, the attacker only acquires the public key, rendering it impossible to impersonate the Super Admin.

## 19. Token Storage & Secure Handshake
The initial handshake and token exchange rely entirely on the physical security of the underlying SSH connection to the server.

* **Storage on Server:** The `bootstrap.py` script writes the newly generated Ed25519 public key to the agent's internal database or a heavily restricted `.env`/vault file.
* **The Export (One-Time View):** The script prints the private key directly to `stdout` in the active terminal session, or writes it to a temporary `genesis_key.pem` file with strict `chmod 400` permissions.
* **The Transfer:** Utilizing the encrypted SSH connection, the user securely copies the terminal output (or uses `scp` to pull the file) to their local machine, and immediately deletes the `.pem` file from the host server. The private key never traverses an application-layer network protocol.

## 20. The "Lost Key" Recovery Protocol
If the local workstation suffers a catastrophic failure and the private key is lost, the recovery mechanism must bypass the agent entirely and rely on fundamental host-level OS access.

* **The Break-Glass Script:** The administrator connects to the server using underlying infrastructure SSH credentials (which are strictly separated from the agent's credentials) and executes a dedicated `recovery.py` script (or `bootstrap.py --rotate-genesis`).
* **The Process:** Utilizing OS-level execution privileges, this script halts the agent daemon, purges the existing Ed25519 public key from the database, generates a brand new key pair, outputs the new private key to the terminal, and restarts the daemon.
* **Lockout Prevention:** The agent itself is mathematically and physically restricted from altering this recovery script or the host's SSH daemon configurations, ensuring the infrastructure administrator always retains a back-door route to reset the system.
