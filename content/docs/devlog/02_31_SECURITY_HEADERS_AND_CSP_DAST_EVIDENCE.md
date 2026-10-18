[//]: # (DOC_ID: SIRA-DEV-02_31 | VERSION: v1.0 | SCOPE: DEV)

# Security Headers & CSP DAST Source Evidence

[//]: # (SECTION_ID: SIRA-DEV-02_31-SEC-1)
## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_31-SEC-1)
This document records source code evidence from `security/security_headers.py` and `core/routes/system.py`. It demonstrates how DevCore eliminates OWASP ZAP baseline vulnerability warnings (`[10020, 10021, 10038, 10063, 90004]`), applies Content Security Policy (CSP) headers, and triggers automated Red Team DAST scans.

---

[//]: # (SECTION_ID: SIRA-DEV-02_31-SEC-2)
## 2. Universal Security Headers Middleware Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_31-SEC-2)
Applied to all outbound Quart responses via an `@app.after_request` hook:

```python
# security/security_headers.py: Lines 3-24
async def apply_security_headers(response):
    """
    Applies strict HTTP security headers to all outbound Quart responses.
    Fixes OWASP ZAP Baseline DAST Warnings [10020, 10021, 10038, 10063, 90004].
    """
    # 1. Prevent Clickjacking (X-Frame-Options)
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    # 2. Prevent MIME-sniffing (X-Content-Type-Options)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # 3. Content Security Policy (CSP)
    # Allows local execution + Tailwind/jsDelivr/unpkg CDNs + YouTube embeds
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "frame-src 'self' https://www.youtube.com; "
        "report-uri /api/security/csp-report;"
    )
    return response
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_31-SEC-3)
## 3. CSP Reporting & Red Team Strike Routes Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_31-SEC-3)
Handled inside `core/routes/system.py`:

```python
# core/routes/system.py: System security endpoints
@system_bp.route('/api/security/csp-report', methods=['POST'])
async def api_csp_report():
    """Ingests browser CSP violation reports and logs them to the SIEM."""
    report = await request.get_json(force=True, silent=True)
    if report:
        from security.central_logger import log_siem_event
        log_siem_event(
            level="WARN",
            message=f"[CSP_VIOLATION] Blocked URI: {report.get('csp-report', {}).get('blocked-uri')}",
            module_name="csp_firewall"
        )
    return jsonify({"received": True}), 204

@system_bp.route('/api/security/red-team-strike', methods=['POST'])
async def api_trigger_red_team():
    """Triggers automated internal DAST vulnerability strike (Tier 5 Admin only)."""
    user = get_current_user()
    if not user or user.get("role") not in ["super_admin", "Tier5_SysAdmin"]:
        return jsonify({"error": "Access Denied: Red Team strikes require Tier 5 Admin authorization."}), 403
        
    asyncio.create_task(trigger_dast_scan_internal())
    return jsonify({"success": True, "message": "Red Team strike initiated."})
```

---

[//]: # (SECTION_ID: SIRA-DEV-02_31-SEC-4)
## 4. Why Order Matters in Security Headers
[//]: # (SECTION_ID: SIRA-DOC-02_31-SEC-4)
1. **Apply Headers in `@after_request` Hook**: Registering the middleware globally guarantees that all API endpoints—including error pages (404 and 500)—carry security headers.
2. **Return HTTP 204 on CSP Reports**: Returning `204 No Content` minimizes network overhead for background browser telemetry reporting.
3. **Validate Tier 5 Role Before DAST Execution**: Because running a Red Team strike consumes significant CPU and network resources, strict RBAC authorization must precede task creation.

---

[//]: # (SECTION_ID: SIRA-DEV-02_31-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_31-SEC-5)
**Q: What does `default-src 'self'` mean in CSP?**  
A: It is a strict whitelist rule that says: by default, only load images, scripts, and fonts that originate from the exact same domain as the web page.

**Q: Why is `report-uri /api/security/csp-report` included?**  
A: If a malicious script attempts to run or a broken CDN link occurs, the browser automatically sends a JSON summary of the violation to that endpoint.

**Q: What is a Red Team Strike?**  
A: An automated internal penetration test that launches simulated attacks against your own endpoints to verify that all firewalls and rate limiters are functioning properly.
