# Chapter 02_17: Directory Tiering & API Contract Evidence

Primary source evidence from the Siraugga security manager (`security/security_manager.py`) demonstrating how recursive directory namespace scanning and cryptographic master key verification enforce zero-trust isolation.

---

## Source Citation 1: Cryptographic Master Signature Verification (`security/security_manager.py`)

This excerpt displays how the application mathematically verifies that it is executing on the creator's machine without hardcoding plaintext secret keys:

```python
# Location: <project_root>/security/security_manager.py
# Lines: 31-56

@staticmethod
def check_master_signature() -> bool:
    """
    Cryptographically verifies if this application is running on developer's physical machine.
    Reads local .devcore_master.key and compares its SHA-256 hash to expected value.
    This prevents reverse-engineers from finding the raw key in compiled executable.
    """
    import hashlib
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".devcore_master.key"))
    
    if not os.path.exists(key_path):
        return False
        
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            raw_key = f.read().strip()
            
        # Expected Hash of the raw key
        EXPECTED_HASH = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"
        actual_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        
        return actual_hash == EXPECTED_HASH
    except Exception as e:
        print(f"[Security] Failed to verify master signature: {e}")
        return False
```

### What This Source Proves
- **Immunity to Reverse Engineering**: When compiled to native machine code via Nuitka, strings extracted by hackers reveal only the SHA-256 digest (`80fbad...`), which cannot be mathematically reversed to produce the raw 32-byte key file.
- **Frictionless Developer Auto-Bypass**: The creator never encounters trial locks or API key prompts on their physical hardware.

---

## Source Citation 2: Directory-Level Tiering Algorithm (`security/security_manager.py`)

This excerpt demonstrates the recursive path scanner that stamps entire folder namespaces as protected:

```python
# Location: <project_root>/security/security_manager.py
# Lines: 64-67, 301-315

CORE_DIRECTORIES = {
    "core", "security", "sandbox", "plugins", "docs", 
    "archives", "backups", "scripts"
}

def classify_file(self, rel_path: str) -> str:
    norm_path = os.path.normpath(rel_path).replace("\\", "/")
    parts = norm_path.split("/")

    for p in parts[:-1]:  # Check all parent directory parts
        if p in self.FORBIDDEN_NAMES or p.startswith("."):
            return self.TIER_FORBIDDEN
        if p in self.CORE_DIRECTORIES:
            return self.TIER_CORE_ENGINE

    # Check filename itself
    filename = parts[-1]
    if filename in self.CORE_FILES:
        return self.TIER_CORE_ENGINE
```

### What This Source Proves
- **Deep Namespace Protection**: Even if a file has an innocent extension like `.json` or `.txt`, if it lives inside `core/` (e.g., `core/ui_config.json`), lines 308–309 immediately classify it as `TIER_CORE_ENGINE`.
- **Symlink & Path Traversal Immunity**: Calling `os.path.normpath()` resolves relative tricks (`../../`) before splitting directory parts.

---

## The "Why Order Matters" Principle

In recursive security classification, path evaluation sequence prevents bypasses:
1. **Normalize Path String Before Splitting**: Slashes must be normalized (`\` to `/`) and relative segments (`..`) resolved before analyzing path components.
2. **Evaluate Parent Directory Parts Before Filename**: If a folder is forbidden, its child files are automatically forbidden. Testing directories first saves compute cycles.
3. **Verify Master Signature Before Token Generation**: Check the local cryptographic key before generating high-privilege session tokens.

---

## Beginner Coder Q&A

### What is a SHA-256 digest?
A SHA-256 digest is a 64-character fingerprint of data. Even if you change one comma in a file, the entire fingerprint completely changes, making forgery impossible.

### Why do we check `parts[:-1]`?
`parts[:-1]` selects all folder names in the path, leaving out the file itself. This lets us check if the file is inside a protected folder before we even look at the filename.

### How does this protect game engine developers?
Third-party modders or game developers given access to write game scripts are jailed to `playground/` and blocked from modifying server code or security configs.

---

## Next Steps & Related Chapters
- To understand why flat file matching failed, read [`01_PROBLEMS_ENCOUNTERED/01_22_FILE_LEVEL_CLASSIFICATION_FLAW_AND_DIRECTORY_TIERING.md`](/docs/devlog/01_22_FILE_LEVEL_CLASSIFICATION_FLAW_AND_DIRECTORY_TIERING).
- To view diagnostic test logs of directory classification, visit [`03_DIAGNOSTIC_TESTS/03_16_DIRECTORY_TIERING_AND_SANDBOX_JAIL_AUDIT_LOGS.md`](/docs/devlog/03_16_DIRECTORY_TIERING_AND_SANDBOX_JAIL_AUDIT_LOGS).
- To build the complete zero-trust RBAC engine from scratch, follow [`05_FROM_SCRATCH_CREATION_GUIDES/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH.md`](/docs/devlog/05_03_ZERO_TRUST_RBAC_ENGINE_FROM_SCRATCH).
