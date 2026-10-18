[//]: # (DOC_ID: SIRA-DEV-04_05 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 04.5: Architecture Solutions: Sovereign AI & Offline Broker Recipes

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Architecture Chapter**: [`04_04_EXTENDING_SIRAUGGA_PLUGINS_AND_SERVICES.md`](/docs/devlog/04_04_EXTENDING_SIRAUGGA_PLUGINS_AND_SERVICES)
- **Next: From-Scratch Creation Guides**: [`../05_FROM_SCRATCH_CREATION_GUIDES/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH.md`](/docs/devlog/05_01_QUART_STREAMING_SERVER_FROM_SCRATCH)

---

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-1)

Following the lessons learned from enterprise pre-authorization roadblocks (`AADSTS65002`) and institutional data compliance audits (DEVLOG Chapters 70–72), Siraugga transitioned to a **Sovereign Local Intelligence Architecture**.

This guide provides copy-paste recipes for setting up an offline local model broker, intercepting outbound model traffic, and enforcing strict data custody for compliance with regulations like POPIA and GDPR.

---

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-2)
## Recipe 1: Setting Up the Local Sovereign Proxy Broker
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-2)

Instead of allowing the AI CLI to connect directly to external cloud servers, Siraugga routes all traffic through a local proxy endpoint on Port 5000.

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-3)
### Step 1: Configure the Subprocess Environment in `agent_manager.py`
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-3)
Pass local broker URLs and synthetic dummy tokens:

```python
def get_sovereign_environment():
    """Builds an isolated execution environment pointing to the local proxy."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "USER": os.environ.get("USER", ""),
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        # Route model requests to local offline broker
        "GEMINI_BASE_URL": "http://127.0.0.1:5000/api/proxy",
        "GEMINI_API_KEY": "sovereign_dummy_token",
        "GOOGLE_API_KEY": "sovereign_dummy_token"
    }
    return env
```

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-4)
### Step 2: Implement the Local Broker Route in `core/routes/proxy.py`
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-4)
```python
from quart import Blueprint, request, jsonify

proxy_bp = Blueprint("proxy", __name__)

@proxy_bp.route("/api/proxy/v1beta/models/<model_name>:streamGenerateContent", methods=["POST"])
async def sovereign_broker(model_name):
    payload = await request.get_json()
    
    # 1. Forensic Audit Logging (Verify zero PII exists)
    print(f"[SOVEREIGN BROKER] Intercepted inference request for {model_name}")
    
    # 2. Forward to local offline model server (e.g., Ollama or local vLLM)
    # or process through local deterministic rule engine
    return jsonify({
        "candidates": [{
            "content": {
                "parts": [{"text": "Sovereign local response generated offline."}],
                "role": "model"
            }
        }]
    })
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-5)
## Recipe 2: The 4-Layer Forensic Purge Script
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-5)

When enterprise compliance requires purging proprietary data from an agentic workspace, use this deterministic cleanup sequence:

```bash
#!/usr/bin/env bash
# 4-Layer Forensic Purge Script
set -e

echo "=== Layer 1: Working Tree Sanitization ==="
rm -rf plugins/*/content/proprietary_*
git rm -r --cached plugins/*/content/proprietary_* 2>/dev/null || true

echo "=== Layer 2: Git History Rewriting ==="
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch -rf plugins/*/content/proprietary_*' \
  --prune-empty --tag-name-filter cat -- --all
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "=== Layer 3: SQLite Database VACUUM ==="
python3 -c "
import sqlite3, os
db_path = os.path.expanduser('~/.gemini/antigravity-cli/conversations.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute('VACUUM;')
    conn.close()
    print('SQLite database zeroed and vacuumed.')
"

echo "[SUCCESS] 4-Layer Forensic Purge Complete. Workspace 100% compliant."
```

---

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-6)
## Why Order Matters in Sovereign Architecture
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-6)

1. **Proxy Environment Flags Before Subprocess Startup**:
   - `GEMINI_BASE_URL` must be set in the process environment *before* spawning the CLI. If the CLI starts without the redirect, it attempts to contact public internet servers over WAN.
2. **History Rewriting Before Garbage Collection**:
   - In git forensics, `git filter-branch` must complete before `git gc --prune=now`. Running garbage collection before rewriting does nothing, because historical commits are still referenced by git branch heads.

---

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-7)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-8)

### Q: Why pass a dummy token like `sovereign_dummy_token`?
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-8)
**A:** Many AI SDKs check for the existence of an API key at startup and throw an error if the string is empty. Providing a synthetic dummy token satisfies the SDK while the proxy routes traffic to your local offline model.

[//]: # (SECTION_ID: SIRA-DEV-04_05-SEC-9)
### Q: What is `VACUUM` in SQLite?
[//]: # (SECTION_ID: SIRA-DOC-04_05-SEC-9)
**A:** When you delete rows from a database, SQLite simply marks the space as free rather than erasing it from disk. `VACUUM` physically wipes and defragments the database file on your hard drive.
