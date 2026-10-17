[//]: # (DOC_ID: SIRA-DOC-04_15 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Chapter 04_15: Portable Executable & Binary Stamping Architecture

An architectural guide to Siraugga's **Portable Executable & Dynamic Binary Stamping Pipeline**—delivering zero-install, standalone Windows executables with client time-locks and developer auto-bypass.

---

## Architectural Overview & Topology
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-1)

Distributing Python AI applications to clients usually requires installing Python, setting up virtual environments, and configuring CLI dependencies—a fragile process that frequently fails.

Siraugga solves this via a **4-Layer Decoupled Portable Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 1: NUITKA C-COMPILER                  │
│  • Compiles entire Python codebase into native C machine code│
│  • Bundles internal agy.exe CLI via --include-data-file     │
│  • Compiles with --windows-disable-console for zero popup   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Produces Master Executable (Siraugga.exe)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 2: BINARY STAMPER                     │
│  • Duplicates Master Executable in 0.1 seconds              │
│  • Appends AES-128 (Fernet) encrypted JSON trailer          │
│  • Encapsulates metadata between MAGIC byte delimiters      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Produces Client Executable (Client_John.exe)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 3: RUNTIME TAIL SEEKER                │
│  • sys.frozen detects compiled execution                    │
│  • Seeks to last 4096 bytes of sys.executable in RAM        │
│  • Evaluates client trial expiration timestamp              │
└──────────────────────────────┬──────────────────────────────┘
                               │ Evaluates Authorization
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 LAYER 4: MASTER KEY AUTO-BYPASS             │
│  • Hashes local .devcore_master.key with SHA-256            │
│  • If matches expected hash: bypasses stamp & login screen  │
│  • Grants permanent Super Admin access on creator's machine │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Invariants
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-2)

1. **Zero-Install Portability**:
   - The compiled `.exe` does not require Python or Git to be installed on the client's PC. The bundled `agy.exe` AI brain is extracted into `%TEMP%` on demand.
2. **Client Quota Protection**:
   - Clients enter their own Google Gemini API key on the initial login screen. The key is injected into `os.environ["GEMINI_API_KEY"]`, ensuring the client uses their own billing quota.
3. **Instantaneous Trial Generation**:
   - Generating a custom trial version takes under 100 milliseconds because the stamper appends data to the existing binary rather than recompiling.

---

## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-3)

In binary stamping and authentication, evaluation sequence guarantees access control:
1. **Check Master Key Signature Before Trial Expiration**: Always verify `.devcore_master.key` first. The creator must never be locked out of their own binary, even if a trial timestamp has expired.
2. **Seek to EOF Before Reading Binary Trailer**: Never buffer a 40MB executable into memory to read metadata. Seek directly to the last 4096 bytes.
3. **Verify Fernet HMAC Before Decrypting JSON**: Verifying the authentication tag prevents crashes caused by corrupted trailer bytes.

---

## Reusable Integration Recipe
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-4)

To stamp a custom trial binary for a client in under 10 seconds:

```bash
# Step 1: Duplicate and stamp the binary
python3 security/stamper.py \
    --source dist/Siraugga.exe \
    --dest dist/Client_Demo.exe \
    --client-id "DEMO-001" \
    --days 7

# Step 2: Distribute Client_Demo.exe to the client!
```

---

## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-5)

### Can a client decompile the `.exe` to remove the expiration check?
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-6)
Because Nuitka compiles Python code into native C machine code (assembly), decompiling it is extremely difficult—similar to reverse-engineering a compiled C++ video game.

### What happens when the 7-day trial expires?
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-7)
The application locks itself, disables the AI agent process, and displays a friendly notice inviting the client to upgrade their license.

---

## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-04_15-SEC-8)
- To understand why portable binaries required dynamic stamping, read [`01_PROBLEMS_ENCOUNTERED/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS.md`](/docs/devlog/01_24_DESKTOP_WINDOW_WRAPPING_AND_PYWEBVIEW_TRAPS).
- To inspect primary source citations of the stamper utility, view [`02_SOURCE_EVIDENCE/02_15_BINARY_STAMPER_AND_PE_TRAILER_EVIDENCE.md`](/docs/devlog/02_15_BINARY_STAMPER_AND_PE_TRAILER_EVIDENCE).
- To build the complete binary stamping tool from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_17_PE_BINARY_STAMPER_AND_VERIFIER_FROM_SCRATCH.md`](/docs/devlog/05_17_PE_BINARY_STAMPER_AND_VERIFIER_FROM_SCRATCH).
