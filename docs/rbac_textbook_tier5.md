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
