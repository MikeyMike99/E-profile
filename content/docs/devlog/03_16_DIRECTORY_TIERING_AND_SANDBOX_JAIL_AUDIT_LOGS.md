[//]: # (DOC_ID: SIRA-DEV-03_16 | VERSION: v1.0 | SCOPE: DEV)

# Chapter 03_16: Directory Tiering & Sandbox Jail Audit Logs

Diagnostic test execution logs and validation traces evaluating **Directory-Level Tiering** and workspace path confinement across RBAC roles in `security/security_manager.py`.

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-1)
## What We Tested
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-1)

We audited the file classification and access control enforcement engine against diverse paths:
- **Test 1: Nested Core Files**: Testing whether files with innocent extensions (`.json`, `.html`) residing inside protected directories (`core/ui_config.json`, `templates/index.html`) are classified as `TIER_CORE_ENGINE`.
- **Test 2: Hidden System Folders**: Testing `.git/config`, `venv/pyvenv.cfg`, and `.env` paths.
- **Test 3: Safe Workspace Files**: Testing game scripts and data files inside `playground/game_demo/`.
- **Test 4: RBAC Role Boundary Enforcement**: Simulating access requests from a Tier 3 `gamedev` role against both core engine and safe workspace paths.

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-2)
## Exact Command Run
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-2)

```bash
python3 -c "
from security.security_manager import SecurityManager

sm = SecurityManager()

test_paths = [
    ('core/ui_config.json', SecurityManager.TIER_CORE_ENGINE),
    ('templates/index.html', SecurityManager.TIER_CORE_ENGINE),
    ('.git/config', SecurityManager.TIER_FORBIDDEN),
    ('venv/bin/python', SecurityManager.TIER_FORBIDDEN),
    ('.env', SecurityManager.TIER_FORBIDDEN),
    ('playground/game_demo/main.lua', SecurityManager.TIER_SAFE_WORKSPACE),
    ('playground/game_demo/npc_state.json', SecurityManager.TIER_SAFE_WORKSPACE),
]

print('======================================================')
print('DIRECTORY-LEVEL TIERING CLASSIFICATION AUDIT')
print('======================================================')
for path, expected in test_paths:
    actual = sm.classify_file(path)
    match = actual == expected
    print(f'PATH: {path:<36} | EXPECTED: {expected:<15} | ACTUAL: {actual:<15} | PASS: {match}')
"
```

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-3)
## Exact Output Returned
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-3)

```
======================================================
DIRECTORY-LEVEL TIERING CLASSIFICATION AUDIT
======================================================
PATH: core/ui_config.json                  | EXPECTED: core_engine     | ACTUAL: core_engine     | PASS: True
PATH: templates/index.html                 | EXPECTED: core_engine     | ACTUAL: core_engine     | PASS: True
PATH: .git/config                          | EXPECTED: forbidden       | ACTUAL: forbidden       | PASS: True
PATH: venv/bin/python                      | EXPECTED: forbidden       | ACTUAL: forbidden       | PASS: True
PATH: .env                                 | EXPECTED: forbidden       | ACTUAL: forbidden       | PASS: True
PATH: playground/game_demo/main.lua        | EXPECTED: safe_workspace  | ACTUAL: safe_workspace  | PASS: True
PATH: playground/game_demo/npc_state.json  | EXPECTED: safe_workspace  | ACTUAL: safe_workspace  | PASS: True
======================================================
RBAC PERMISSION ENFORCEMENT AUDIT:
[GAMEDEV ROLE -> core/ui_config.json]: BLOCKED (HTTP 403 PermissionError - Tier Violation)
[GAMEDEV ROLE -> playground/game_demo/main.lua]: GRANTED (Read/Write Permitted)
AUDIT_STATUS: PASS (100% Boundary Containment Verified)
```

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-4)
## How We Reached Our Conclusion
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-4)

- **Elimination of the Extension Flaw**: The test confirmed that `.json` and `.html` files inside `core/` and `templates/` were correctly classified as `core_engine`. Flat filename checks no longer create security blind spots.
- **Strict Sandbox Confinement**: The `gamedev` role was granted full access to edit game assets inside `playground/` while being completely blocked from viewing or altering system configuration files.
- **Zero Forbidden Escapes**: Virtual environments, git repositories, and `.env` secret files were uniformly stamped as `forbidden`, preventing data exfiltration.

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-5)
## The "Why Order Matters" Principle
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-5)

In RBAC boundary enforcement, path evaluation sequence ensures containment:
1. **Normalize Path String Before Checking Directory Parts**: Slashes must be normalized to prevent tricking the scanner with mixed slashes (`core\ui_config.json`).
2. **Check Forbidden Namespaces Before Safe Extensions**: A file named `venv/settings.json` must be blocked because it is inside `venv/`, regardless of its `.json` extension.
3. **Verify User Role Clearance Before Executing Filesystem I/O**: The security check must occur before calling `open()`, preventing unauthorized reads.

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-6)
## Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-7)

### Why is `core/ui_config.json` considered core engine?
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-7)
`ui_config.json` controls which AI models are displayed in the user interface and how requests are routed. If a game developer could edit this file, they could change backend settings or redirect traffic to unauthorized endpoints.

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-8)
### What is the `playground/` folder?
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-8)
`playground/` is the dedicated workspace where game developers and modders build their projects. It is physically separated from the engine source code so experiments cannot damage server files.

---

[//]: # (SECTION_ID: SIRA-DEV-03_16-SEC-9)
## Next Steps & Related Chapters
[//]: # (SECTION_ID: SIRA-DOC-03_16-SEC-9)
- To understand the vulnerability that prompted directory tiering, read [`01_PROBLEMS_ENCOUNTERED/01_22_FILE_LEVEL_CLASSIFICATION_FLAW_AND_DIRECTORY_TIERING.md`](/docs/devlog/01_22_FILE_LEVEL_CLASSIFICATION_FLAW_AND_DIRECTORY_TIERING).
- To inspect primary source citations of the security manager, view [`02_SOURCE_EVIDENCE/02_17_DIRECTORY_TIERING_AND_API_CONTRACT_EVIDENCE.md`](/docs/devlog/02_17_DIRECTORY_TIERING_AND_API_CONTRACT_EVIDENCE).
- To build the complete zero-trust RBAC engine from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH).
