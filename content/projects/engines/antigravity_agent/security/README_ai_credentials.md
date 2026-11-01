# `ai_credentials.json` — encrypted AI credential store

**For agents/developers working in this repo.** This file holds AI-provider
secrets (currently the Claude / Anthropic API key) **encrypted at rest**. It is
written and read only through DevCore's credential vault — never hand-edit it
and never store a key in plaintext.

## What it is
- A small JSON file: `{ "anthropic_api_key": "<base64 AES-GCM ciphertext>" }`.
- Encrypted with **AES-GCM**, key derived (PBKDF2-HMAC-SHA256) from the hardware
  master key `.devcore_master.key` via `security/subscription_guard.py`
  (`encrypt_credential` / `decrypt_credential`).
- Decryptable only on a host that has the matching `.devcore_master.key`.

## How to use it (do NOT read/parse this file directly)
All access goes through `core/local_model_service.py`:

```python
from core.local_model_service import (
    set_claude_api_key,      # store a key (encrypts + writes this file, 0600)
    get_anthropic_api_key,   # -> decrypted key (env ANTHROPIC_API_KEY overrides)
    get_anthropic_credential # -> truthy if any usable credential exists
)
```

Resolution order for the key: `ANTHROPIC_API_KEY` env var → this encrypted file.
The agent brain (`run_claude_model`) and the `/ai_agent/api/ai/connect` admin
endpoint use these helpers; they never touch plaintext.

## Rules
- **Never** commit this file (it is gitignored) or log its contents.
- **Never** write the key to `.env` or any plaintext file.
- To set/rotate the key: call `set_claude_api_key(new_key)` (or use the
  `/ai_agent/setup` admin page), which re-encrypts in place.
- If `.devcore_master.key` changes, previously stored secrets can no longer be
  decrypted — re-enter the key.
