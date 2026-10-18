[//]: # (DOC_ID: SIRA-DEV-SECURITY | VERSION: v1.1 | SCOPE: DEV)

# Antigravity Security & Threat Model Documentation

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-1)
## Threat Landscape for In-Game Developer & Assistive Study Deployments
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-1)

When embedding an autonomous AI portal inside developer workflows, game engines, and assistive study environments, standard conversational guardrails are insufficient. Hard architectural controls must prevent sandbox escapes, data leakage, and system compromise without exposing internal filesystem structures.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-1)
### 1. Symlink Traversal (CWE-59)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-1)
- **Methodology**: Canonical Path Resolution & Physical Boundary Enforcement
- **Vulnerability**: An unprivileged user creates a symbolic link within an assigned workspace pointing to restricted host files outside the project root. Traditional string-based path normalization only resolves relative dot-segments without dereferencing filesystem links, which could allow unauthorized reads or writes.
- **Mitigation Applied**: The backend security resolver dereferences all filesystem links to their canonical physical destination at the operating-system level and verifies that the physical destination resides strictly within the authorized workspace boundary before any file operation occurs.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-2)
### 2. Multi-Tenant WebSocket Bleed (CWE-200)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-2)
- **Methodology**: Session-Scoped Stream Routing
- **Vulnerability**: Indiscriminate WebSocket broadcasting could emit streaming agent tokens and tool outputs to all connected clients, leaking private prompts and session transcripts across users.
- **Mitigation Applied**: The task orchestration layer binds an immutable authenticated user context to each active WebSocket connection. Every asynchronous task is tagged with the originating session identity, and streaming output chunks are routed exclusively to sockets owned by that authenticated session.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-3)
### 3. Subprocess Environment & Credential Exfiltration (CWE-214)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-3)
- **Methodology**: Environment Whitelisting & Server-Side Credential Proxying
- **Vulnerability**: Spawning agent subprocesses with the host's raw environment variables could expose root API keys, cloud tokens, and sensitive host configuration if a prompt instructs the agent to inspect its environment.
- **Mitigation Applied**: The subprocess orchestrator constructs a strictly sanitized environment dictionary. Root billing and provider credentials are completely stripped from the agent's memory space. The subprocess receives only an ephemeral placeholder token and routes traffic through an internal server-side proxy, which attaches the encrypted vault key strictly on the backend before forwarding requests upstream.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-4)
### 4. Indirect Prompt Injection via Untrusted Assets (CWE-74)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-4)
- **Methodology**: Tiered Workspace Confinement & Semantic Context Delimiters
- **Vulnerability**: Poisoned third-party assets, scripts, or documents imported into a workspace may contain hidden adversarial instructions designed to hijack the agent's behavior when read.
- **Mitigation Applied**:
  - File inspection for unprivileged roles is strictly confined to designated safe workspace tiers.
  - Untrusted content is isolated inside structural semantic delimiters (`<user_data_untrusted>`), instructing the language model to treat enclosed content strictly as passive data rather than executable directives.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-5)
### 5. Localhost & Private Subnet SSRF (CWE-918)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-5)
- **Methodology**: OS-Level Sandbox Confinement & Loopback Isolation
- **Vulnerability**: An unprivileged user or adversarial prompt instructs the agent to query internal loopback services, administrative endpoints, or cloud metadata addresses.
- **Mitigation Applied**: Non-administrative sessions are forcefully launched inside an isolated sandbox mode, blocking arbitrary network probes and unauthorized loopback requests.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-6)
### 6. Resource Exhaustion & Runaway Subprocesses (CWE-400)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-6)
- **Methodology**: Execution Timeouts, Write Quotas, & Bounded Event Queues
- **Vulnerability**: Adversarial prompts triggering infinite execution loops, oversized disk writes, or unbounded memory consumption.
- **Mitigation Applied**:
  - Hard execution timeouts terminate runaway agent tasks automatically.
  - Per-transaction file write payloads are strictly capped.
  - Event delivery queues enforce a bounded message capacity to prevent memory exhaustion.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-7)
### 7. Dynamic Tool Feed Bleed (CWE-200 / CWE-497)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-7)
- **Methodology**: Real-Time Telemetry Scrubbing & Stealth Obfuscation
- **Vulnerability**: Even when file I/O is blocked by the firewall, streaming the agent's internal tool-call telemetry to the client interface could inadvertently reveal internal architectural indicators before the firewall denies the request.
- **Mitigation Applied**: Before any tool telemetry event is transmitted to unprivileged clients, an outbound sanitizer scans the payload for internal system indicators. If restricted indicators are detected, the server scrubs the payload and replaces the status announcement with a generic message (`"Running a routine background check..."`), preventing architectural reconnaissance.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-8)
### 8. Source Code Disclosure via Backup Artifacts (CWE-530)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-8)
- **Methodology**: In-Place Atomic Editing & Zero-Residue Workspace Policy
- **Vulnerability**: Automated editing tools that leave temporary `.bak`, `.orig`, or `.tmp` files on disk risk exposing source code or configuration data if a web server serves unrecognized file extensions as plain text.
- **Mitigation Applied**: The architecture prohibits persistent backup or scratch files across all workspaces. Code modifications are performed strictly in-place, relying on version control for state recovery and enforcing immediate cleanup of any temporary artifacts.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-9)
### 9. Custom Extension & Protocol Evasion (CWE-284)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-9)
- **Methodology**: Unified Pre-Execution AST Diffing Across Built-In & Custom Tools
- **Vulnerability**: Custom extension tools (such as coordinate-based line editors) operate outside standard built-in file tools and could bypass permission checks if the interceptor only inspects default tool signatures.
- **Mitigation Applied**: The pre-execution memory interceptor normalizes arguments across both built-in tools and custom Model Context Protocol (MCP) extensions. Proposed edits are projected into memory and parsed into an Abstract Syntax Tree (AST) to verify symbol-level read/write permissions against the Virtual File System (VFS) policy map before touching the disk.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-10)
### 10. Cloud Context Leakage of Sensitive Study Material & Cloud-Synced Folders (CWE-359)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-10)
- **Methodology**: The 5-Layer "Blindfolded Broker" Architecture & Zero-Config Sync-Root Discovery
- **Vulnerability**: When users store proprietary coursework, institutional policies, or PII-heavy study documents inside protected vaults or personal cloud-synced directories (such as Microsoft OneDrive folders with arbitrary custom names), standard AI file-reading or search tools would transmit raw document text directly to the cloud LLM.
- **Mitigation Applied (5 Defense Layers)**:
  1. **Layer 1 — VFS Sensitivity Tagging, Automatic Cloud-Sync Detection & Pre-Execution Block**:
     - The Virtual File System (VFS) policy map marks designated study vaults and automatically discovered cloud-synced directories as strictly sensitive (`read: false`, `write: false`, `execute: false`, `local_broker: true`).
     - **Zero-Config Cloud-Sync Root Detection**: Automatically identifies synced cloud storage directories regardless of what the folder is named by inspecting OS-level sync-engine metadata markers, shell class bindings, and cross-platform path normalizations across both native and virtualized mounts.
     - The pre-execution interceptor blocks all direct file-read, directory-list, file-write, and text-search tools targeting sensitive namespaces before execution.
  2. **Layer 2 — Shell Command & Operator Chaining Lockdown**:
     - Any terminal command whose working directory or argument string targets a sensitive vault or cloud-synced directory is blocked prior to shell execution.
     - Only single-purpose invocations of the authorized offline Local Inference Broker are permitted, and shell-chaining operators (`;`, `&&`, `||`, `|`, backticks, subshells) are strictly rejected.
  3. **Layer 3 — Anti-Exfiltration Intent Guard**:
     - If the online model attempts to socially engineer the offline broker into returning raw document text (requesting verbatim dumps, full text, word-for-word copies, or encoded payloads), the broker aborts prior to model inference and returns an explicit exfiltration block status.
  4. **Layer 4 — Verbatim Source Line Filter**:
     - Before returning any synthesized study digest or answer, the offline broker compares every output line against the raw source material. Any line exceeding 60 characters that matches the source document verbatim is automatically redacted.
  5. **Layer 5 — Ephemeral CPU Inference, Offline Document Parsing & POPIA DLP Scrubbing**:
     - Executes a quantized local instruction model (`Qwen2.5-1.5B-Instruct`) strictly on the local CPU in single-turn mode, releasing 100% of allocated RAM immediately after each request (0 MB idle footprint).
     - Extracts text 100% offline from plain text, Word (`.docx`), and PDF (`.pdf`) study materials with zero external network calls.
     - Both input text and synthesized outputs pass through deterministic regular expressions and local Natural Language Processing (Microsoft Presidio + `spaCy`) to redact:
       - **National Identification Numbers** (including 13-digit South African ID numbers) $\rightarrow$ `<REDACTED_SA_ID>`
       - **Student, Learner, Passport & Tax Identifiers** $\rightarrow$ `<REDACTED_ID_NUMBER>`
       - **Mobile & Landline Telephone Numbers** $\rightarrow$ `<REDACTED_PHONE>`
       - **Bank Account & Payment Card Numbers** $\rightarrow$ `<REDACTED_FINANCIAL_ID>`
       - **Physical Street Addresses** $\rightarrow$ `<REDACTED_ADDRESS>`
       - **Protected Health, Medical & Disability Information** $\rightarrow$ `<REDACTED_MEDICAL_INFO>`
       - **Person Names, Email Addresses, IP Addresses & Cryptographic Secrets** $\rightarrow$ `<PERSON>`, `<REDACTED_EMAIL>`, `<REDACTED_IP>`, `<REDACTED_SECRET>`

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-11)
### 11. Regulatory & Institutional Policy Alignment (Self-Study & Accessibility)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-11)
- **Regulatory Scope**: Engineered to align with the **Protection of Personal Information Act 4 of 2013 (POPIA)** and institutional AI, Acceptable Use, and Data Governance standards for **personal self-study, academic research, and assistive accessibility**.
- **Compliance Guarantees**:
  - **Assistive Accessibility & Non-Assessed Self-Study**: Supports blind and visually impaired learners by summarizing complex reading material and generating non-graded practice quizzes formatted for screen readers.
  - **Strict Cloud Boundary**: Raw institutional documents and personal identifiers never leave the local machine or enter public cloud AI context windows. Only de-identified, newly synthesized practice questions or high-level topic summaries reach the orchestrator for UI rendering.
  - **Zero Cross-Border Data Transfer**: All sensitive document parsing and PII redaction execute 100% offline on the local CPU.
  - **Tamper-Evident Audit Telemetry**: Every blocked access attempt, exfiltration query, verbatim redaction, and PII scrub event is recorded with ISO-8601 UTC timestamps to the central SIEM and intrusion alert queues.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-12)
### 12. Deep Red-Team Blind-Spot Audit & Hardening Summary
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-12)
During comprehensive red-team auditing of the runtime interceptor, local HTTP endpoints, and OS-level filesystem boundaries, **8 advanced bypass vectors** were identified, remediated, and locked behind **30 automated verification checks across 6 audit stages**:

1. **Hook Configuration Schema & Global Scope Enforcement**:
   - *Finding*: If a runtime hook manifest uses an unindexed array structure or is registered only at a workspace-relative level, the CLI runtime may fail to unmarshal the specification or miss sessions launched from nested subdirectories.
   - *Remediation*: Standardized the hook manifest to the strict named-object specification required by the runtime parser and enforced dual registration across both workspace and global user configurations.
2. **Local HTTP Loopback Read/Write Lockdown**:
   - *Finding*: Internal HTTP artifact routes intended for UI flip-card rendering could be queried via local loopback requests (`curl` or URL-fetching tools) to read or overwrite sensitive files if sensitivity checks were omitted at the HTTP layer.
   - *Remediation*: Enforced VFS sensitivity resolution directly inside the HTTP artifact read and save handlers, returning **HTTP 403 Forbidden** and logging an intrusion alert whenever a sensitive vault or cloud-synced path is requested—even under administrative sessions.
3. **Internal Runtime Step Aliases, URL Fetchers & Hex-Encoding (`%xx`) Deobfuscation**:
   - *Finding*: The CLI runtime maps internal execution steps to lower-level action aliases (such as directory listing, blob writing, shell execution, and URL fetching), and attackers could obfuscate restricted directory names inside URLs or shell commands using `%xx` hexadecimal encoding.
   - *Remediation*: Expanded the pre-execution interceptor to cover all internal runtime step aliases and URL-fetching tools, and integrated automatic URL percent-decoding prior to path evaluation.
4. **Immutable Self-Protection of Security Guard Modules**:
   - *Finding*: An elevated agent could attempt to modify, overwrite, or rename the firewall interceptor, VFS policy map, or offline broker via file-editing tools or stream-editing shell commands (`sed`, `awk`, `mv`, `cp`, redirection).
   - *Remediation*: Added a dedicated self-protection layer inside the pre-execution interceptor that hard-locks all security enforcement modules and configuration manifests against AI modification or shell tampering.
5. **Shell Wildcard Globbing & Relative Path Traversal Prevention**:
   - *Finding*: Shell commands executed from a sibling directory could use relative parent segments (`..`) combined with wildcard globs (`*`, `?`, `[`) to rename or move a protected directory without spelling its literal name.
   - *Remediation*: The pre-execution interceptor resolves relative tokens against the command's working directory and expands shell wildcards in memory prior to execution, blocking any command whose expanded targets intersect a sensitive boundary.
6. **String-Concatenation & Base64 Pipeline Deobfuscation**:
   - *Finding*: Inline scripting one-liners could split sensitive directory names across concatenated string literals or pipe base64-encoded commands directly into an interpreter.
   - *Remediation*: Added quote-concatenation collapsing and base64-decode pipeline blocking to the command analyzer before any subprocess is spawned.
7. **Two-Step Script Creation & Execution Inspection**:
   - *Finding*: An agent could write a benignly named helper script containing filesystem move or read logic targeting a protected vault, and then execute that script in a second step.
   - *Remediation*: The interceptor scans the source payload of any script file during write operations and inspects the contents of referenced script files prior to shell execution.
8. **64-Bit Hardware Inode (`st_ino`) Fingerprinting**:
   - *Finding*: Path-string validation alone could be bypassed if a protected folder were ever renamed outside standard tool channels.
   - *Remediation*: The VFS map records the 64-bit operating-system Master File Table (MFT) / filesystem inode identifier (`st_ino`) of every sensitive directory. Even if a directory's display name changes, its hardware inode remains locked by the resolver.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-13)
### 13. Indirect Version-Control Overwrite & Git-Trojan Bypass (CWE-284 / CWE-829 / CWE-74)
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-13)
- **Methodology**: VCS Command Introspection, Remote Pinning, & Filesystem Inode Immutability.
- **Vulnerability**: While standard file modification tools (`write_to_file`, `replace_file_content`, `edit_lines`) and shell redirections (`>`, `sed`, `mv`) are intercepted by the PreToolUse security firewall, an adversary with architectural knowledge of hook locations (`.agents/hooks.json`, `.agents/raugus_hook.py`) can exploit native Version Control System (VCS) operations (`git pull`, `git checkout`, `git restore`, `git apply`). By injecting an adversarial prompt or guidance string (e.g., claiming security hotfixes must be pulled from Git), the adversary coerces the agent into executing a Git pull or branch checkout. Because Git writes directly to the working tree on disk via its compiled C-runtime, it bypasses file-tool interceptors and bash redirection filters, silently replacing core security hooks on the next pull.
- **The CoT Telemetry Reconnaissance Vector (CWE-200 / CWE-74)**: Real-time broadcast of internal reasoning and raw pre-tool hook error strings leaks defensive filters to the observer. In this incident, the agent's live narration of blocked in-place edits and internal mental models allowed the observer to identify the exact defense mechanisms in real time, craft a targeted prompt injection ("pull it from git"), and steer the agent directly into attempting a Git-based overwrite.
- **Mitigation Applied (5-Layer Defense Protocol)**:
  1. **PreToolUse VCS Mutation Interception**: The PreToolUse hook inspects terminal Git commands and immediately denies mutating operations (`git checkout`, `git restore`, `git reset`, `git apply`, `git pull`, `git merge`) whenever their target arguments intersect `PROTECTED_SECURITY_FILES`. Read-only commands (`git log`, `git diff`, `git status`) remain authorized.
  2. **Remote Lockdown & Origin Pinning**: Commands altering repository upstream remotes (`git remote add`, `git remote set-url`, `git remote rm`) are blocked, preventing the agent from being tricked into fetching from untrusted external repositories.
  3. **OS-Level Filesystem Inode Immutability (`chmod 444`)**: Core security guard modules and configuration manifests are marked read-only at the filesystem inode layer. Even if a mutated Git command runs, the Git binary aborts with an operating-system permission error before modifying files in the working tree.
  4. **Out-of-Band Human-in-the-Loop Standard**: System prompts and resolver rejection messages strictly declare that autonomous agents are prohibited from modifying or pulling security files. Updates to security hooks require out-of-band administration directly on the host console by authorized human administrators.
  5. **CoT Telemetry & Error Sanitization**: Runtime tool rejection strings and reasoning telemetry emitted to observer feeds are scrubbed of raw regex filters, internal file paths, and implementation details to prevent adversarial reconnaissance.

---

[//]: # (SECTION_ID: SIRA-DEV-SECURITY-SEC-9)
## 9. Cross-References & System Parallels
[//]: # (SECTION_ID: SIRA-DOC-SEC-SEC-9)

<details class="crossref-dropdown" style="border: 1px solid #38bdf8; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(56, 189, 248, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #38bdf8;">🔽 Cross-References & System Parallels: Zero-Trust Security & Vault Boundaries (Click to Expand Dropdown)</summary>

| Related Subsystem | Architectural Parallel & Shared Mechanism | Collection / Scope |
| :--- | :--- | :--- |
| **E-Profile RBAC & Threat Model** | [E-Profile Devlog: Chapter 4 & 6.3](/docs/eprofile/DEVLOG#chapter-4-the-5-tier-zero-trust-role-based-access-control-rbac--the-lockout-paradox) — 5-tier classification, Lockout Paradox Ghost Admin bypass, and server-side DevTools inspection defeat. | E-Profile Devlog |
| **EncryptMe Zero-Knowledge Tool** | [Cryptographic Architecture (v3.0)](/docs/encrypt_me/CRYPTOGRAPHIC_ARCHITECTURE) — Split-key challenge-response recovery and securing the Global Forensic Vault. | EncryptMe Security |
| **Zero-Trust Cybersecurity Textbook** | [Chapter 1: Tier 5 - Absolute Power](/docs/textbook/Chapter_01_Tier_5_The_Architecture_of_Absolute_Power) — Asymmetric Ed25519 root bootstrapping and kernel peer credentialing. | Zero-Trust Textbook |

</details>
