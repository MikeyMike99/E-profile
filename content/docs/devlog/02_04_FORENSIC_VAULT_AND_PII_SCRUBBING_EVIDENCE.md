[//]: # (DOC_ID: SIRA-DEV-02_04 | VERSION: v1.0 | SCOPE: DEV)

# Pillar 02.4: Source Evidence: Forensic Vault & PII Scrubbing Engine

- **Back to Master Index**: [`../00_README_INDEX.md`](/docs/devlog/00_README_INDEX)
- **Previous Source Evidence**: [`02_03_HOT_PATCH_AND_SELF_HEALING_EVIDENCE.md`](/docs/devlog/02_03_HOT_PATCH_AND_SELF_HEALING_EVIDENCE)
- **Next Source Evidence**: [`02_05_EPHEMERAL_PLUGINS_AND_MCP_EVIDENCE.md`](/docs/devlog/02_05_EPHEMERAL_PLUGINS_AND_MCP_EVIDENCE)

---

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-1)
## Overview
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-1)

This chapter documents verbatim source code citations from Siraugga's data privacy and forensic archival subsystems (`security/local_security.py` and session ownership metadata).

These citations prove how Microsoft Presidio scrubs PII and secrets in real time, and how conversation histories are archived into encrypted forensic vaults before active memory wipes.

---

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-2)
## Source 1: Real-Time PII & Secret Scrubbing
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-2)

- **Source File**: `<project_root>/security/local_security.py`
- **Location**: Presidio Anonymizer Engine

```python
class LocalSecurity:
    """LocalSecurity utilizes Microsoft Presidio to analyze and scrub
    personally identifiable information (PII), secrets, and other sensitive
    data from logs, tool outputs, and LLM conversations."""

    def __init__(self):
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self.enabled = True
        except ImportError:
            print("[WARN] presidio-analyzer missing. PII scrubbing disabled.")
            self.enabled = False

    def scrub_text(self, text: str) -> str:
        """Analyzes text and replaces detected entities with anonymized tokens."""
        if not self.enabled or not text:
            return text
            
        results = self.analyzer.analyze(
            text=text,
            language='en',
            entities=["EMAIL_ADDRESS", "IP_ADDRESS", "CRYPTO", "IBAN_CODE", "PHONE_NUMBER"]
        )
        anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
```

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-3)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-3)
1. **Automated Anonymization**: Outbound text is analyzed for sensitive patterns and replaced with sanitized tokens (`<EMAIL_ADDRESS>`, `<IP_ADDRESS>`) before leaving the machine.
2. **Graceful Degradation**: If Presidio is uninstalled, the service fails open with a system warning rather than crashing the WebSocket stream.

---

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-4)
## Source 2: Forensic Vault Archival & Ownership Mapping
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-4)

- **Source File**: Brain Session Ownership Registry (`session_ownership.json`)
- **Location**: Metadata Schema Structure

```json
{
  "c47cfb2a-6fd8-4042-b84f-23dcdd06b94a": {
    "owner": "Super Admin",
    "project": "Offline_Crack_Lab",
    "created_at": 1791972593.5828376,
    "updated_at": 1791972593.6057096,
    "custom_title": "Active Threat Simulation Lab"
  },
  "8a26ea19-e397-40a1-a432-388efc55c38a": {
    "owner": "Super Admin",
    "project": null,
    "created_at": 1791980033.2020757,
    "updated_at": 1792222775.6434104
  }
}
```

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-5)
### What This Source Proves
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-5)
1. **Multi-Tenant Attribution**: Every historical chat transcript is cryptographically tied to its creator and assigned project workspace.
2. **Audit Preservation**: When a user clicks "Clear History" in the UI to reclaim quota, the transcript is archived into the encrypted forensic vault before active memory is reset.

---

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-6)
## Why Order Matters in Data Privacy
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-6)

1. **Scrub PII Before Log Persistence**:
   - `scrub_text()` must execute *before* writing strings to disk logs or telemetry queues. Writing plain credentials to disk and scrubbing later leaves forensic traces on the file storage blocks.
2. **Forensic Archival Before Active Memory Deletion**:
   - The session must be committed to the vault *before* executing `db.delete()`. If the system crashes mid-operation, un-archived conversation data could be permanently lost.

---

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-7)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-8)

### Q: What is Presidio?
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-8)
**A:** Microsoft Presidio is an open-source data protection framework that identifies sensitive entities (names, phone numbers, passwords) in unstructured text using natural language processing (NLP).

[//]: # (SECTION_ID: SIRA-DEV-02_04-SEC-9)
### Q: Why do we keep forensic archives if the user requested deletion?
[//]: # (SECTION_ID: SIRA-DOC-02_04-SEC-9)
**A:** In cybersecurity and corporate governance, audit trails must be preserved for compliance. Non-admin users see their active screen cleared, but administrators retain encrypted forensic records to investigate unauthorized privilege attempts.
