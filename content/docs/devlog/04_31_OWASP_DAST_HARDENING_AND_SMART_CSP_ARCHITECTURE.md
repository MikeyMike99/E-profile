[//]: # (DOC_ID: SIRA-DEV-04_31 | VERSION: v1.0 | SCOPE: DEV)

# OWASP DAST Hardening & Smart CSP Architecture

[//]: # (SECTION_ID: SIRA-DEV-04_31-SEC-1)
## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_31-SEC-1)
Modern web-based developer portals face sophisticated browser-level attacks, including clickjacking, cross-site scripting (XSS), MIME-type confusion, and cross-site request forgery (CSRF). 

The OWASP DAST Hardening & Smart CSP Architecture (`security/security_headers.py`) eliminates OWASP ZAP baseline vulnerabilities (`[10020, 10021, 10038, 10063, 90004]`). It injects universal HTTP defense headers on every response, enforces a balanced Content Security Policy (CSP), and routes violation telemetry to the SIEM.

```
+-------------------------------------------------------------+
|                     Quart Response Object                   |
|                   (Outbound from Web Server)                |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              Security Headers Middleware Hook               |
|               (security/security_headers.py)                |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
     Clickjacking & MIME Headers     Smart Content Security Policy
     - X-Frame-Options: SAMEORIGIN   - default-src 'self'
     - X-Content-Type: nosniff       - Whitelists Tailwind/CDNJS
               |                             |
               +--------------+--------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Client Web Browser                     |
|           Enforces Sandbox Rules & Reports Violations       |
+-------------------------------------------------------------+
                              |
                     POST /api/security/csp-report
                              |
                              v
+-------------------------------------------------------------+
|                 SIEM Telemetry & Threat Logger              |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_31-SEC-2)
## 2. Remediated OWASP Baseline Vulnerabilities
[//]: # (SECTION_ID: SIRA-DOC-04_31-SEC-2)
1. **Clickjacking (Alert 10020)**: `X-Frame-Options: SAMEORIGIN` prevents malicious third-party websites from framing Siraugga in transparent iframes to hijack clicks.
2. **MIME-Sniffing (Alert 10021)**: `X-Content-Type-Options: nosniff` forces browsers to adhere strictly to declared MIME types, preventing executable code execution from uploaded text files.
3. **Cross-Site Scripting (Alert 10038)**: A scoped `Content-Security-Policy` limits script execution to the local origin and trusted CDNs (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`, `unpkg.com`).
4. **Cookie Tampering (Alert 10063)**: Session cookies enforce `HttpOnly` (blocking JavaScript access) and `SameSite=Strict` (blocking CSRF requests).

---

[//]: # (SECTION_ID: SIRA-DEV-04_31-SEC-3)
## 3. Smart CSP & Violation Reporting
[//]: # (SECTION_ID: SIRA-DOC-04_31-SEC-3)
Rather than a rigid policy that breaks stylesheets, the Smart CSP permits necessary CDNs while configuring `report-uri /api/security/csp-report`. If an unauthorized script attempt occurs, the browser submits a violation report, which is logged to `devcore_master.jsonl` as a security event.

---

[//]: # (SECTION_ID: SIRA-DEV-04_31-SEC-4)
## 4. Why Order Matters in Security Headers Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_31-SEC-4)
1. **Attach Headers in After-Request Middleware**: Enforcing headers at the after-request hook ensures that dynamic API endpoints, static assets, and 404 error responses all carry protective headers.
2. **Return HTTP 204 on Reports**: Acknowledging CSP violation reports with `204 No Content` minimizes network overhead for background browser telemetry.
3. **Restrict Red Team Trigger to Tier 5**: Limiting `/api/security/red-team-strike` to Super Admins prevents unauthorized users from overloading the server with automated penetration scans.

---

[//]: # (SECTION_ID: SIRA-DEV-04_31-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_31-SEC-5)
**Q: What is a Content Security Policy (CSP)?**  
A: An HTTP response header that tells the browser which domains are allowed to load scripts, styles, images, and fonts, blocking rogue external scripts.

**Q: Why is `unsafe-inline` needed in the CSP?**  
A: For local developer utility scripts and inline SVG icons. It is strictly constrained by `default-src 'self'`.

**Q: What happens if an external domain attempts to load a script?**  
A: The browser refuses to execute the script, prints an error in the developer console, and dispatches a JSON report to `/api/security/csp-report`.
