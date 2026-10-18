[//]: # (DOC_ID: SIRA-DEV-01_35 | VERSION: v1.0 | SCOPE: DEV)

# OWASP DAST Vulnerabilities & CSP Reporting Traps

[//]: # (SECTION_ID: SIRA-DEV-01_35-SEC-1)
## 1. The Problem: The Standard Web Framework Blindspot
[//]: # (SECTION_ID: SIRA-DOC-01_35-SEC-1)
Default Python web frameworks (such as Flask or Quart) prioritize developer convenience over hardened defense. Out of the box, responses do not include modern HTTP security headers, leaving portals vulnerable to browser-level exploits.

When automated Dynamic Application Security Testing (DAST) suites (like OWASP ZAP) scan the application, they flag critical baseline security warnings:
- **Alert 10020**: Missing Anti-Clickjacking Header (`X-Frame-Options`).
- **Alert 10021**: Missing `X-Content-Type-Options: nosniff` (MIME-Sniffing vulnerability).
- **Alert 10038**: Content Security Policy (CSP) Not Set.
- **Alert 10063**: Missing `HttpOnly` or `SameSite` flags on session cookies.

```
+-------------------------------------------------------------+
|             Untrusted External Malicious Website            |
|       Embeds Siraugga in hidden 1x1 pixel <iframe>          |
+-------------------------------------------------------------+
                              |
                     CLICKJACKING ATTACK
                     (X-Frame-Options Missing)
                              |
                              v
+-------------------------------------------------------------+
|              User clicks 'Download' on malicious site       |
|    - Clicks actually pass through to hidden Siraugga prompt |
|    - Malicious terminal commands executed unknowingly!      |
+-------------------------------------------------------------+
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_35-SEC-2)
## 2. The Rigid CSP Breakage Trap
[//]: # (SECTION_ID: SIRA-DOC-01_35-SEC-2)
To fix Alert 10038, developers often add a rigid `default-src 'self'` policy. However, this causes severe UI breakage: Tailwind CSS CDNs fail to load, FontAwesome icons disappear, and markdown parsers (`turndown.js`) are blocked, rendering the portal visually unreadable.

Furthermore, configuring a CSP reporting endpoint without rate limiting allows malicious actors to flood `/api/security/csp-report` with millions of fake violation packets, exhausting server logs.

---

[//]: # (SECTION_ID: SIRA-DEV-01_35-SEC-3)
## 3. The Solution: Smart CSP & Automated DAST Remediation
[//]: # (SECTION_ID: SIRA-DOC-01_35-SEC-3)
Siraugga resolved this with the Security Headers Middleware (`security/security_headers.py`):
1. **Universal Security Headers**: Every Quart response automatically injects `X-Frame-Options: SAMEORIGIN` and `X-Content-Type-Options: nosniff`.
2. **Smart Content Security Policy**: Allows local execution while explicitly whitelisting trusted CDN domains (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`, `unpkg.com`, `www.youtube.com`).
3. **Bounded CSP Reporting**: Violations are submitted to `/api/security/csp-report`, scrubbed, and logged to the SIEM with strict rate limits.
4. **Red Team Strike Endpoint**: An administrative endpoint (`/api/security/red-team-strike`) triggers automated DAST scans to continuously verify compliance.

---

[//]: # (SECTION_ID: SIRA-DEV-01_35-SEC-4)
## 4. Why Order Matters in Security Headers
[//]: # (SECTION_ID: SIRA-DOC-01_35-SEC-4)
1. **Apply Headers in `@app.after_request` Hook**: Injecting headers in the universal post-response hook guarantees that 404, 500, and error pages also carry protective headers.
2. **Whitelist Known CDNs Before Blocking Nonce**: Carefully scoping CDN allowances prevents breaking client stylesheets while still blocking unapproved script execution.
3. **Throttle CSP Violation Reports**: Rate limiting `/api/security/csp-report` prevents Denial-of-Service attacks targeting log storage.

---

[//]: # (SECTION_ID: SIRA-DEV-01_35-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_35-SEC-5)
**Q: What is Clickjacking?**  
A: A malicious technique where an attacker tricks a user into clicking invisible buttons by loading your web application inside a transparent iframe on their website.

**Q: What does `X-Content-Type-Options: nosniff` do?**  
A: It prevents browsers from guessing the file type. For example, it stops a browser from executing an uploaded `.txt` or `.png` file as executable JavaScript.

**Q: What does `X-Frame-Options: SAMEORIGIN` achieve?**  
A: It tells browsers that your website can only be framed by pages with the exact same domain, completely neutralizing clickjacking attacks.
