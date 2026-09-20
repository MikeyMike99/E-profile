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
