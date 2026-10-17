[//]: # (DOC_ID: SIRA-DOC-03_21 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Deployment Token Brute-Force & Auth Diagnostic Logs

## 1. Test Overview & Objectives
[//]: # (SECTION_ID: SIRA-DOC-03_21-SEC-1)
This test suite verifies the security, rate-limiting resistance, and credential isolation of the Headless Deployment Token protocol (`login.html` and `/api/auth/login`). It validates that valid tokens grant immediate access while automated brute-force attacks are halted by exponential rate limiting.

---

## 2. Test Execution Trace
[//]: # (SECTION_ID: SIRA-DOC-03_21-SEC-2)

```text
[AUTH-TEST-INIT] Booting server in headless mode...
[AUTH-TEST-INIT] Generated Ephemeral Deploy Token: AGY-DEPLOY-4F8A1B9C
[AUTH-TEST-INIT] Security rate limit policy: max 5 failed attempts per IP / 60 seconds.

--- TEST SCENARIO 1: Valid Token Authentication ---
[REQUEST] POST /api/auth/login -> {"token": "AGY-DEPLOY-4F8A1B9C"}
[SERVER-LOG] Token verified. Issuing session token: 'sess_9dfa81...'
[RESPONSE] HTTP 200 OK -> {"status": "success", "session_token": "sess_9dfa81..."}
[CLIENT] Storing token in sessionStorage. Navigating to '/'
[VERDICT] PASS - Legitimate developer authenticated successfully.

--- TEST SCENARIO 2: Unauthenticated WebSocket Hijack Attempt ---
[REQUEST] ws://127.0.0.1:5000/ws (Headers: None)
[SERVER-LOG] Handshake rejected: No valid deployment session token present.
[RESPONSE] HTTP 403 Forbidden (Connection closed immediately)
[VERDICT] PASS - Unauthenticated WebSocket access blocked.

--- TEST SCENARIO 3: Automated Brute-Force Simulation ---
[ATTACK] Script launching dictionary guesses from IP 192.168.1.105...
[ATTACK-1] POST /api/auth/login -> {"token": "AGY-DEPLOY-00000000"} -> HTTP 401 Unauthorized (Failure 1)
[ATTACK-2] POST /api/auth/login -> {"token": "AGY-DEPLOY-11111111"} -> HTTP 401 Unauthorized (Failure 2)
[ATTACK-3] POST /api/auth/login -> {"token": "AGY-DEPLOY-22222222"} -> HTTP 401 Unauthorized (Failure 3)
[ATTACK-4] POST /api/auth/login -> {"token": "AGY-DEPLOY-33333333"} -> HTTP 401 Unauthorized (Failure 4)
[ATTACK-5] POST /api/auth/login -> {"token": "AGY-DEPLOY-44444444"} -> HTTP 401 Unauthorized (Failure 5)
[RATE-LIMIT] IP 192.168.1.105 exceeded maximum failure threshold (5 attempts).
[SIEM-ALERT] CRITICAL: Brute-force threshold breached on /api/auth/login by 192.168.1.105. IP jailed for 300s.
[ATTACK-6] POST /api/auth/login -> {"token": "AGY-DEPLOY-4F8A1B9C"} (Even with correct token!)
[RESPONSE] HTTP 429 TOO MANY REQUESTS -> {"status": "error", "message": "IP temporarily banned. Try again in 300s."}
[VERDICT] PASS - Automated brute-force neutralized.
```

---

## 3. Security Metrics & Verification Summary
[//]: # (SECTION_ID: SIRA-DOC-03_21-SEC-3)

| Security Check | Expected Policy | Measured Behavior | Status |
| :--- | :--- | :--- | :--- |
| **Token Entropy** | 32-bit hex (4 bytes) | 4.29 billion possibilities | **PASS** |
| **Max Guess Allowance** | 5 attempts | Lockout on 6th attempt | **PASS** |
| **Lockout Duration** | 300 seconds | Verified active ban | **PASS** |
| **WebSocket Defense** | Zero unauthenticated pipes | HTTP 403 Handshake drop | **PASS** |

---

## 4. Why Order Matters in Authentication Defense
[//]: # (SECTION_ID: SIRA-DOC-03_21-SEC-4)
1. **Drop Unauthenticated WebSockets Before Accepting Frames**: Inspecting credentials during the HTTP upgrade prevents malicious actors from sending malicious JSON payloads into the server's event loop.
2. **Apply IP Jail Before Evaluating Token String**: Checking if the caller is banned before comparing the submitted token prevents timing attacks and spares CPU resources.
3. **Log Security Incidents Before Returning HTTP 429**: Writing the breach to the SIEM log before dispatching the response ensures forensic records exist even if the attacker terminates the socket early.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-03_21-SEC-5)
**Q: Why was Attempt 6 blocked even though it guessed the correct token?**  
A: Because the IP address was jailed after 5 failed attempts! Once jailed, the server rejects all requests from that IP address, preventing lucky late guesses.

**Q: Where is the deployment token shown to the developer?**  
A: It is printed directly in the server host terminal window when Siraugga starts up.

**Q: What is HTTP 429?**  
A: The standard HTTP status code for "Too Many Requests", informing the client that it has exceeded the rate limit.
