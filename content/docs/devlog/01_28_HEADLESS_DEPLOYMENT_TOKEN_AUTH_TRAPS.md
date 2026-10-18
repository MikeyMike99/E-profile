[//]: # (DOC_ID: SIRA-DEV-01_28 | VERSION: v1.0 | SCOPE: DEV)

# Headless Deployment Token Authentication Traps

[//]: # (SECTION_ID: SIRA-DEV-01_28-SEC-1)
## 1. The Problem: Unprotected Headless Endpoints
[//]: # (SECTION_ID: SIRA-DOC-01_28-SEC-1)
When developers launch Siraugga on a remote server, secondary workstation, or inside a Docker container, the service must bind to network interfaces so client browsers can connect.

However, binding an autonomous agent engine to `0.0.0.0` or a local area network (LAN) creates severe security risks. Any machine on the subnet can open `http://<host-ip>:5000`, gain immediate access to the prompt box, and execute arbitrary terminal commands with the server's OS privileges.

```
+-------------------------------------------------------------+
|             Headless Linux / VM Host Server                 |
|             Quart Bound to 0.0.0.0:5000                     |
+-------------------------------------------------------------+
                              |
                     Unsecured LAN Traffic
                              |
               +--------------+--------------+
               |                             |
      Legitimate Developer          Unauthorized LAN Device
      Attempts Connection           Opens Browser -> Root Control!
```

---

[//]: # (SECTION_ID: SIRA-DEV-01_28-SEC-2)
## 2. The Authentication Trap
[//]: # (SECTION_ID: SIRA-DOC-01_28-SEC-2)
Initial attempts to secure the portal relied on basic HTTP passwords saved in static configuration files. This introduced two fatal traps:
1. **Config File Leaks**: Hardcoded passwords in `.env` or `config.json` frequently got committed to Git repositories or ingested by AI prompt contexts.
2. **Infinite Brute-Force**: Without an authentication challenge screen and rate limiter, attackers could script thousands of automated password guesses per second against `/ws`.

---

[//]: # (SECTION_ID: SIRA-DEV-01_28-SEC-3)
## 3. The Solution: Ephemeral Terminal Deployment Tokens
[//]: # (SECTION_ID: SIRA-DOC-01_28-SEC-3)
Siraugga resolved this with the Headless Deployment Token Protocol (`sandbox/templates/login.html`):
1. **Ephemeral Token Generation**: When the server boots headlessly, it prints an ephemeral token directly to the host console:
   ```text
   ====================================================
   DEPLOYMENT AUTHENTICATION REQUIRED
   Token: AGY-DEPLOY-8F4C2A1E
   Visit http://127.0.0.1:5000/ to authenticate client.
   ====================================================
   ```
2. **Challenge Screen Gatekeeper**: Unauthenticated HTTP requests are redirected to `login.html`.
3. **Session Token Issuance**: Submitting the matching token issues an in-memory session token that unlocks the WebSocket and dashboard routes.
4. **Brute-Force Lockout**: Five consecutive invalid token submissions trigger a 5-minute IP firewall ban.

---

[//]: # (SECTION_ID: SIRA-DEV-01_28-SEC-4)
## 4. Why Order Matters in Headless Security
[//]: # (SECTION_ID: SIRA-DOC-01_28-SEC-4)
1. **Generate Token in Memory Before Binding Socket**: The server must generate the deployment token before accepting network traffic so no unauthenticated window exists.
2. **Validate Auth Token Before Upgrading WebSocket**: The server must verify authentication headers during the HTTP upgrade handshake; once a WebSocket is established, connection-level defense is bypassed.
3. **Enforce Rate Limiting Before Token Comparison**: Rate limiting counters must be updated before cryptographic string comparison to throttle timing attacks.

---

[//]: # (SECTION_ID: SIRA-DEV-01_28-SEC-5)
## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-01_28-SEC-5)
**Q: Why generate a new token on every server restart?**  
A: Ephemerality ensures that even if a token is exposed, it becomes invalid as soon as the server process terminates.

**Q: Can attackers steal the token from the terminal?**  
A: Only if they already possess root shell access to the host machine. If an attacker has host shell access, your system is already fully compromised.

**Q: Does `login.html` work with screen readers?**  
A: Yes! It uses semantic HTML form controls, explicit `<label>` elements, and an `aria-live` region for error announcements.
