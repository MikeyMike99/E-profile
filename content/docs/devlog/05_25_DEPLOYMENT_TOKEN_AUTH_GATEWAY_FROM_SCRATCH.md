[//]: # (DOC_ID: SIRA-DOC-05_25 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Deployment Token Auth Gateway from Scratch

## 1. Architectural Role & Module Overview
[//]: # (SECTION_ID: SIRA-DOC-05_25-SEC-1)
Deploying an autonomous AI web portal across a local network or remote VM without authentication creates an open door for unauthorized code execution.

This guide details how to build a complete, self-contained Deployment Token Authentication Gateway (`auth_gateway.py`). On boot, it generates an ephemeral deployment token printed exclusively to the terminal, requires clients to authenticate via a clean login challenge, enforces rate limiting, and issues secure session keys.

```
+-------------------------------------------------------------+
|                     Terminal Host Boot                      |
|          Generates Ephemeral Token: AGY-DEPLOY-XXXX         |
+-------------------------------------------------------------+
                              |
                     Client Connects (HTTP)
                              |
               +--------------+--------------+
               |                             |
       Session Valid?               No Valid Session
               |                             |
               v                             v
       Serve Dashboard                  Serve login.html
                                             |
                                    Submit Deploy Token
                                             |
                                             v
                                  Validate & Rate Limit:
                                  - 5 fails -> 300s ban
                                  - Match? -> Issue Session
```

---

## 2. Complete Python Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_25-SEC-2)
Save the following script as `auth_gateway.py`:

```python
import time
import secrets
from collections import defaultdict
from quart import Quart, request, jsonify, redirect, make_response

app = Quart(__name__)

# Step 1: Generate Ephemeral In-Memory Token on Boot
RAW_TOKEN = secrets.token_hex(4).upper()
DEPLOY_TOKEN = f"AGY-DEPLOY-{RAW_TOKEN}"
print("\n" + "="*56)
print(f"  DEPLOYMENT TOKEN: {DEPLOY_TOKEN}")
print("  Enter this token in your browser to authenticate.")
print("="*56 + "\n")

# In-memory storage for active sessions & rate limiting
ACTIVE_SESSIONS = set()
FAILED_ATTEMPTS = defaultdict(list)
BANNED_IPS = {}

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Deploy Authentication</title></head>
<body style="background:#0f172a;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;">
  <form id="f" style="background:#1e293b;padding:30px;border-radius:10px;width:320px;">
    <h2>Terminal Auth</h2>
    <p style="font-size:0.85rem;color:#94a3b8;">Enter the deployment token shown in your terminal.</p>
    <input type="password" id="t" placeholder="AGY-DEPLOY-XXXX" style="width:100%;padding:10px;margin-bottom:15px;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:6px;" required>
    <div id="err" role="alert" style="color:#ef4444;font-size:0.85rem;margin-bottom:10px;display:none;"></div>
    <button type="submit" style="width:100%;padding:10px;background:#0d9488;color:#fff;font-weight:bold;border:none;border-radius:6px;cursor:pointer;">Authenticate</button>
  </form>
  <script>
    document.getElementById('f').onsubmit = async (e) => {
      e.preventDefault();
      const err = document.getElementById('err');
      err.style.display = 'none';
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ token: document.getElementById('t').value })
      });
      const data = await resp.json();
      if (data.status === 'success') {
        window.location.reload();
      } else {
        err.textContent = data.message;
        err.style.display = 'block';
      }
    };
  </script>
</body>
</html>
"""

def is_ip_banned(ip: str) -> bool:
    """Checks if an IP is currently serving an active lockout."""
    if ip in BANNED_IPS:
        if time.time() < BANNED_IPS[ip]:
            return True
        del BANNED_IPS[ip]
    return False

@app.route('/')
async def index():
    token = request.cookies.get('session_token')
    if token in ACTIVE_SESSIONS:
        return "<h1>Welcome to the Protected Workspace Dashboard!</h1>"
    return LOGIN_HTML

@app.route('/api/auth/login', methods=['POST'])
async def login():
    ip = request.remote_addr or '127.0.0.1'
    if is_ip_banned(ip):
        return jsonify({"status": "error", "message": "Too many failed attempts. IP banned for 300s."}), 429

    data = await request.get_json()
    submitted = (data.get('token') or '').strip().upper()

    # Constant-time comparison prevents timing attacks
    if secrets.compare_digest(submitted, DEPLOY_TOKEN):
        session_id = secrets.token_urlsafe(32)
        ACTIVE_SESSIONS.add(session_id)
        resp = jsonify({"status": "success"})
        resp.set_cookie('session_token', session_id, httponly=True, samesite='Strict')
        return resp
    else:
        now = time.time()
        # Track failures in a 60-second window
        FAILED_ATTEMPTS[ip] = [t for t in FAILED_ATTEMPTS[ip] if now - t < 60]
        FAILED_ATTEMPTS[ip].append(now)

        if len(FAILED_ATTEMPTS[ip]) >= 5:
            BANNED_IPS[ip] = now + 300  # 5-minute ban
            return jsonify({"status": "error", "message": "Limit exceeded. IP locked out for 300 seconds."}), 429

        return jsonify({"status": "error", "message": "Invalid token. Please check terminal."}), 401

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
```

---

## 3. Why Order Matters in Authentication Processing
[//]: # (SECTION_ID: SIRA-DOC-05_25-SEC-3)
1. **Check IP Lockout Before Evaluating Token**: Evaluating jail status before string comparison stops attackers from spamming the server CPU.
2. **Use `secrets.compare_digest`**: Comparing strings in constant time eliminates microsecond variations that could reveal correct characters.
3. **Set `httponly=True` on Cookies**: Forbidding JavaScript access to session cookies protects credentials from Cross-Site Scripting (XSS) extraction.

---

## 4. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_25-SEC-4)
**Q: What does `httponly=True` mean?**  
A: It instructs the browser that JavaScript code cannot read or modify the cookie, protecting the session from rogue web scripts.

**Q: Where is the session token stored?**  
A: In the server's `ACTIVE_SESSIONS` memory set. If the server restarts, all sessions expire automatically, enforcing complete ephemerality.

**Q: Why use `defaultdict(list)` for failed attempts?**  
A: It automatically creates a new list for each unseen IP address without raising `KeyError`, making rate limiting code clean and concise.
