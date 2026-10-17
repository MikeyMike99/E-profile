# OWASP Security Headers & CSP from Scratch

## 1. Architectural Role & Module Overview
Web developer applications often suffer from baseline OWASP vulnerabilities like Clickjacking, MIME-Sniffing, and Cross-Site Scripting because default frameworks do not attach HTTP security headers.

This guide details how to build `security_headers.py` and its accompanying CSP violation report collector in Quart from scratch. It injects anti-clickjacking headers, MIME-type locks, a balanced Content Security Policy, and an endpoint to capture browser violation reports.

```
+-------------------------------------------------------------+
|                      Client Web Request                     |
|                   GET / or GET /api/files                   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                  Quart Application Router                   |
|                  Generates Response Object                  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|               @app.after_request Middleware Hook            |
|   1. Injects X-Frame-Options: SAMEORIGIN                    |
|   2. Injects X-Content-Type-Options: nosniff                |
|   3. Injects Content-Security-Policy (Whitelist CDNs)       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                  Outbound Hardened Response                 |
|             (0 OWASP ZAP Baseline DAST Alerts!)             |
+-------------------------------------------------------------+
```

---

## 2. Complete Python Implementation
Save the following script as `secure_headers_app.py`:

```python
import json
from quart import Quart, Response, jsonify, request

app = Quart(__name__)

# Step 1: Universal Security Headers Middleware
@app.after_request
async def apply_security_headers(response: Response):
    """Applies strict HTTP defense headers to all outbound responses."""
    # 1. Anti-Clickjacking: Only allow framing by the exact same domain
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    # 2. Anti-MIME-Sniffing: Stop browsers from interpreting text as code
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # 3. Content Security Policy (CSP): Whitelist trusted CDNs & YouTube
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "frame-src 'self' https://www.youtube.com; "
        "report-uri /api/security/csp-report;"
    )
    response.headers['Content-Security-Policy'] = csp_policy

    return response

# Step 2: CSP Violation Report Ingestion Endpoint
@app.route('/api/security/csp-report', methods=['POST'])
async def csp_report():
    """Captures and logs CSP violation telemetry from the browser."""
    try:
        report_data = await request.get_json(force=True, silent=True)
        if report_data:
            blocked_uri = report_data.get('csp-report', {}).get('blocked-uri', 'unknown')
            print(f"[SECURITY ALERT] CSP Violation Detected! Blocked URI: {blocked_uri}")
    except Exception as e:
        print(f"[CSP REPORT ERROR] {e}")

    # Return HTTP 204 No Content for lightweight reporting
    return Response("", status=204)

# Sample Route
@app.route('/')
async def home():
    return "<h1>Secure DevCore Portal</h1><p>Inspected with hardened security headers.</p>"

if __name__ == "__main__":
    print("[SERVER] Starting hardened Quart app on 127.0.0.1:5000...")
    app.run(host="127.0.0.1", port=5000)
```

---

## 3. Why Order Matters in Security Middleware
1. **Apply Headers in `@after_request` Hook**: Registering headers on the outbound response hook ensures that even 404 or 500 error pages carry clickjacking protection.
2. **Include `report-uri` in Policy**: Adding the report directive ensures browsers alert you if an external dependency changes its hosting domain before users report bugs.
3. **Return HTTP 204 from Report Endpoint**: Returning an empty 204 response prevents browsers from spending CPU cycles parsing response bodies for telemetry pings.

---

## 4. Beginner Coder Q&A
**Q: What is MIME-sniffing?**  
A: When a server sends an image or text file, some browsers try to "guess" the file type by inspecting the content. If an attacker uploaded a malicious script disguised as a `.txt` file, the browser might execute it! `nosniff` completely prevents this.

**Q: Why whitelist `https://cdn.tailwindcss.com`?**  
A: Because Tailwind CSS provides dynamic, accessible styling for the portal. Whitelisting only trusted domains prevents untrusted third-party scripts from executing.

**Q: How do I test that headers are working?**  
A: Run `curl -I http://127.0.0.1:5000/` in your terminal. You will see `X-Frame-Options`, `X-Content-Type-Options`, and `Content-Security-Policy` in the response headers.
