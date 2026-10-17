[//]: # (DOC_ID: SIRA-DOC-04_23 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Headless Deployment Token Security Architecture

## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_23-SEC-1)
When Siraugga runs headlessly on a remote server, local development VM, or cloud container, the web server must accept connections across local network boundaries. If the portal is unprotected, any unauthorized device on the local network can open the browser and execute arbitrary code.

The Headless Deployment Token Security Architecture provides an ephemeral, zero-configuration authentication barrier without saving static passwords to disk.

```
+-------------------------------------------------------------+
|                     Headless Host Boot                      |
|           Generates In-Memory Token: AGY-DEPLOY-XXXX        |
|             Prints to Terminal Console ONLY                 |
+-------------------------------------------------------------+
                              |
                     Incoming HTTP Traffic
                              |
               +--------------+--------------+
               |                             |
     Has Session Cookie?           No Valid Session
               |                             |
               v                             v
       Access Granted               Serve login.html
     (Dashboard & WS)               (Enter Deploy Token)
                                             |
                                             v
                                    POST /api/auth/login
                                             |
                               +-------------+-------------+
                               |                           |
                            Match?                     Mismatch
                               |                           |
                               v                           v
                      Issue Session Token         Increment IP Counter
                      Redirect to /               (5 Fails -> 300s Ban)
```

---

## 2. Ephemeral In-Memory Token Lifecycle
[//]: # (SECTION_ID: SIRA-DOC-04_23-SEC-2)
1. **Creation on Boot**: On startup, `server.py` invokes `secrets.token_hex(4).upper()` to create an 8-character token (e.g., `AGY-DEPLOY-9E2B1F4A`). It is stored purely in volatile process RAM.
2. **Console Output**: The token is printed directly to the server's standard output, ensuring only users with direct physical or SSH terminal access can view it.
3. **Session Token Minting**: Upon successful entry in `login.html`, the backend mints a high-entropy session key (`secrets.token_urlsafe(32)`) valid for the duration of the browser tab.

---

## 3. Defense Against Automated Brute-Force
[//]: # (SECTION_ID: SIRA-DOC-04_23-SEC-3)
Because an 8-character hex token has 4.29 billion permutations, an attacker cannot guess it manually. To stop automated network scripts, the architecture enforces IP-based rate limiting:
- **Threshold**: 5 failed token submissions from an IP address within 60 seconds.
- **Action**: Immediate HTTP 429 response, SIEM security alert logged, and client IP blocked for 300 seconds.

---

## 4. Why Order Matters in Headless Auth Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_23-SEC-4)
1. **Verify Token During HTTP Upgrade**: Authentication must be validated during the initial HTTP handshake before upgrading to a persistent WebSocket.
2. **Log Security Event Before Dropping Socket**: The SIEM must record failed attempts immediately to preserve the IP audit trail before terminating the connection.
3. **Purge Session Tokens on Process Termination**: Because the tokens live strictly in memory, restarting the server instantly revokes all active browser sessions.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_23-SEC-5)
**Q: Why not just use a password in a `.env` file?**  
A: Static passwords in `.env` files frequently get committed to GitHub by accident or ingested into AI model training data. Ephemeral tokens in RAM cannot leak via Git.

**Q: What if I lose the terminal window where the token was printed?**  
A: Simply stop and restart the server (`python3 core/server.py`). It will generate and print a brand-new token in 100 milliseconds.

**Q: Can this be used alongside HTTPS?**  
A: Yes! When deploying over public networks, running behind a reverse proxy (like Nginx or Caddy) with TLS encryption provides complete end-to-end security.
