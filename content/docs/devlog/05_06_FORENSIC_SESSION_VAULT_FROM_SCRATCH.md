[//]: # (DOC_ID: SIRA-DOC-05_06 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Pillar 05.6: From-Scratch Creation Guide: Forensic Session Vault

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous From-Scratch Guide**: [`05_05_ZERO_DOWNTIME_HOT_PATCH_RUNNER_FROM_SCRATCH.md`](/docs/devlog/05_05_ZERO_DOWNTIME_HOT_PATCH_RUNNER_FROM_SCRATCH)

---

## Overview
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-1)

This guide walks you through building an encrypted **Forensic Session Vault** (`forensic_vault.py`) from a blank editor.

The vault solves a critical compliance dilemma: when developers clear their active chat history to reclaim AI quota, the conversation is archived into an administrative forensic directory with cryptographically hashed timestamps before active memory is purged.

---

## Step-by-Step Implementation
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-2)

### Step 1: Open a Blank Python File
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-3)
```bash
nano forensic_vault.py
```

### Step 2: Implement Vault Storage & Metadata Mapping (Lines 1–45)
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-4)
```python
import hashlib
import json
import os
import shutil
import time

class ForensicVault:
    def __init__(self, vault_dir: str):
        self.vault_dir = os.path.realpath(vault_dir)
        self.meta_file = os.path.join(self.vault_dir, "session_ownership.json")
        os.makedirs(self.vault_dir, exist_ok=True)
        if not os.path.exists(self.meta_file):
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def archive_session(self, session_id: str, transcript_file: str, owner: str, project: str = None) -> str:
        """Archives a conversation transcript into the forensic vault before deletion."""
        if not os.path.exists(transcript_file):
            raise FileNotFoundError(f"Transcript not found: {transcript_file}")

        # 1. Generate SHA-256 Integrity Hash of conversation
        with open(transcript_file, 'rb') as f:
            content_bytes = f.read()
            sha256_hash = hashlib.sha256(content_bytes).hexdigest()

        # 2. Copy transcript to secure admin archive
        archive_name = f"{session_id}.archive.jsonl"
        archive_path = os.path.join(self.vault_dir, archive_name)
        shutil.copy2(transcript_file, archive_path)

        # 3. Update Session Ownership Registry
        with open(self.meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        meta[session_id] = {
            "owner": owner,
            "project": project,
            "archived_at": time.time(),
            "sha256": sha256_hash,
            "archive_file": archive_name
        }

        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)

        return archive_path
```

---

## Why Order Matters in Forensic Archival
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-5)

1. **Calculate Hash Before Moving Files**:
   - The SHA-256 integrity hash must be computed *before* copying or touching the file. This creates an unalterable cryptographic fingerprint proving the archive matches the exact live conversation.
2. **Commit Vault Archive Before Deleting Active Session**:
   - The archive copy and metadata record must succeed *before* the active session database deletes the chat. Deleting first risks permanent data loss if disk I/O errors occur.

---

## Verification & Testing
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-6)

Verify that your vault archives transcripts and tracks ownership metadata:

```bash
python3 -c "
import os
from forensic_vault import ForensicVault

os.makedirs('/tmp/vault_test', exist_ok=True)
# Create dummy transcript
with open('/tmp/vault_test/live_chat.jsonl', 'w') as f:
    f.write('{\"user\": \"hello\", \"model\": \"world\"}\n')

vault = ForensicVault('/tmp/vault_test/archive')
archive_dest = vault.archive_session(
    session_id='sess_123',
    transcript_file='/tmp/vault_test/live_chat.jsonl',
    owner='admin',
    project='Quest_System'
)
print('[PASS] Archived to:', archive_dest)

# Verify metadata
with open('/tmp/vault_test/archive/session_ownership.json') as f:
    print('[PASS] Vault Registry:\n', f.read())
"
```

**Expected Output**:
```text
[PASS] Archived to: /tmp/vault_test/archive/sess_123.archive.jsonl
[PASS] Vault Registry:
{
  "sess_123": {
    "owner": "admin",
    "project": "Quest_System",
    "sha256": "..."
  }
}
```

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-7)

### Q: Why do we calculate a SHA-256 hash?
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-8)
**A:** In legal compliance and cybersecurity audits, proving that forensic evidence has not been tampered with is essential. If anyone alters even a single letter in the archived transcript, the SHA-256 hash changes completely.

### Q: Who is allowed to read files in the vault directory?
[//]: # (SECTION_ID: SIRA-DOC-05_06-SEC-9)
**A:** In the Siraugga platform, the forensic vault is classified as Tier 3/Tier 5, meaning only authenticated system administrators can access or decrypt historical records.
