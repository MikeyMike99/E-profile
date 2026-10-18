[//]: # (DOC_ID: SIRA-DEV-01_08 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 01.8: Problems Encountered: The Enterprise Pre-Authorization Wall (AADSTS65002)

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Problem Chapter**: [`01_07_NUITKA_COMPILATION_AND_BINARY_PACKAGING_TRAPS.md`](/docs/devlog/01_07_NUITKA_COMPILATION_AND_BINARY_PACKAGING_TRAPS)
- **Next: Source Evidence**: [`../02_SOURCE_EVIDENCE/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE.md`](/docs/devlog/02_01_SERVER_AND_AGENT_STREAMING_EVIDENCE)

---

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-1)

When navigating enterprise governance, organizations often attempt to leverage institutional cloud services (such as Microsoft 365 Copilot and Azure AD) to inherit enterprise compliance automatically.

As documented in DEVLOG Chapters 71 and 72, the Siraugga development team conducted headless authentication experiments with Microsoft Entra ID. This led to an insurmountable bureaucratic and technical wall: **Error `AADSTS65002`**.

This chapter analyzes why headless enterprise authentication failed and why it sparked Siraugga's decisive pivot to **Sovereign Local Intelligence**.

---

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-2)
## The Incident: Hitting Error `AADSTS65002`
[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-3)

### What Happened
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-3)
To test whether Siraugga could authenticate headlessly through an organizational Microsoft 365 Copilot tenant, the team built an OAuth 2.0 test harness using the Microsoft Authentication Library (`msal`). 

We initiated a headless Device Code Flow (`initiate_device_flow`):
```text
To sign in, use a web browser to open the page https://login.microsoft.com/device 
and enter the code FX83Z9QL to authenticate.
```

The user opened the link on their mobile device and successfully logged in with valid organizational credentials. However, the moment consent was submitted, Microsoft Entra ID abruptly rejected the token exchange:

```text
AADSTS65002: Consent between first party application '04b07795-8ddb-461a-bbee-02f9e1bf7b46' 
and first party resource '00000003-0000-0000-c000-000000000000' must be configured 
via preauthorization - applications owned and operated by Microsoft must get approval 
from the API owner before requesting tokens for that API.
```

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-4)
### Why It Happened: The Enterprise Illusion
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-4)
Many developers assume that because an employee or student can log into Microsoft Word or Copilot on the web, their scripts can programmatically consume that same intelligence via APIs. 

This is an illusion:
1. **Interactive SaaS vs. Headless APIs**: Microsoft web apps authenticate through pre-authorized internal Microsoft client IDs. External CLI tools cannot piggyback on those internal IDs.
2. **The Tenant Admin Wall**: To consume Graph or Copilot APIs headlessly, an IT administrator must manually provision an **Enterprise App Registration**, grant explicit delegated permissions (`Copilot.Data`), and approve **Tenant Admin Consent**.
3. **Bureaucratic Deadlock**: In large institutions, getting custom enterprise app registrations approved requires review boards, compliance filings, and weeks of administrative delay.

---

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-5)
## The Architectural Pivot: Sovereign Independence
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-5)

Rather than remaining chained to external enterprise bureaucracy, the team made a permanent architectural pivot: **Zero Cloud Entanglement**.

```text
+-------------------------------------------------------------------------------+
|                       The Fragile Cloud Paradigm                              |
|   App -> OAuth2 -> Entra ID (AADSTS65002) -> Tenant Admin -> $30/mo API      |
|   (Vulnerable to policy shifts, permission revocations, and network outages)  |
+-------------------------------------------------------------------------------+
                                        |
                                        v (Architectural Pivot)
+-------------------------------------------------------------------------------+
|                      The Sovereign Local Core (Siraugga)                      |
|   App -> Local Model Broker (Ollama / Local LLM) -> Raugus Semantic Mantrap   |
|   (100% offline, zero monthly API fees, zero admin consent requirements)      |
+-------------------------------------------------------------------------------+
```

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-6)
### The Three Sovereignty Pillars
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-6)
1. **Local-First Model Orchestration**: Siraugga prioritizes offline, self-hosted LLM endpoints running directly on local developer hardware.
2. **Self-Contained Security**: Rather than relying on cloud vendor firewalls, data classification is enforced locally via the **Raugus Resolver** and **Semantic Egress Firewall**.
3. **Clean-Room Defense**: Operating completely independent of enterprise cloud infrastructure guarantees 100% sovereign code ownership with zero intellectual property claims from institutional landlords.

---

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-7)
## Why Order Matters in Authentication Architecture
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-7)

1. **Verify Token Scopes Before Interactive Prompts**:
   - Applications must verify client registration authority *before* displaying device codes to users. Prompts that authenticate users only to fail at token grant waste human time and damage UX.
2. **Fallback to Local Stubs on Remote Auth Failure**:
   - In resilient software, authentication failures must immediately fall back to local offline stubs rather than terminating the application daemon.

---

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-8)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-9)

### Q: What is MSAL?
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-9)
**A:** MSAL stands for Microsoft Authentication Library. It is an official SDK used by developers to authenticate users against Microsoft Azure Active Directory (now called Microsoft Entra ID).

[//]: # (SECTION_ID: SIRA-DEV-01_08-SEC-10)
### Q: What is Device Code Flow?
[//]: # (SECTION_ID: SIRA-DOC-01_08-SEC-10)
**A:** It is an OAuth 2.0 flow designed for headless devices (like smart TVs, game consoles, or terminal scripts) that lack a web browser. The device displays a short code and a URL, allowing the user to approve the login from their smartphone or computer.
