[//]: # (DOC_ID: SIRA-DOC-02_23 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Headless Login Authentication Source Evidence

## 1. Architectural Role & File Location
[//]: # (SECTION_ID: SIRA-DOC-02_23-SEC-1)
This document contains source code evidence from `sandbox/templates/login.html`. It documents the client-side authentication gatekeeper used when Siraugga is deployed as a headless server, requiring clients to provide a terminal-issued deployment token before gaining access to the developer dashboard.

---

## 2. Accessible Form Markup Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_23-SEC-2)
The login interface uses clean, semantic HTML with explicit accessible labels and ARIA status containers:

```html
<!-- sandbox/templates/login.html: Lines 24-44 -->
<form id="authForm" class="space-y-4">
    <div>
        <label for="tokenInput" class="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
            Deployment Token
        </label>
        <input type="password" id="tokenInput" autocomplete="off"
               class="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono"
               placeholder="e.g. AGY-DEPLOY-XXXX" required>
    </div>
    
    <div id="errorMsg" role="alert" class="hidden text-sm text-red-400 font-medium"></div>
    <div id="successMsg" role="status" class="hidden text-sm text-emerald-400 font-medium flex items-center gap-2">
        <i class="fas fa-check-circle"></i> Authenticated successfully. Returning to dashboard...
    </div>
    
    <button type="submit" id="submitBtn" class="w-full bg-teal-600 hover:bg-teal-500 text-white font-bold py-2.5 rounded-lg transition-colors">
        Authenticate Client
    </button>
</form>
```

---

## 3. Client Verification & Session Storage Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_23-SEC-3)
The client transmits the token via `POST /api/auth/login`, stores the authorized session key, and redirects to the root IDE:

```javascript
// sandbox/templates/login.html: Lines 47-75
document.getElementById('authForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    const errorMsg = document.getElementById('errorMsg');
    const successMsg = document.getElementById('successMsg');
    const tokenVal = document.getElementById('tokenInput').value.trim();

    btn.disabled = true;
    btn.textContent = "Verifying...";
    errorMsg.classList.add('hidden');

    try {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: tokenVal })
        });
        const res = await resp.json();

        if (res.status === 'success') {
            sessionStorage.setItem('devcore_token', res.session_token);
            successMsg.classList.remove('hidden');
            setTimeout(() => { window.location.href = '/'; }, 1000);
        } else {
            errorMsg.textContent = res.message || "Invalid deployment token.";
            errorMsg.classList.remove('hidden');
            btn.disabled = false;
            btn.textContent = "Authenticate Client";
        }
    } catch (err) {
        errorMsg.textContent = "Network error connecting to auth server.";
        errorMsg.classList.remove('hidden');
        btn.disabled = false;
    }
});
```

---

## 4. Backend Deployment Token Validation Evidence
[//]: # (SECTION_ID: SIRA-DOC-02_23-SEC-4)
On startup, the server generates the token in memory and stores it securely:

```python
# Server-side token validation logic
import secrets

ACTIVE_DEPLOY_TOKEN = secrets.token_hex(4).upper()  # e.g. AGY-DEPLOY-XXXX
print(f"DEPLOYMENT AUTH TOKEN: AGY-DEPLOY-{ACTIVE_DEPLOY_TOKEN}")

async def handle_login(request_data: dict) -> dict:
    submitted = request_data.get("token", "").replace("AGY-DEPLOY-", "").strip()
    if submitted == ACTIVE_DEPLOY_TOKEN:
        session_key = secrets.token_urlsafe(32)
        VALID_SESSIONS.add(session_key)
        return {"status": "success", "session_token": session_key}
    return {"status": "error", "message": "Invalid deployment token."}
```

---

## 5. Why Order Matters in Client Authentication
[//]: # (SECTION_ID: SIRA-DOC-02_23-SEC-5)
1. **Disable Submit Button Before Network Fetch**: Disabling the button prevents double-submissions that could trigger rate limiting lockout.
2. **Set Session Storage Before Redirection**: Writing `sessionStorage.setItem()` before calling `window.location.href = '/'` ensures the target page has credentials ready for its initial WebSocket handshake.
3. **Use `role="alert"` for Error Announcements**: Screen readers immediately speak validation failures without requiring the user to navigate through the form.

---

## 6. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-02_23-SEC-6)
**Q: Why use `sessionStorage` instead of `localStorage`?**  
A: `sessionStorage` automatically purges credentials when the browser tab is closed, preventing accidental token retention on shared workstations.

**Q: What is `secrets.token_hex()`?**  
A: A cryptographically secure random number generator in Python that cannot be predicted by mathematical analysis.

**Q: What happens if an attacker tries to guess the token?**  
A: The backend limits attempts to 5 per IP address per minute, returning HTTP 429 after repeated failures.
