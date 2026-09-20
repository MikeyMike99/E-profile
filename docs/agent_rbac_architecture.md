# Antigravity Agent & E-Profile: Role-Based Access Control (RBAC) Architecture

This document defines the 5-tier security and privilege hierarchy for the E-Profile ecosystem and its integration with the Antigravity Agent. 

The core philosophy of this architecture is **Strict Decoupling of Host and Application**. The system must ensure that administrative application control does not accidentally grant underlying host operating system privileges. The agent operates on a "Zero Trust" model, strictly enforcing sandbox boundaries tailored to the authenticated user's exact tier.

---

## Level 5: Super Admin (System Owner)
The Super Admin is the ultimate authority of the ecosystem (the deployment owner). 

* **Definition & Purpose:** The Super Admin manages the underlying infrastructure, the host operating system (e.g., PythonAnywhere, AWS), and the core architectural logic of the agent and web server itself.
* **Agent Sandbox State:** **DISABLED** (`--dangerously-skip-permissions`).
* **Filesystem Access Scope:** Unrestricted. The agent is permitted to read, write, execute, and delete any file on the host OS, including configuration files, environment variables, and `.git` internal directories.
* **Model Configuration:** Unrestricted (Access to the heaviest, most capable reasoning models for complex core architectural rewrites).
* **Security Imperative:** The Super Admin must never be "held captive" by their own application. If the web UI fails, the Super Admin's agent access can repair the server from the OS level.

---

## Level 4: Admin (Application Manager)
The Admin has absolute control over the *business logic* and *data* of the application, but zero control over the host infrastructure.

* **Definition & Purpose:** The Admin manages users, databases, configurations, and the general operation of the application they are plugged into. They do not need (and are barred from) modifying the underlying host server or the agent's core source code.
* **Agent Sandbox State:** **ENABLED** (`--sandbox`).
* **Filesystem Access Scope:** Full Application Scope. The agent can modify templates, manage databases, and manipulate business logic files. However, OS-level execution, network port manipulation, and modifications to the core agent logic (`agent_manager.py`) are strictly blocked.
* **Model Configuration:** Access to advanced models for complex application-level data management and code generation.
* **Security Imperative:** Protects the host server. A compromised Admin account cannot be leveraged to execute an OS-level server wipe or install malicious system binaries.

---

## Level 3: Dev Team (Scoped Contributor)
The Dev Team consists of internal engineers assigned to specific modules or tickets.

* **Definition & Purpose:** Developers write, debug, and maintain code for specific features. Their access is compartmentalized strictly to their assigned tickets or project domains.
* **Agent Sandbox State:** **ENABLED & CHROOTED**.
* **Filesystem Access Scope:** Workspace-Restricted. The agent mathematically calculates the root of the developer's assigned workspace. If a developer is assigned to `/projects/echos_lab/`, the agent will physically reject any request to read or write to `/projects/core_engine/`. 
* **Model Configuration:** Access to standard pro-tier coding models for generating features and tests within their designated scopes.
* **Security Imperative:** Prevents lateral movement. A junior developer cannot accidentally (or maliciously) overwrite another team's project files or the core application settings.

---

## Level 2: Guest / Client (Plugin Creator)
Guests or Clients are external users permitted to extend the application for their own localized needs.

* **Definition & Purpose:** Clients can write custom integrations, themes, and plugins without needing internal developer resources.
* **Agent Sandbox State:** **HEAVILY RESTRICTED**.
* **Filesystem Access Scope:** Isolated Directory. The agent is confined exclusively to a designated `/custom/` or `/plugins/` directory. It has strictly **Read-Only** access to the application's core APIs (to understand how to interface with them) and **Write-Only** access to their localized plugin folder. 
* **Model Configuration:** Access to standard coding models optimized for safe, isolated integrations.
* **Security Imperative:** Client modifications must be guaranteed to never influence, degrade, or overwrite how the core application natively functions. 

---

## Level 1: Least Privilege (End User)
The End User is the standard consumer of the application.

* **Definition & Purpose:** Standard users interacting with the frontend application, requiring support, navigation assistance, or basic chatbot interactions.
* **Agent Sandbox State:** **LOCKED DOWN** (Execution & Write privileges fully revoked).
* **Filesystem Access Scope:** **None.** The agent has zero filesystem write capabilities. It cannot create, edit, or delete any files. It can only format data to trigger standardized internal webhooks (e.g., generating a JSON payload to submit a support ticket to the database).
* **Model Configuration:** Forced usage of high-speed, lightweight models (e.g., `flash`).
* **Security Imperative:** Prevents prompt injection attacks. Even if an end-user maliciously instructs the agent to "delete the server," the agent lacks the physical filesystem tools and permissions to execute the command, rendering the attack harmless. 

---

## Implementation Roadmap
To enforce this architecture, the current binary `is_admin` check inside the `AgentTaskManager` must be replaced with a tiered authorization payload. 

The host application (E-Profile) will authenticate the user and pass an un-forgeable token to the Agent declaring their exact Tier (1-5). The Agent will instantly lock its internal configuration boundaries based on that integer before processing a single prompt.
