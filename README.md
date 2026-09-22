# E-Profile Architecture: System Admin Hub

Welcome to the central repository for the **Secure Cybersecurity E-Portfolio**, developed and maintained by **Michael Robberts**. 
This application serves as an interactive resume, technical portfolio, and a live demonstration of core cybersecurity principles merged with native accessibility. 

The application is built completely from scratch using Python (Flask) for the backend and pure HTML/CSS for the frontend, ensuring absolute control over routing, security, and the DOM structure. 

## 🎯 The Mission
The core philosophy driving this application is that **accessibility and security are not mutually exclusive**. This portfolio utilizes flawless ARIA landmarks, semantic HTML structures, and screen-reader-friendly logic to prove that high-end, dynamic, and secure web applications can be universally accessible from day one. 

## 📂 Core Modules (Tabs)
The portfolio is divided into several primary modules, dynamically rendered from `.md` and `.json` data files.

- **Home**: The public landing page. Provides the core elevator pitch, mission statement, and social connection points. 
- **Bio**: Deep dive into the architect's background, journey, and technical philosophy.
- **Projects**: The interactive engine room. Hosts deployable Python applications (such as the *Echos Engine* and *High Precision Calibrator*) running natively in the browser via backend Flask Blueprints.
- **Blog & Field Notes**: A dynamically sorted technical journal detailing vulnerability write-ups, infrastructure builds, and dev logs.
- **Certifications**: A responsive gallery hosting verified digital badges (CompTIA A+, Security+, Python) and downloadable certificates.
- **Admin**: The restricted command center for managing the application's configuration.

## 🔐 Security & Access Control
This platform employs a rigid, multi-tiered security model built on a custom session-cookie architecture:

1. **The Restricted Public State**
   - By default, general visitors have extremely limited clearance. The Home tab is visible, but all detailed modules (Bio, Projects, Blog, Certifications) are securely locked (`HTTP 403 Forbidden` / UI `[LOCKED 🔒]`).
   - Access is granted via a "Magic Link" token system (an Easter egg hidden off-site on LinkedIn), which generates a secure, one-time payload to unlock the guest profile. 

2. **Role-Based Access Control (RBAC)**
   - **Guest Profile**: Can view tabs but has no administrative power. 
   - **Employer Role (`is_employer`)**: Specially provisioned profiles designed for recruiters and hiring managers. They automatically bypass the public locks and can immediately view all restricted content natively.
   - **System Admin (`is_admin`)**: The root authority. Has complete access to all content, the ability to execute backend scripts, and full control over the Admin Dashboard.

## ⚙️ Administrative Capabilities
The System Admin profile has access to the `/admin` routing panel (`manage_profiles.html`), providing the following core functionalities:
- **Identity Provisioning**: Generate new magic links, assign access PINs, and designate `Employer` or `Admin` privileges to new users.
- **Profile Management**: Reset passwords, edit access permissions, or permanently terminate profiles. 
- **Git Synchronization**: The backend utilizes a built-in file synchronization tool to check local disk mismatches, quarantine modified agent files, and execute `git commit` / `git pull` updates directly from the UI without touching the CLI.
- **System Health Monitor**: Track data stream logs and active user login attempts in real-time. 

## 🛠️ Technology Stack
- **Backend**: Python 3.10+, Flask, Werkzeug, Pathlib 
- **Frontend**: Native HTML5, Custom CSS3 Variables, Vanilla JS, Jinja2 Templating
- **Content Engine**: Python `markdown` library (Dynamic file-parsing instead of a traditional SQL database)

## 🧠 AI Integration (Siraugga)
This application hosts a fully embedded, Zero-Trust AI assistant designed to serve as both an interactive demo for visitors and a root-level developer tool for the system administrator. 

To govern this advanced AI architecture, the repository adheres strictly to the **Zero-Trust RBAC Textbook** (now officially housed and maintained in the root `DevCore` architecture repository). This textbook outlines the 27 Core Pillars of our Enterprise Security Architecture, including:

- **The Immutable Host Doctrine:** Utilizing Docker `read_only` and RAM-disks (`tmpfs`) to prevent AI Data Remanence and Remote Code Execution persistence.
- **The Semantic Firewall:** Intercepting all prompts through an Evaluator LLM middleware to mathematically neutralize Prompt Injection and Jailbreaks.
- **Ephemeral UI Plugins:** Using Iframe Sandboxing and Capability Bootstrapping to allow the AI to safely generate dynamic UI (like Exam Portals and Accessible YouTube Media Players) without risking XSS or Template Corruption.
- **Subagent Zombie Reaping:** Issuing `SIGKILL` commands to entire Linux Process Groups (`os.killpg`) to eradicate orphaned AI subagents and prevent Resource Exhaustion (Denial of Wallet).

### The "Dual-Reality" Security Sandbox
Siraugga dynamically adjusts its absolute filesystem boundaries based on the user's cryptographic backend session:
1. **The Playground (Visitors)**: Unprivileged users are trapped in a strict sub-folder (`/playground/`). The backend's canonical path resolution mathematically blocks the AI from traversing out of the playground to see or modify the core website code.
2. **God-Mode (Root Admin)**: When accessed via the admin-exclusive pop-out shortcut, the AI detects the master session (Tier 5) and completely bypasses the Semantic Firewall and path restrictions, elevating its anchor to the absolute root of the directory for unrestricted deployment power.

copy_right 