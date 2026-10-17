# Module 2: Access Control & Prompt Firewalls

## What Will I Learn in this Module?
This module explores the active defense systems that enforce the Sandbox tiers established in Module 1. You will learn:
* **Zero Trust Agentic Security:** Why the Siraugga framework assumes every AI tool call is inherently hostile until mathematically proven otherwise.
* **The Principle of Least Privilege:** How limiting an AI's Tool Whitelist prevents catastrophic Privilege Escalation (Jailbreaking).
* **Next-Gen Prompt Firewalls (NGPF):** How the Raugus Resolver inspects the semantic meaning of a JSON payload to block unauthorized actions.
* **Agentic Control Lists (ACLs):** How to define the exact type of JSON traffic allowed into a specific `/playground` namespace.

---

## 2.1 Zero Trust Agentic Security
Zero Trust is a comprehensive architectural approach to securing access across networks, AI subagents, and third-party environments. The overarching principle of Zero Trust is: **"Never trust, always verify."**

In legacy networks, the "perimeter" (the corporate firewall) was the only boundary between trusted internal users and the untrusted internet. In the Siraugga framework, this concept is completely inverted. Because autonomous AI agents are prone to Agentic Drift and hallucinatory Prompt Injections, *any place an access control decision is required is considered a perimeter*. 

Even if a highly privileged `Coding` subagent successfully authenticated and bypassed the outer firewall, it is not trusted to alter the `/playground` database until the Raugus Resolver mathematically verifies its specific `write_to_file` payload. The AI must be verified at every single layer of logic execution.

## 2.2 The Principle of Agentic Least Privilege
To enforce Zero Trust, DevCore utilizes the **Principle of Least Privilege**. This dictates that users and AI processes should be granted the absolute minimum amount of access required to perform their specific work function. 

In the DevCore ecosystem, if a subagent is tasked simply with reading a file to summarize its contents, it should *never* be spawned with a Tool Whitelist that includes `write_to_file` or `run_command`. Giving an AI tools it does not explicitly need vastly increases the attack surface if that AI suffers a Prompt Injection.

### Agentic Privilege Escalation (Jailbreaking)
When the Principle of Least Privilege fails, the system is vulnerable to **Privilege Escalation** (commonly known in the AI space as Jailbreaking). In this exploit, vulnerabilities in the access control system are used to grant a lower-tier AI higher levels of privilege. If an AI breaks out of its DAC (Discretionary) sandbox and gains MAC (Mandatory) root privileges, the entire host is compromised.


## 2.3 Next-Gen Prompt Firewalls (NGPF)
Legacy firewalls relied on "Port Monitoring" (e.g., blocking Port 80). In an AI ecosystem, Port Monitoring is entirely useless. Simply knowing that a Subagent used the `run_command` tool tells the Admin nothing. Was the AI running a diagnostic `ls` command, or was it compiling malware? 

To solve this, Siraugga utilizes a **Next-Gen Prompt Firewall (NGPF)** (often referred to as the Raugus Resolver). 

Instead of blocking ports, the NGPF performs **Semantic Visibility and Control (SVC)**. It deeply inspects the JSON payload of every tool call passing through the WebSocket. It analyzes the *semantic meaning* of the prompt. If the NGPF detects an Intrusion Event (e.g., a prompt attempting to override system instructions) or a Malware Event (an AI writing a destructive script), it violently severs the connection before the Subagent can even process the tokens.


## 2.4 Agentic Control Lists (ACLs)
While the NGPF analyzes semantic intent, **Agentic Control Lists (ACLs)** provide hard, static boundaries. An ACL is a sequential list of permit or deny statements applied to the sandbox.

For example, an Admin can configure an ACL that states:
1.  `Permit` the `read_file` tool if the target directory is `/playground/game_demo/`.
2.  `Deny` the `read_file` tool if the target directory contains `.env` or `/core_engine/`.
3.  `Deny` all other traffic.

### Sandbox Rule Evasion (Bypassing ACLs)
ACLs can give a false sense of security if they are overly relied upon. Sophisticated threat actors know how to bypass static ACLs using a technique known as **Sandbox Rule Evasion**.

Because an ACL only looks for exact string matches, a rogue AI can use **Semantic Steganography**. Instead of executing `cat .env` (which the ACL would block), the AI might encode the command in Base64 or obfuscate the bash script through string concatenation (e.g., `c""a""t .e""n""v`). This allows the malicious payload to slip past the static ACL, forcing the Orchestrator to rely on the probabilistic machine-learning models of the Next-Gen Prompt Firewall to catch the hidden intent.

## 2.5 Sub-File Granularity and AST Diffing

The implementation of the Next-Gen Prompt Firewall (NGPF) introduces a complex architectural dilemma: **Sub-File Granularity**. What happens if an AI requires legitimate `Write` access to a specific file, but critical components *inside* that file (such as a specific security function or authentication variable) must remain strictly locked as `Read-Only`?

If the NGPF relies purely on File Classification Tiers, it cannot enforce this. If the file is writable, the entire file is writable. 

To achieve Sub-File Granularity, the DevCore architecture relies on two advanced systems: **Deep Alias Mapping** and **AST Diffing**.

### 1. Deep Alias Mapping
The Raugus Map Generator does not stop at the file level. When mapping the host operating system, it utilizes Python's native Abstract Syntax Tree (`ast`) library to physically read the source code of every executable script. It parses the syntax tree, extracts every top-level Function and Variable, and assigns them independent permission blocks within the `raugus_map.json` architecture. 

For example, `devcore.core.App Router Module` may have full `Read/Write` access, but the specific function alias `devcore.core.App Router Module::hypercorn_config` can be statically assigned a `Read-Only` permission block.

### 2. Proactive Memory Interception (The PreToolUse Hook)
If an AI attempts to rewrite a file (e.g., invoking `replace_file_content`), the NGPF must prevent the modification from ever reaching the physical hard drive. It utilizes a **PreToolUse Hook** (`.agents/hooks.json`).

Before the Operating System is notified of the write request, the Hook intercepts the execution in RAM. It performs an **AST Diff**:
1. It pulls the original file from the host storage into memory.
2. It virtually applies the AI's proposed replacement code.
3. It parses the new Abstract Syntax Tree and calculates the modified line-number ranges.
4. It cross-references the modified nodes against the Deep Aliases in the Raugus Map.

If the NGPF calculates that the AI is attempting to modify a function node explicitly flagged as `Read-Only`, the firewall instantly outputs a `deny` decision. The tool execution is violently aborted, and the file on the physical disk remains 100% untouched. 

### 3. Elegant Degradation (Agent UX)
A critical feature of the PreToolUse Hook architecture is **Elegant Degradation**. 

In older reactive firewalls, detecting a breach resulted in the system violently terminating the AI process (`proc.kill()`). While secure, this severed the WebSocket connection, leaving the human user with a frozen UI or a meaningless drop-off. 

The Proactive PreToolUse Hook does not kill the agent. When an AI is blocked from writing to a locked AST node, the tool execution fails gracefully. The specific reason (e.g., `"AST Diffing blocked the modification"`) is injected directly back into the AI's context window. 

Because the AI is instantly aware of *why* it was blocked, it can naturally pivot. The AI will remain alive and respond to the human in the chat feed, typically offering a compliant fallback action: *"I am blocked from modifying this system function directly. I will generate an Implementation Plan artifact instead for your manual review."* This ensures absolute security without degrading the human user's experience.

## 2.6 The Semantic Mantrap (Concurrency Firewall)

Because DevCore orchestrates autonomous AI Swarms, it is highly susceptible to **Agentic Race Conditions**. If Subagent A and Subagent B both attempt to modify a core database (like `session_ownership.json`) or perform AST Diffing on the exact same file at the exact same millisecond, state corruption can occur. Even worse, a malicious payload could theoretically slip through the firewall if the validation logic is busy processing a legitimate request on a parallel thread.

To eliminate this vulnerability, the framework utilizes **The Semantic Mantrap**. 

A mantrap is a physical security device with two interlocking doors, ensuring only one authenticated entity can be inside the execution chamber at a time. In DevCore, this is implemented natively at the Operating System kernel level.

### The Staggered Logic Flow
When a Subagent attempts to execute a high-risk modification, it must pass through the Mantrap:
1. **The Outer Door (Acquiring the Lock):** The agent requests an exclusive OS-level file lock. If another agent is already inside, the requesting agent is physically frozen at this line of code. Its logic flow is completely staggered.
2. **The Execution Chamber (Validation & Write):** Once inside, the agent performs its AST Diffing or Database Write securely, isolated from parallel threads.
3. **The Inner Door (Release):** Upon completion, the lock is released, and the next queued agent is permitted to enter.

### Cross-Platform Kernel Locking
Because standard Python async locks do not function reliably across independent command-line subprocesses, the Semantic Mantrap utilizes absolute file descriptor locking:
* **Linux/WSL:** Utilizes `fcntl.flock(fcntl.LOCK_EX)` to enforce the kernel lock.
* **Native Windows:** Utilizes the Microsoft Visual C Runtime (`msvcrt.locking` with `LK_LOCK`) to lock specific memory regions of the file, guaranteeing identical thread-staggering behavior regardless of the host OS.
