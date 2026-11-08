"""Unified Bitwarden CLI and X_SHI3LD_X (.vault) Cryptographic Engine for e_profile and DevCore.

Provides dual-mode credential management:
1. Primary Mode: Bitwarden CLI (`bw`) integration with ephemeral RAM session management.
2. Fallback & At-Rest Mode: Binary-compatible `MRSV` / `||X_SHI3LD_X||` `.vault` encryption
   with PBKDF2-HMAC-SHA256 key derivation, Fernet master key wrapping, Split-Key Shadow
   Recovery Bridge rotation, and KMS Keychain DEK wrapping.
3. In-Transit Mode: Ephemeral AES-256-GCM authenticated envelopes with timestamp and
   nonce replay protection for browser-to-server and cross-node sync payloads.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import string
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import Blueprint, jsonify, render_template, request, session

BINARY_SIGNATURE = b"\x4d\x52\x53\x56\x01\x02\x03\x04"
HEADER_SEP = b"||X_SHI3LD_X||"
DEFAULT_KDF_ITERATIONS = 100000
SESSION_TTL_SECONDS = 900
TRANSIT_WINDOW_SECONDS = 120

_SYS_RAND = secrets.SystemRandom()


def _mask_secret(val: str) -> str:
    if not val:
        return "••••••••"
    s = str(val).strip()
    if len(s) <= 8:
        return s[:2] + "•" * max(4, len(s) - 2)
    return f"{s[:4]}••••••{s[-3:]}"


def derive_fernet_key(password: str, salt: bytes, iterations: int = DEFAULT_KDF_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=int(iterations),
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def derive_aesgcm_key(secret_text: str, salt: bytes, iterations: int = DEFAULT_KDF_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret_text.encode("utf-8"),
        salt,
        int(iterations),
        dklen=32,
    )


def generate_split_key_data(master_key: bytes) -> Tuple[str, str, str]:
    pool = string.ascii_letters + string.digits + "!@#$%^&*"
    cipher_string = "".join(_SYS_RAND.choice(pool) for _ in range(64))
    indices = [_SYS_RAND.randint(0, 63) for _ in range(6)]
    secret_key = "-".join(f"{i:02d}" for i in indices)
    secret_chars = "".join(cipher_string[i] for i in indices)
    recovery_pass = derive_fernet_key(secret_chars, b"RECOVERY_SALT", DEFAULT_KDF_ITERATIONS)
    recovery_vault = Fernet(recovery_pass).encrypt(master_key).decode("utf-8")
    return cipher_string, secret_key, recovery_vault


def compute_recovery_token_from_header(recovery_cipher: str, recovery_map: str) -> str:
    parts = [int(x.strip()) for x in recovery_map.split("-") if x.strip().isdigit()]
    return "".join(recovery_cipher[idx] for idx in parts if 0 <= idx < len(recovery_cipher))


class TransitCryptoEnvelope:
    """Manages ephemeral AES-256-GCM transit sessions with timestamp and nonce anti-replay."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._seen_nonces: Dict[str, float] = {}

    def _prune(self, now: float) -> None:
        expired_sessions = [
            kid for kid, meta in self._sessions.items()
            if now - meta.get("created_at", 0) > SESSION_TTL_SECONDS
        ]
        for kid in expired_sessions:
            self._sessions.pop(kid, None)
        expired_nonces = [
            n for n, ts in self._seen_nonces.items()
            if now - ts > TRANSIT_WINDOW_SECONDS * 2
        ]
        for n in expired_nonces:
            self._seen_nonces.pop(n, None)

    def issue_handshake(self, actor_id: str = "admin") -> Dict[str, Any]:
        now = time.time()
        key_id = f"tr_{uuid.uuid4().hex[:16]}"
        salt = os.urandom(16)
        seed = base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
        derived = derive_aesgcm_key(seed, salt, DEFAULT_KDF_ITERATIONS)
        with self._lock:
            self._prune(now)
            self._sessions[key_id] = {
                "actor_id": actor_id,
                "salt": salt,
                "seed": seed,
                "key": derived,
                "created_at": now,
            }
        return {
            "key_id": key_id,
            "salt_b64": base64.b64encode(salt).decode("utf-8"),
            "seed": seed,
            "iterations": DEFAULT_KDF_ITERATIONS,
            "server_ts": int(now),
            "ttl_seconds": SESSION_TTL_SECONDS,
        }

    def encrypt_for_transit(self, key_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            self._prune(now)
            sess = self._sessions.get(key_id)
        if not sess:
            raise ValueError("Transit session expired or unknown key_id.")
        iv = os.urandom(12)
        nonce = uuid.uuid4().hex
        ts = int(now)
        envelope_body = {
            "ts": ts,
            "nonce": nonce,
            "data": payload,
        }
        plaintext = json.dumps(envelope_body).encode("utf-8")
        aad = f"{key_id}:{ts}:{nonce}".encode("utf-8")
        ct = AESGCM(sess["key"]).encrypt(iv, plaintext, aad)
        return {
            "enc_envelope": True,
            "key_id": key_id,
            "iv_b64": base64.b64encode(iv).decode("utf-8"),
            "ciphertext_b64": base64.b64encode(ct).decode("utf-8"),
            "ts": ts,
            "nonce": nonce,
        }

    def decrypt_from_transit(self, raw_body: Dict[str, Any], require_envelope: bool = False) -> Dict[str, Any]:
        if not isinstance(raw_body, dict):
            raise ValueError("Invalid payload structure.")
        if not raw_body.get("enc_envelope"):
            if require_envelope:
                raise ValueError("Encrypted transit envelope required.")
            return raw_body

        now = time.time()
        key_id = str(raw_body.get("key_id") or "")
        iv_b64 = str(raw_body.get("iv_b64") or "")
        ct_b64 = str(raw_body.get("ciphertext_b64") or "")
        ts = int(raw_body.get("ts") or 0)
        nonce = str(raw_body.get("nonce") or "")

        if not (key_id and iv_b64 and ct_b64 and ts and nonce):
            raise ValueError("Malformed transit envelope.")
        if abs(now - ts) > TRANSIT_WINDOW_SECONDS:
            raise ValueError("Transit envelope timestamp outside anti-replay window.")

        nonce_key = f"{key_id}:{nonce}"
        with self._lock:
            self._prune(now)
            if nonce_key in self._seen_nonces:
                raise ValueError("Replay detected: transit nonce already consumed.")
            sess = self._sessions.get(key_id)
            if not sess:
                raise ValueError("Transit session expired or invalid key_id.")
            self._seen_nonces[nonce_key] = now

        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)
        aad = f"{key_id}:{ts}:{nonce}".encode("utf-8")
        plaintext = AESGCM(sess["key"]).decrypt(iv, ct, aad)
        parsed = json.loads(plaintext.decode("utf-8"))
        if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], dict):
            return parsed["data"]
        return parsed if isinstance(parsed, dict) else {}


class EProfileKeychain:
    """KMS Keychain bringing DevCore's KEK/DEK wrapping and AES-GCM credential encryption to e_profile."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.cache_dir = self.base_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.master_key_path = self._resolve_master_key_path()
        self.keychain_path = self.cache_dir / "keychain.json"
        self.kek = self._derive_kek()
        self._ensure_keychain()

    def _resolve_master_key_path(self) -> Path:
        devcore_key = self.base_dir.parent / "DevCore" / ".devcore_master.key"
        if devcore_key.exists():
            return devcore_key
        local_key = self.cache_dir / ".eprofile_master.key"
        if not local_key.exists():
            seed = secrets.token_urlsafe(48)
            local_key.write_text(seed, encoding="utf-8")
            try:
                os.chmod(local_key, 0o600)
            except Exception:
                pass
        return local_key

    def _derive_kek(self) -> Fernet:
        raw_master = self.master_key_path.read_text(encoding="utf-8").strip()
        return Fernet(derive_fernet_key(raw_master, b"devcore_static_salt_for_kek", DEFAULT_KDF_ITERATIONS))

    def _ensure_keychain(self) -> None:
        if not self.keychain_path.exists():
            initial_dek = Fernet.generate_key()
            payload = {
                "active_key_id": "key_1",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "keys": {
                    "key_1": self.kek.encrypt(initial_dek).decode("utf-8"),
                },
            }
            self.keychain_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            try:
                os.chmod(self.keychain_path, 0o600)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.keychain_path.read_text(encoding="utf-8"))
            return {
                "initialized": True,
                "active_key_id": data.get("active_key_id", "unknown"),
                "key_count": len(data.get("keys", {})),
                "shared_devcore_master": self.master_key_path.name == ".devcore_master.key",
            }
        except Exception as e:
            return {"initialized": False, "error": str(e)}

    def get_active_cipher(self) -> Fernet:
        data = json.loads(self.keychain_path.read_text(encoding="utf-8"))
        active_id = data["active_key_id"]
        enc_dek = data["keys"][active_id]
        return Fernet(self.kek.decrypt(enc_dek.encode("utf-8")))

    def get_all_ciphers(self) -> List[Fernet]:
        data = json.loads(self.keychain_path.read_text(encoding="utf-8"))
        return [
            Fernet(self.kek.decrypt(enc_dek.encode("utf-8")))
            for enc_dek in data.get("keys", {}).values()
        ]

    def rotate_key(self) -> str:
        data = json.loads(self.keychain_path.read_text(encoding="utf-8"))
        new_id = f"key_{len(data.get('keys', {})) + 1}"
        new_dek = Fernet.generate_key()
        data.setdefault("keys", {})[new_id] = self.kek.encrypt(new_dek).decode("utf-8")
        data["active_key_id"] = new_id
        data["last_rotated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.keychain_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return new_id

    def encrypt_bytes(self, raw: bytes) -> bytes:
        return self.get_active_cipher().encrypt(raw)

    def decrypt_bytes(self, token: bytes) -> bytes:
        for cipher in reversed(self.get_all_ciphers()):
            try:
                return cipher.decrypt(token)
            except InvalidToken:
                continue
        raise InvalidToken("Unable to decrypt payload with any KMS keychain DEK.")


class ShieldVaultContainer:
    """Implements the MRSV / ||X_SHI3LD_X|| .vault specification from Documents/encryption_toll/encrypt_me.py."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path).resolve()
        self._lock = threading.Lock()
        self._master_key: Optional[bytes] = None
        self._unlocked_user: Optional[str] = None
        self._unlocked_at: float = 0.0

    def _check_ttl(self) -> None:
        if self._master_key and (time.time() - self._unlocked_at) > SESSION_TTL_SECONDS:
            self._master_key = None
            self._unlocked_user = None
            self._unlocked_at = 0.0

    def is_unlocked(self) -> bool:
        with self._lock:
            self._check_ttl()
            return self._master_key is not None

    def exists(self) -> bool:
        return self.vault_path.is_file()

    def read_header(self, target_path: Optional[Path] = None) -> Dict[str, Any]:
        vp = Path(target_path or self.vault_path).resolve()
        if not vp.is_file():
            return {}
        blob = vp.read_bytes()
        if not blob.startswith(BINARY_SIGNATURE):
            raise ValueError("Invalid binary signature: not an MRSV X_SHI3LD_X .vault file.")
        no_sig = blob[len(BINARY_SIGNATURE):]
        if HEADER_SEP not in no_sig:
            raise ValueError("Missing ||X_SHI3LD_X|| header separator.")
        header_part, _ = no_sig.split(HEADER_SEP, 1)
        return json.loads(header_part.decode("utf-8"))

    def _split_blob(self, target_path: Optional[Path] = None) -> Tuple[Dict[str, Any], bytes]:
        vp = Path(target_path or self.vault_path).resolve()
        blob = vp.read_bytes()
        if not blob.startswith(BINARY_SIGNATURE):
            raise ValueError("Invalid binary signature: not an MRSV X_SHI3LD_X .vault file.")
        no_sig = blob[len(BINARY_SIGNATURE):]
        header_part, encrypted_content = no_sig.split(HEADER_SEP, 1)
        return json.loads(header_part.decode("utf-8")), encrypted_content

    def _write_blob(self, header: Dict[str, Any], master_key: bytes, plaintext_bytes: bytes, target_path: Optional[Path] = None) -> None:
        vp = Path(target_path or self.vault_path).resolve()
        vp.parent.mkdir(parents=True, exist_ok=True)
        cipher_str, secret_map, shadow_vault = generate_split_key_data(master_key)
        header.update({
            "recovery_cipher": cipher_str,
            "recovery_map": secret_map,
            "recovery_vault": shadow_vault,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        encrypted_content = Fernet(master_key).encrypt(plaintext_bytes)
        tmp_path = vp.with_suffix(vp.suffix + ".tmp")
        tmp_path.write_bytes(BINARY_SIGNATURE + json.dumps(header).encode("utf-8") + HEADER_SEP + encrypted_content)
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        tmp_path.replace(vp)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            self._check_ttl()
            unlocked = self._master_key is not None
            user = self._unlocked_user
            rem = max(0, int(SESSION_TTL_SECONDS - (time.time() - self._unlocked_at))) if unlocked else 0
        exists = self.exists()
        header_meta: Dict[str, Any] = {}
        if exists:
            try:
                h = self.read_header()
                header_meta = {
                    "file_uuid": h.get("file_uuid", ""),
                    "last_updated": h.get("last_updated", ""),
                    "users": list(h.get("users", {}).keys()),
                    "recovery_standard_enabled": bool(h.get("recovery_standard_enabled", True)),
                    "recovery_cipher": h.get("recovery_cipher", "") if unlocked else "",
                    "recovery_map": h.get("recovery_map", "") if unlocked else "",
                }
            except Exception as e:
                header_meta = {"error": str(e)}
        return {
            "exists": exists,
            "vault_file": self.vault_path.name,
            "unlocked": unlocked,
            "unlocked_user": user,
            "remaining_ttl_seconds": rem,
            "header": header_meta,
        }

    def initialize(
        self,
        username: str,
        password: str,
        initial_items: Optional[List[Dict[str, Any]]] = None,
        allow_recovery: bool = True,
    ) -> Dict[str, Any]:
        username = (username or "").strip()
        if not username or not password or len(password) < 4:
            raise ValueError("Username and a password of at least 4 characters are required.")
        master_key = Fernet.generate_key()
        salt = os.urandom(16)
        user_key = derive_fernet_key(password, salt, DEFAULT_KDF_ITERATIONS)
        access_list = {
            username: {
                "salt": base64.b64encode(salt).decode("utf-8"),
                "vault": Fernet(user_key).encrypt(master_key).decode("utf-8"),
            }
        }
        header = {
            "file_uuid": str(uuid.uuid4()),
            "recovery_standard_enabled": bool(allow_recovery),
            "kdf_iterations": DEFAULT_KDF_ITERATIONS,
            "users": access_list,
        }
        store_payload = {
            "version": 1,
            "items": initial_items or [],
        }
        with self._lock:
            self._write_blob(header, master_key, json.dumps(store_payload, indent=2).encode("utf-8"))
            self._master_key = master_key
            self._unlocked_user = username
            self._unlocked_at = time.time()
        return self.get_status()

    def unlock(self, username: str, password: str) -> Dict[str, Any]:
        username = (username or "admin").strip()
        if not self.exists():
            if password and len(password.strip()) >= 4:
                return self.initialize(username=username, password=password, allow_recovery=True)
            raise FileNotFoundError("Local .vault file does not exist yet. Enter a password (min 4 chars) to auto-initialize.")
        header, encrypted_content = self._split_blob()
        users = header.get("users", {})
        if username not in users:
            raise PermissionError(f"User '{username}' is not registered in this .vault header.")
        user_data = users[username]
        salt = base64.b64decode(user_data["salt"])
        iters = int(header.get("kdf_iterations", DEFAULT_KDF_ITERATIONS))
        user_key = derive_fernet_key(password, salt, iters)
        try:
            master_key = Fernet(user_key).decrypt(user_data["vault"].encode("utf-8"))
            Fernet(master_key).decrypt(encrypted_content)
        except InvalidToken as exc:
            raise PermissionError("Access Denied: Invalid password or corrupted .vault token.") from exc

        with self._lock:
            self._master_key = master_key
            self._unlocked_user = username
            self._unlocked_at = time.time()
        return self.get_status()

    def lock(self) -> Dict[str, Any]:
        with self._lock:
            self._master_key = None
            self._unlocked_user = None
            self._unlocked_at = 0.0
        return self.get_status()

    def _load_store_unlocked(self) -> Tuple[Dict[str, Any], bytes, Dict[str, Any]]:
        self._check_ttl()
        if not self._master_key:
            raise PermissionError("Local .vault is locked. Unlock it first.")
        header, encrypted_content = self._split_blob()
        decrypted = Fernet(self._master_key).decrypt(encrypted_content)
        data = json.loads(decrypted.decode("utf-8"))
        if not isinstance(data, dict):
            data = {"version": 1, "items": []}
        data.setdefault("items", [])
        return header, self._master_key, data

    def list_items(self, search: str = "") -> List[Dict[str, Any]]:
        with self._lock:
            _, _, data = self._load_store_unlocked()
            items = list(data.get("items", []))
        q = (search or "").strip().lower()
        results = []
        for it in items:
            if q and q not in (it.get("name", "").lower() + " " + it.get("category", "").lower() + " " + it.get("username", "").lower()):
                continue
            results.append({
                "id": it.get("id"),
                "name": it.get("name", "Untitled"),
                "category": it.get("category", "Secret"),
                "username": it.get("username", ""),
                "secret_masked": _mask_secret(it.get("secret", "")),
                "notes": it.get("notes", ""),
                "uri": it.get("uri", ""),
                "updated_at": it.get("updated_at", ""),
                "engine": "shield_vault",
            })
        return results

    def reveal_item(self, item_id: str) -> Dict[str, Any]:
        with self._lock:
            _, _, data = self._load_store_unlocked()
            for it in data.get("items", []):
                if it.get("id") == item_id:
                    return {
                        "id": it.get("id"),
                        "name": it.get("name"),
                        "username": it.get("username", ""),
                        "secret": it.get("secret", ""),
                        "notes": it.get("notes", ""),
                        "uri": it.get("uri", ""),
                    }
        raise KeyError(f"Item '{item_id}' not found in .vault.")

    def upsert_item(
        self,
        name: str,
        secret: str,
        category: str = "API Key",
        username: str = "",
        notes: str = "",
        uri: str = "",
        item_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name or not secret:
            raise ValueError("Item name and secret value are required.")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            header, master_key, data = self._load_store_unlocked()
            items = data.setdefault("items", [])
            target = None
            if item_id:
                target = next((x for x in items if x.get("id") == item_id), None)
            if not target:
                target = next((x for x in items if x.get("name") == name and x.get("category") == category), None)
            if target:
                target.update({
                    "name": name,
                    "category": category,
                    "username": username,
                    "secret": secret,
                    "notes": notes,
                    "uri": uri,
                    "updated_at": now_str,
                })
                saved = target
            else:
                saved = {
                    "id": f"sv_{uuid.uuid4().hex[:12]}",
                    "name": name,
                    "category": category,
                    "username": username,
                    "secret": secret,
                    "notes": notes,
                    "uri": uri,
                    "updated_at": now_str,
                }
                items.append(saved)
            self._write_blob(header, master_key, json.dumps(data, indent=2).encode("utf-8"))
        return {
            "id": saved["id"],
            "name": saved["name"],
            "category": saved["category"],
            "username": saved["username"],
            "secret_masked": _mask_secret(saved["secret"]),
            "updated_at": saved["updated_at"],
            "engine": "shield_vault",
        }

    def delete_item(self, item_id: str) -> bool:
        with self._lock:
            header, master_key, data = self._load_store_unlocked()
            before = len(data.get("items", []))
            data["items"] = [x for x in data.get("items", []) if x.get("id") != item_id]
            if len(data["items"]) == before:
                return False
            self._write_blob(header, master_key, json.dumps(data, indent=2).encode("utf-8"))
            return True

    def add_or_update_user(self, target_username: str, target_password: str) -> Dict[str, Any]:
        target_username = (target_username or "").strip()
        if not target_username or not target_password or len(target_password) < 4:
            raise ValueError("Username and password (min 4 chars) required.")
        with self._lock:
            header, master_key, data = self._load_store_unlocked()
            salt = os.urandom(16)
            iters = int(header.get("kdf_iterations", DEFAULT_KDF_ITERATIONS))
            uk = derive_fernet_key(target_password, salt, iters)
            header.setdefault("users", {})[target_username] = {
                "salt": base64.b64encode(salt).decode("utf-8"),
                "vault": Fernet(uk).encrypt(master_key).decode("utf-8"),
            }
            self._write_blob(header, master_key, json.dumps(data, indent=2).encode("utf-8"))
        return self.get_status()

    def get_recovery_challenge(self, verify_username: str) -> Dict[str, Any]:
        if not self.exists():
            raise FileNotFoundError("Local .vault file does not exist.")
        header = self.read_header()
        if verify_username not in header.get("users", {}):
            raise PermissionError("Username not recognized in .vault access list.")
        return {
            "file_uuid": header.get("file_uuid", ""),
            "last_updated": header.get("last_updated", "Unknown"),
            "recovery_cipher": header.get("recovery_cipher", ""),
            "recovery_map": header.get("recovery_map", ""),
        }

    def emergency_recover(self, verify_username: str, recovery_token: str, new_password: str) -> Dict[str, Any]:
        if not self.exists():
            raise FileNotFoundError("Local .vault file does not exist.")
        if not new_password or len(new_password) < 4:
            raise ValueError("New password must be at least 4 characters.")
        header, encrypted_content = self._split_blob()
        if verify_username not in header.get("users", {}):
            raise PermissionError("Target username not found in .vault access list.")
        recovery_pass = derive_fernet_key(recovery_token.strip(), b"RECOVERY_SALT", DEFAULT_KDF_ITERATIONS)
        try:
            master_key = Fernet(recovery_pass).decrypt(header["recovery_vault"].encode("utf-8"))
            plaintext = Fernet(master_key).decrypt(encrypted_content)
        except InvalidToken as exc:
            raise PermissionError("Recovery failed: Invalid or expired Split-Key Recovery Token.") from exc

        new_salt = os.urandom(16)
        iters = int(header.get("kdf_iterations", DEFAULT_KDF_ITERATIONS))
        new_uk = derive_fernet_key(new_password, new_salt, iters)
        header["users"][verify_username] = {
            "salt": base64.b64encode(new_salt).decode("utf-8"),
            "vault": Fernet(new_uk).encrypt(master_key).decode("utf-8"),
        }
        with self._lock:
            self._write_blob(header, master_key, plaintext)
            self._master_key = master_key
            self._unlocked_user = verify_username
            self._unlocked_at = time.time()
        return self.get_status()

    def encrypt_external_file(self, file_path: Path, username: str, password: str) -> Dict[str, Any]:
        fp = Path(file_path).resolve()
        if not fp.is_file():
            raise FileNotFoundError(f"File not found: {fp.name}")
        vault_out = Path(str(fp) + ".vault")
        master_key = Fernet.generate_key()
        salt = os.urandom(16)
        uk = derive_fernet_key(password, salt, DEFAULT_KDF_ITERATIONS)
        header = {
            "file_uuid": str(uuid.uuid4()),
            "recovery_standard_enabled": True,
            "kdf_iterations": DEFAULT_KDF_ITERATIONS,
            "users": {
                username: {
                    "salt": base64.b64encode(salt).decode("utf-8"),
                    "vault": Fernet(uk).encrypt(master_key).decode("utf-8"),
                }
            },
        }
        raw_bytes = fp.read_bytes()
        self._write_blob(header, master_key, raw_bytes, target_path=vault_out)
        return {
            "source_file": fp.name,
            "vault_file": vault_out.name,
            "size_bytes": vault_out.stat().st_size,
            "file_uuid": header["file_uuid"],
        }

    def decrypt_external_file(self, vault_file_path: Path, username: str, password: str, output_path: Optional[Path] = None) -> Dict[str, Any]:
        vp = Path(vault_file_path).resolve()
        if not vp.is_file():
            raise FileNotFoundError(f"Vault file not found: {vp.name}")
        header, encrypted_content = self._split_blob(target_path=vp)
        users = header.get("users", {})
        if username not in users:
            raise PermissionError(f"User '{username}' not in vault access list.")
        u_info = users[username]
        salt = base64.b64decode(u_info["salt"])
        iters = int(header.get("kdf_iterations", DEFAULT_KDF_ITERATIONS))
        uk = derive_fernet_key(password, salt, iters)
        try:
            master_key = Fernet(uk).decrypt(u_info["vault"].encode("utf-8"))
            decrypted = Fernet(master_key).decrypt(encrypted_content)
        except InvalidToken as exc:
            raise PermissionError("Invalid password for external .vault file.") from exc

        if output_path:
            out_p = Path(output_path).resolve()
            out_p.write_bytes(decrypted)
            try:
                os.chmod(out_p, 0o600)
            except Exception:
                pass
            return {"restored_file": out_p.name, "size_bytes": len(decrypted)}
        return {"decrypted_size_bytes": len(decrypted), "verified": True}


class BitwardenCliBridge:
    """Thread-safe wrapper around the Bitwarden CLI (`bw`) with strict in-memory session storage."""

    def __init__(self, shield_fallback: Optional[ShieldVaultContainer] = None) -> None:
        self._lock = threading.Lock()
        self._bw_session: Optional[str] = None
        self._unlocked_at: float = 0.0
        self._shield_fallback: Optional[ShieldVaultContainer] = shield_fallback

    def find_binary(self) -> Optional[str]:
        candidates = [
            shutil.which("bw"),
            str(Path.home() / ".local" / "bin" / "bw"),
            "/usr/local/bin/bw",
            "/usr/bin/bw",
        ]
        for c in candidates:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return None

    def _check_ttl(self) -> None:
        if self._bw_session and (time.time() - self._unlocked_at) > SESSION_TTL_SECONDS:
            self._bw_session = None
            self._unlocked_at = 0.0

    def _clean_env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = os.environ.copy()
        env["BW_NOINTERACTION"] = "true"
        if extra:
            env.update(extra)
        return env

    def get_status(self) -> Dict[str, Any]:
        bw_bin = self.find_binary()
        if not bw_bin:
            return {
                "installed": False,
                "binary_path": None,
                "status": "unavailable",
                "session_active": False,
                "user_email": None,
                "last_sync": None,
            }
        with self._lock:
            self._check_ttl()
            active_token = self._bw_session
            rem_ttl = max(0, int(SESSION_TTL_SECONDS - (time.time() - self._unlocked_at))) if active_token else 0

        cmd = [bw_bin, "status"]
        env = self._clean_env({"BW_SESSION": active_token} if active_token else None)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=8)
            raw = (res.stdout or "").strip()
            info = json.loads(raw) if raw.startswith("{") else {}
        except Exception:
            info = {}

        cli_status = info.get("status", "unauthenticated")
        if active_token and cli_status == "locked":
            cli_status = "unlocked"

        return {
            "installed": True,
            "binary_path": bw_bin,
            "status": cli_status,
            "session_active": bool(active_token),
            "remaining_ttl_seconds": rem_ttl,
            "user_email": info.get("userEmail"),
            "last_sync": info.get("lastSync"),
            "server_url": info.get("serverUrl"),
        }

    def login(
        self,
        email: str = "",
        password: str = "",
        code: str = "",
        method: str = "0",
        client_id: str = "",
        client_secret: str = "",
    ) -> Tuple[bool, str]:
        bw_bin = self.find_binary()
        if not bw_bin:
            return False, "Bitwarden CLI (`bw`) is not installed on this host. Using Local .vault Engine."

        if client_id and client_secret:
            env = self._clean_env({
                "BW_CLIENTID": client_id.strip(),
                "BW_CLIENTSECRET": client_secret.strip(),
            })
            res = subprocess.run([bw_bin, "login", "--apikey"], capture_output=True, text=True, env=env, timeout=20)
            if res.returncode == 0 and password:
                return self.unlock(password)
            if res.returncode == 0:
                return True, "Logged in via Bitwarden API Key. Enter Master Password to unlock session."
            return False, (res.stderr or res.stdout or "API Key login failed.").strip()

        if not email or not password:
            return False, "Email and Master Password are required for Bitwarden CLI login."

        env = self._clean_env({"BW_PASS": password})
        cmd = [bw_bin, "login", email.strip(), "--passwordenv", "BW_PASS", "--raw"]
        if code:
            cmd.extend(["--method", str(method or "0"), "--code", code.strip()])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=25)
        except Exception as e:
            return False, f"Bitwarden CLI login error: {e}"

        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        if res.returncode == 0 and out and " " not in out and len(out) >= 20:
            with self._lock:
                self._bw_session = out
                self._unlocked_at = time.time()
            return True, "Bitwarden CLI authenticated and unlocked in memory."
        if "already logged in" in (out + " " + err).lower():
            return self.unlock(password)
        return False, (err or out or "Bitwarden login failed. Check credentials or 2FA code.")

    def unlock(self, password: str) -> Tuple[bool, str]:
        if not password:
            return False, "Master Password is required to unlock the vault."

        bw_bin = self.find_binary()
        out = ""
        err = ""
        if bw_bin:
            env = self._clean_env({"BW_PASS": password})
            try:
                res = subprocess.run(
                    [bw_bin, "unlock", "--passwordenv", "BW_PASS", "--raw"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=20,
                )
                out = (res.stdout or "").strip()
                err = (res.stderr or "").strip()
                if res.returncode == 0 and out and " " not in out and len(out) >= 20:
                    with self._lock:
                        self._bw_session = out
                        self._unlocked_at = time.time()
                    return True, "Bitwarden Vault unlocked in ephemeral memory."
            except Exception as e:
                err = str(e)

        combined_err = f"{err} {out}".strip().lower()
        if self._shield_fallback is not None and (not bw_bin or "not logged in" in combined_err or "unauthenticated" in combined_err):
            if len(password.strip()) >= 4:
                try:
                    if not self._shield_fallback.exists():
                        self._shield_fallback.initialize(username="admin", password=password, allow_recovery=True)
                        return (
                            True,
                            "Bitwarden Cloud CLI is not logged in — automatically initialized and unlocked Local X_SHI3LD_X .vault in RAM! (To connect a Bitwarden Cloud account, enter Email + Master Password and click Login CLI.)",
                        )
                    hdr = self._shield_fallback.read_header()
                    reg_users = list((hdr.get("users") or {}).keys())
                    target_u = "admin" if "admin" in reg_users else (reg_users[0] if reg_users else "admin")
                    self._shield_fallback.unlock(username=target_u, password=password)
                    return (
                        True,
                        f"Bitwarden Cloud CLI is not logged in — automatically unlocked Local X_SHI3LD_X .vault ('{target_u}') in RAM!",
                    )
                except Exception as fallback_exc:
                    return (
                        False,
                        f"Bitwarden Cloud CLI is not logged in (enter Email + Master Password and click Login CLI), and Local .vault fallback rejected the password: {fallback_exc}",
                    )

        return False, (err or out or "Failed to unlock Bitwarden CLI. Verify master password or login first.")

    def lock(self) -> Tuple[bool, str]:
        bw_bin = self.find_binary()
        with self._lock:
            self._bw_session = None
            self._unlocked_at = 0.0
        if bw_bin:
            try:
                subprocess.run([bw_bin, "lock"], capture_output=True, text=True, timeout=8)
            except Exception:
                pass
        return True, "Bitwarden CLI session locked and cleared from memory."

    def sync(self) -> Tuple[bool, str]:
        bw_bin = self.find_binary()
        if not bw_bin:
            return False, "Bitwarden CLI unavailable."
        with self._lock:
            self._check_ttl()
            token = self._bw_session
        if not token:
            return False, "Bitwarden CLI is locked. Unlock first."
        env = self._clean_env({"BW_SESSION": token})
        try:
            res = subprocess.run([bw_bin, "sync"], capture_output=True, text=True, env=env, timeout=20)
            if res.returncode == 0:
                return True, "Bitwarden Vault synced with cloud."
            return False, (res.stderr or res.stdout or "Sync failed.").strip()
        except Exception as e:
            return False, f"Sync error: {e}"

    def list_items(self, search: str = "") -> List[Dict[str, Any]]:
        bw_bin = self.find_binary()
        if not bw_bin:
            return []
        with self._lock:
            self._check_ttl()
            token = self._bw_session
        if not token:
            return []

        env = self._clean_env({"BW_SESSION": token})
        cmd = [bw_bin, "list", "items"]
        if search:
            cmd.extend(["--search", search.strip()])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=15)
            if res.returncode != 0:
                return []
            raw_items = json.loads(res.stdout or "[]")
        except Exception:
            return []

        results = []
        for it in raw_items:
            login_obj = it.get("login") or {}
            secret_val = login_obj.get("password") or it.get("notes") or ""
            uris = login_obj.get("uris") or []
            first_uri = uris[0].get("uri", "") if uris and isinstance(uris[0], dict) else ""
            results.append({
                "id": it.get("id"),
                "name": it.get("name", "Untitled"),
                "category": "Login" if it.get("type") == 1 else "Secure Note",
                "username": login_obj.get("username") or "",
                "secret_masked": _mask_secret(secret_val),
                "notes": (it.get("notes") or "")[:120],
                "uri": first_uri,
                "updated_at": it.get("revisionDate", ""),
                "engine": "bitwarden_cli",
            })
        return results

    def create_item(
        self,
        name: str,
        secret: str,
        category: str = "API Key",
        username: str = "",
        notes: str = "",
        uri: str = "",
    ) -> Dict[str, Any]:
        bw_bin = self.find_binary()
        if not bw_bin:
            raise RuntimeError("Bitwarden CLI unavailable.")
        with self._lock:
            self._check_ttl()
            token = self._bw_session
        if not token:
            raise PermissionError("Bitwarden CLI is locked.")

        item_payload = {
            "organizationId": None,
            "folderId": None,
            "type": 1,
            "name": name,
            "notes": f"[{category}] {notes}".strip(),
            "favorite": False,
            "login": {
                "username": username or category,
                "password": secret,
                "totp": None,
                "uris": [{"match": None, "uri": uri}] if uri else [],
            },
        }
        encoded_b64 = base64.b64encode(json.dumps(item_payload).encode("utf-8")).decode("utf-8")
        env = self._clean_env({"BW_SESSION": token})
        res = subprocess.run(
            [bw_bin, "create", "item", encoded_b64],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        if res.returncode != 0:
            raise RuntimeError((res.stderr or res.stdout or "Failed to create Bitwarden item.").strip())
        created = json.loads(res.stdout)
        return {
            "id": created.get("id"),
            "name": created.get("name", name),
            "category": category,
            "username": username,
            "secret_masked": _mask_secret(secret),
            "updated_at": created.get("revisionDate", ""),
            "engine": "bitwarden_cli",
        }

    def reveal_item(self, item_id: str) -> Dict[str, Any]:
        bw_bin = self.find_binary()
        if not bw_bin:
            raise RuntimeError("Bitwarden CLI unavailable.")
        with self._lock:
            self._check_ttl()
            token = self._bw_session
        if not token:
            raise PermissionError("Bitwarden CLI is locked.")

        env = self._clean_env({"BW_SESSION": token})
        res = subprocess.run([bw_bin, "get", "item", item_id], capture_output=True, text=True, env=env, timeout=12)
        if res.returncode != 0:
            raise KeyError("Bitwarden item not found.")
        it = json.loads(res.stdout)
        login_obj = it.get("login") or {}
        uris = login_obj.get("uris") or []
        return {
            "id": it.get("id"),
            "name": it.get("name"),
            "username": login_obj.get("username") or "",
            "secret": login_obj.get("password") or it.get("notes") or "",
            "notes": it.get("notes") or "",
            "uri": uris[0].get("uri", "") if uris and isinstance(uris[0], dict) else "",
        }


import math


def _shannon_entropy(val: str) -> float:
    if not val:
        return 0.0
    length = len(val)
    counts: Dict[str, int] = {}
    for ch in val:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


_PLACEHOLDER_PATTERNS = re.compile(
    r"(?i)^(?:"
    r"changeme|change_me|your[_-]?api[_-]?key(?:[_-]?here)?|your[_-]?secret(?:[_-]?here)?|"
    r"your[_-]?password(?:[_-]?here)?|your[_-]?token(?:[_-]?here)?|insert[_-]?key[_-]?here|"
    r"replace[_-]?me|example(?:[_-]?key|_secret|_token)?|dummy(?:[_-]?key)?|test(?:[_-]?key|_secret|_password)?|"
    r"placeholder|none|null|undefined|true|false|todo|fixme|xxx+|000+|123456(?:78|789)?|"
    r"password|secret|admin|root|guest|default|<[^>]+>|\$\{[^}]+\}|\$[A-Z_][A-Z0-9_]*"
    r")$"
)
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_HEX_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,128}$")

_PREFIX_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "google_gemini_api_key",
        "name": "Google Gemini / Cloud API Key",
        "category": "Google Gemini API",
        "uri": "https://aistudio.google.com/app/apikey",
        "confidence": 0.98,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(AIzaSy[A-Za-z0-9_\-]{33})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "google_oauth_client_secret",
        "name": "Google Cloud OAuth Client Secret",
        "category": "Google Cloud OAuth",
        "uri": "https://console.cloud.google.com/apis/credentials",
        "confidence": 0.98,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(GOCSPX-[A-Za-z0-9_\-]{20,40})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "google_oauth_access_token",
        "name": "Google OAuth 2.0 Access Token",
        "category": "Google OAuth Token",
        "uri": "https://console.cloud.google.com/apis/credentials",
        "confidence": 0.95,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-\.])(ya29\.[A-Za-z0-9_\-\.]{30,512})(?![A-Za-z0-9_\-\.])"),
    },
    {
        "rule_id": "google_oauth_refresh_token",
        "name": "Google OAuth 2.0 Refresh Token",
        "category": "Google OAuth Token",
        "uri": "https://console.cloud.google.com/apis/credentials",
        "confidence": 0.94,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-/])(1//[0-9A-Za-z_\-]{35,200})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "anthropic_api_key",
        "name": "Anthropic Claude API Key",
        "category": "AI Provider API Key",
        "uri": "https://console.anthropic.com/settings/keys",
        "confidence": 0.99,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(sk-ant-(?:api03|sid01)-[A-Za-z0-9_\-]{30,140})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "openai_api_key",
        "name": "OpenAI API Key",
        "category": "AI Provider API Key",
        "uri": "https://platform.openai.com/api-keys",
        "confidence": 0.97,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(sk-(?:proj-|svcacct-)[A-Za-z0-9_\-]{32,180}|sk-[A-Za-z0-9]{40,64})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "github_pat",
        "name": "GitHub Personal Access Token",
        "category": "Git & Deployment",
        "uri": "https://github.com/settings/tokens",
        "confidence": 0.99,
        "regex": re.compile(r"(?<![A-Za-z0-9_])(gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})(?![A-Za-z0-9_])"),
    },
    {
        "rule_id": "gitlab_pat",
        "name": "GitLab Personal Access Token",
        "category": "Git & Deployment",
        "uri": "https://gitlab.com/-/user_settings/personal_access_tokens",
        "confidence": 0.98,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(glpat-[A-Za-z0-9_\-]{20,64})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "huggingface_token",
        "name": "HuggingFace Access Token",
        "category": "AI Provider API Key",
        "uri": "https://huggingface.co/settings/tokens",
        "confidence": 0.97,
        "regex": re.compile(r"(?<![A-Za-z0-9_])(hf_[A-Za-z0-9]{30,64})(?![A-Za-z0-9_])"),
    },
    {
        "rule_id": "slack_token",
        "name": "Slack API / Bot Token",
        "category": "Messaging & Webhook",
        "uri": "https://api.slack.com/apps",
        "confidence": 0.98,
        "regex": re.compile(r"(?<![A-Za-z0-9\-])(xox[abprs]-[0-9A-Za-z\-]{20,120})(?![A-Za-z0-9\-])"),
    },
    {
        "rule_id": "stripe_live_secret",
        "name": "Stripe Live Secret / Webhook Key",
        "category": "Payment & Billing",
        "uri": "https://dashboard.stripe.com/apikeys",
        "confidence": 0.99,
        "regex": re.compile(r"(?<![A-Za-z0-9_])((?:sk|rk)_live_[0-9a-zA-Z]{24,99}|whsec_[0-9a-zA-Z]{24,99})(?![A-Za-z0-9_])"),
    },
    {
        "rule_id": "aws_access_key_id",
        "name": "AWS IAM Access Key ID",
        "category": "Cloud Infrastructure",
        "uri": "https://console.aws.amazon.com/iam/",
        "confidence": 0.95,
        "regex": re.compile(r"(?<![A-Z0-9])((?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16})(?![A-Z0-9])"),
    },
    {
        "rule_id": "package_registry_token",
        "name": "Package Registry / Delivery Token",
        "category": "Git & Deployment",
        "uri": "",
        "confidence": 0.97,
        "regex": re.compile(
            r"(?<![A-Za-z0-9_\-])("
            r"npm_[A-Za-z0-9]{36}|"
            r"pypi-[A-Za-z0-9_\-]{40,200}|"
            r"dckr_pat_[A-Za-z0-9_\-]{20,80}|"
            r"SG\.[A-Za-z0-9_\-]{16,64}\.[A-Za-z0-9_\-]{16,64}|"
            r"shpat_[a-fA-F0-9]{32}"
            r")(?![A-Za-z0-9_\-])"
        ),
    },
    {
        "rule_id": "telegram_bot_token",
        "name": "Telegram Bot API Token",
        "category": "Messaging & Webhook",
        "uri": "https://t.me/BotFather",
        "confidence": 0.95,
        "regex": re.compile(r"(?<![0-9A-Za-z_\-])(\d{8,10}:AA[A-Za-z0-9_\-]{33})(?![0-9A-Za-z_\-])"),
    },
    {
        "rule_id": "spotify_oauth_access_token",
        "name": "Spotify OAuth 2.0 Access Token",
        "category": "Spotify OAuth & Playback",
        "uri": "https://developer.spotify.com/dashboard",
        "confidence": 0.97,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(BQ[A-Za-z0-9_\-]{120,360})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "spotify_oauth_refresh_token",
        "name": "Spotify OAuth 2.0 Refresh Token",
        "category": "Spotify OAuth & Playback",
        "uri": "https://developer.spotify.com/dashboard",
        "confidence": 0.97,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(AQ[A-Za-z0-9_\-]{90,260})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "devcore_master_key",
        "name": "DevCore Hardware Master Key",
        "category": "DevCore Core Security",
        "uri": "",
        "confidence": 0.99,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(DEVCORE-MASTER-[0-9a-fA-F]{64})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "devcore_session_bearer",
        "name": "DevCore Bearer Session Token",
        "category": "DevCore Auth Token",
        "uri": "",
        "confidence": 0.99,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(sec-[0-9a-fA-F]{64})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "devcore_access_key",
        "name": "DevCore RBAC User Access Key",
        "category": "DevCore Auth Token",
        "uri": "",
        "confidence": 0.98,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(key-[0-9a-fA-F]{32})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "raugus_jit_token",
        "name": "Raugus Super Admin JIT Elevation Token",
        "category": "DevCore Core Security",
        "uri": "",
        "confidence": 0.99,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(raugus-jit-[0-9a-fA-F]{32})(?![A-Za-z0-9_\-])"),
    },
    {
        "rule_id": "eprofile_transit_key",
        "name": "e_profile AES-256-GCM Transit Key ID",
        "category": "e_profile Custom Login Token",
        "uri": "",
        "confidence": 0.95,
        "regex": re.compile(r"(?<![A-Za-z0-9_\-])(tr_[0-9a-fA-F]{16})(?![A-Za-z0-9_\-])"),
    },
]

_PEM_PRIV_KEY_RE = re.compile(
    r"(-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY-----[\s\S]{64,8192}?-----END (?:RSA |EC |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY-----)"
)
_DB_URI_RE = re.compile(
    r"\b((?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqp|amqps)://([^:\s/@\"']+):([^@\s/\"']{4,128})@([^\s/\"']+))"
)
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_\-])(eyJ[A-Za-z0-9_\-]{10,200}\.eyJ[A-Za-z0-9_\-]{10,500}\.[A-Za-z0-9_\-]{16,300})(?![A-Za-z0-9_\-])"
)
_SECRET_KEY_NAME_RE = re.compile(
    r"(?i)(?:^|[_\-\.])(pass(?:word|wd|phrase)?|pwd|secret|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|auth[_-]?token|private[_-]?key|app[_-]?password|smtp[_-]?pass(?:word)?|sync[_-]?secret|master[_-]?key|signing[_-]?key|webhook[_-]?secret|admin[_-]?key|employer[_-]?key|auth[_-]?key|encryption[_-]?key|credentials)(?:$|[_\-\.])"
)
_USER_KEY_NAME_RE = re.compile(
    r"(?i)(?:^|[_\-\.])(user(?:name)?|email|mail[_-]?user(?:name)?|smtp[_-]?user|gmail[_-]?user|client[_-]?id|account|login|owner)(?:$|[_\-\.])"
)
_INLINE_SECRET_ASSIGN_RE = re.compile(
    r"(?m)^\s*(?:export\s+)?([A-Za-z0-9_]*(?:CLIENT_SECRET|API_SECRET|APP_SECRET|SECRET_KEY|ADMIN_KEY|EMPLOYER_KEY|PRIVATE_KEY|ACCESS_TOKEN|REFRESH_TOKEN|AUTH_TOKEN))\s*=\s*['\"]([^'\"\r\n]{8,256})['\"]"
)
_INLINE_CLIENT_ID_RE = re.compile(
    r"(?m)^\s*(?:export\s+)?([A-Za-z0-9_]*CLIENT_ID)\s*=\s*['\"]([^'\"\r\n]{8,128})['\"]"
)


class MachineSecretHarvester:
    """Multi-layer secret, token, OAuth, and password scraper with BOM/UTF-16 safe reads,
    structured .env/JSON/INI/PEM/URI extractors, prefix-anchored rule engine, Shannon entropy
    and placeholder filtering, and keyed HMAC-SHA256 deduplication."""

    PRUNE_DIRS = {
        ".git", "node_modules", "venv", ".venv", "env", "__pycache__", ".pytest_cache",
        ".mypy_cache", "site-packages", "dist", "build", "backups", "patches", "cache",
        ".system_generated", "CLAUDE-SECURITY", "Trash", ".cache", ".npm",
    }
    SKIP_SUFFIXES = {
        ".vault", ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".png", ".jpg", ".jpeg",
        ".gif", ".webp", ".ico", ".mp3", ".mp4", ".wav", ".ogg", ".pdf", ".zip", ".tar",
        ".gz", ".7z", ".whl", ".db", ".sqlite", ".sqlite3", ".lock", ".min.js", ".min.css",
    }

    def __init__(self, user_root: Optional[Path] = None, hmac_seed: bytes = b"X_SHI3LD_X_HARVESTER_FINGERPRINT_KEY") -> None:
        self.user_root = Path(user_root or "/mnt/c/Users/michael").resolve()
        self.wsl_home = Path.home().resolve()
        self._hmac_key = hmac_seed
        self._last_report: Dict[str, Any] = {"findings": [], "errors": [], "skipped": [], "stats": {}}

    def _fingerprint(self, secret_val: str) -> str:
        return hmac.new(self._hmac_key, secret_val.strip().encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    @staticmethod
    def _is_placeholder_or_noise(val: str, is_prefix_anchored: bool = False, is_password_field: bool = False) -> bool:
        s = (val or "").strip()
        if not s or len(s) < 4:
            return True
        if _PLACEHOLDER_PATTERNS.match(s):
            return True
        lower = s.lower()
        if any(tok in lower for tok in ("your_api_key", "your-api-key", "changeme", "<redacted", "example.com", "placeholder", "xxxx")):
            return True
        if s.startswith(("/mnt/", "/home/", "/var/", "/etc/", "C:\\", "c:\\")) or lower.endswith((".json", ".pem", ".crt", ".key", ".sqlite")):
            return True
        if len(set(s)) <= 2 and len(s) >= 5:
            return True
        if _UUID_RE.match(s):
            return True
        if is_prefix_anchored:
            if "XXXX" in s or "xxxx" in s or _shannon_entropy(s) < 2.5:
                return True
            return False
        if is_password_field:
            return len(s) < 6
        if _HEX_HASH_RE.match(s) and _shannon_entropy(s) < 3.1:
            return True
        if len(s) < 12 or _shannon_entropy(s) < 3.2:
            return True
        return False

    @staticmethod
    def _is_valid_jwt(token: str) -> bool:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        try:
            hdr_b64 = parts[0] + "=" * (-len(parts[0]) % 4)
            hdr = json.loads(base64.urlsafe_b64decode(hdr_b64).decode("utf-8"))
            return isinstance(hdr, dict) and ("alg" in hdr or "typ" in hdr)
        except Exception:
            return False

    def safe_read_text(self, path: Path, max_bytes: int = 1_572_864) -> Tuple[Optional[str], Optional[str]]:
        try:
            if not path.exists() or not path.is_file():
                return None, "not_a_file"
            if path.suffix.lower() in self.SKIP_SUFFIXES or path.name.endswith(".vault"):
                return None, "skipped_extension"
            st = path.stat()
            if st.st_size == 0:
                return None, "empty_file"
            if st.st_size > max_bytes:
                return None, f"exceeds_size_cap({st.st_size})"
            raw = path.read_bytes()
            if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                return raw.decode("utf-16"), None
            if b"\x00" in raw[:4096]:
                if raw[1:4:2] == b"\x00\x00":
                    try:
                        return raw.decode("utf-16-le"), None
                    except Exception:
                        pass
                return None, "binary_nul_detected"
            return raw.decode("utf-8-sig"), None
        except UnicodeDecodeError:
            try:
                return raw.decode("latin-1"), None
            except Exception as e:
                return None, f"decode_error:{type(e).__name__}"
        except Exception as e:
            return None, f"io_error:{type(e).__name__}"

    @staticmethod
    def parse_dotenv(text: str) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip().lstrip("\ufeff")
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().lstrip("\ufeff")
            v = v.strip()
            if not k:
                continue
            if v and v[0] in ('"', "'"):
                q = v[0]
                end_idx = v.find(q, 1)
                if end_idx != -1:
                    v = v[1:end_idx]
                else:
                    v = v[1:]
            else:
                if " #" in v:
                    v = v.split(" #", 1)[0].strip()
                elif "\t#" in v:
                    v = v.split("\t#", 1)[0].strip()
            parsed[k] = v
        return parsed

    def scan_text(
        self,
        text: str,
        source_label: str = "ad_hoc_input",
        include_raw: bool = False,
        default_username: str = "",
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if not text:
            return results

        for m in _PEM_PRIV_KEY_RE.finditer(text):
            pem_block = m.group(1).strip()
            fp = self._fingerprint(pem_block)
            item: Dict[str, Any] = {
                "key_id": f"pem_privkey_{fp[:8]}",
                "rule_id": "pem_private_key",
                "fingerprint": fp,
                "name": f"PEM Private Key ({Path(source_label).name})",
                "category": "Cryptographic Private Key",
                "username": default_username or "PEM_PRIVATE_KEY",
                "source": source_label,
                "masked": _mask_secret(pem_block.splitlines()[1] if len(pem_block.splitlines()) > 1 else pem_block),
                "confidence": 0.99,
                "notes": f"Multiline private key extracted from {source_label}",
                "uri": "",
            }
            if include_raw:
                item["secret"] = pem_block
            results.append(item)

        for m in _DB_URI_RE.finditer(text):
            full_uri, db_user, db_pass, db_host = m.group(1), m.group(2), m.group(3), m.group(4)
            if self._is_placeholder_or_noise(db_pass, is_password_field=True):
                continue
            fp = self._fingerprint(full_uri)
            scheme = full_uri.split("://", 1)[0]
            item = {
                "key_id": f"db_uri_{scheme}_{fp[:8]}",
                "rule_id": "database_connection_uri",
                "fingerprint": fp,
                "name": f"Database Connection URI ({scheme}://{db_host})",
                "category": "Database & Broker URI",
                "username": db_user,
                "source": source_label,
                "masked": f"{scheme}://{db_user}:{_mask_secret(db_pass)}@{db_host}",
                "confidence": 0.96,
                "notes": f"Connection string harvested from {source_label}",
                "uri": f"{scheme}://{db_host}",
            }
            if include_raw:
                item["secret"] = full_uri
            results.append(item)

        for rule in _PREFIX_RULES:
            for m in rule["regex"].finditer(text):
                sec_val = m.group(1).strip()
                if self._is_placeholder_or_noise(sec_val, is_prefix_anchored=True):
                    continue
                fp = self._fingerprint(sec_val)
                item = {
                    "key_id": f"{rule['rule_id']}_{fp[:8]}",
                    "rule_id": rule["rule_id"],
                    "fingerprint": fp,
                    "name": f"{rule['name']} ({Path(source_label).parent.name or Path(source_label).name})",
                    "category": rule["category"],
                    "username": default_username or rule["rule_id"],
                    "source": source_label,
                    "masked": _mask_secret(sec_val),
                    "confidence": rule["confidence"],
                    "notes": f"Harvested from {source_label} (original preserved)",
                    "uri": rule["uri"],
                }
                if include_raw:
                    item["secret"] = sec_val
                results.append(item)

        for m in _JWT_RE.finditer(text):
            jwt_val = m.group(1).strip()
            if not self._is_valid_jwt(jwt_val):
                continue
            fp = self._fingerprint(jwt_val)
            item = {
                "key_id": f"jwt_token_{fp[:8]}",
                "rule_id": "jwt_bearer_token",
                "fingerprint": fp,
                "name": f"Signed JWT Bearer Token ({Path(source_label).name})",
                "category": "OAuth / JWT Token",
                "username": default_username or "jwt_bearer",
                "source": source_label,
                "masked": _mask_secret(jwt_val),
                "confidence": 0.92,
                "notes": f"Validated JWT header from {source_label}",
                "uri": "",
            }
            if include_raw:
                item["secret"] = jwt_val
            results.append(item)

        seen_fps = {r["fingerprint"] for r in results}
        paired_client_id = ""
        cid_match = _INLINE_CLIENT_ID_RE.search(text)
        if cid_match:
            paired_client_id = cid_match.group(2).strip()

        for m in _INLINE_SECRET_ASSIGN_RE.finditer(text):
            var_name, sec_val = m.group(1).strip(), m.group(2).strip()
            if self._is_placeholder_or_noise(sec_val, is_password_field=True):
                continue
            fp = self._fingerprint(sec_val)
            if fp in seen_fps:
                continue
            seen_fps.add(fp)
            is_spotify_ctx = "spotify" in text.lower() or "spotipy" in text.lower()
            proj_name = Path(source_label).parent.name or Path(source_label).name
            if is_spotify_ctx and "CLIENT_SECRET" in var_name.upper():
                item_name = f"Spotify Web API Client Secret ({proj_name})"
                cat = "Spotify OAuth & Playback"
                uri = "https://developer.spotify.com/dashboard"
                uname = paired_client_id or default_username or var_name
            else:
                item_name = f"Hardcoded {var_name} ({proj_name})"
                cat = "Application Secret"
                uri = ""
                uname = paired_client_id or default_username or var_name
            item = {
                "key_id": f"code_assign_{var_name.lower()}_{fp[:8]}",
                "rule_id": "inline_secret_assignment",
                "fingerprint": fp,
                "name": item_name,
                "category": cat,
                "username": uname,
                "source": f"{source_label}:{var_name}",
                "masked": _mask_secret(sec_val),
                "confidence": 0.96 if is_spotify_ctx else 0.91,
                "notes": f"Assigned to {var_name}" + (f" (Client ID: {paired_client_id})" if paired_client_id else ""),
                "uri": uri,
            }
            if include_raw:
                item["secret"] = sec_val
            results.append(item)

        return results

    def _extract_dotenv_file(self, path: Path, source_label: str, include_raw: bool) -> List[Dict[str, Any]]:
        txt, err = self.safe_read_text(path)
        if err or not txt:
            if err and err not in ("not_a_file", "empty_file"):
                self._last_report["skipped"].append({"source": source_label, "reason": err})
            return []

        kv = self.parse_dotenv(txt)
        discovered: List[Dict[str, Any]] = []

        example_kv: Dict[str, str] = {}
        example_path = path.parent / ".env.example"
        if example_path.is_file():
            ex_txt, _ = self.safe_read_text(example_path)
            if ex_txt:
                example_kv = self.parse_dotenv(ex_txt)

        paired_user = ""
        for k, v in kv.items():
            if _USER_KEY_NAME_RE.search(k) and v and not self._is_placeholder_or_noise(v, is_password_field=True):
                paired_user = v
                break

        project_tag = path.parent.name or "workspace"
        for k, v in kv.items():
            if not v:
                continue
            inline_hits = self.scan_text(v, source_label=f"{source_label}:{k}", include_raw=include_raw, default_username=paired_user or k)
            if inline_hits:
                for hit in inline_hits:
                    hit["notes"] = f"Env key: {k} in {source_label}"
                    discovered.append(hit)
                continue

            upper_k = k.upper()
            is_smtp_pass = upper_k in ("SMTP_PASS", "SMTP_PASSWORD", "MAIL_PASSWORD", "GMAIL_APP_PASSWORD")
            is_login_key = upper_k in ("ADMIN_KEY", "EMPLOYER_KEY", "AUTH_KEY", "MASTER_KEY")
            is_secret_key = is_smtp_pass or is_login_key or bool(_SECRET_KEY_NAME_RE.search(k))
            if not is_secret_key:
                continue

            if self._is_placeholder_or_noise(v, is_password_field=True):
                self._last_report["skipped"].append({"source": f"{source_label}:{k}", "reason": "placeholder_or_low_entropy"})
                continue

            matches_example = bool(example_kv.get(k) and example_kv.get(k) == v)
            warn_suffix = " [WARNING: Matches .env.example default!]" if matches_example else ""
            fp = self._fingerprint(v)
            if is_smtp_pass:
                name = f"Google Gmail SMTP App Password ({project_tag}){warn_suffix}"
                cat = "Google Workspace / SMTP"
                uname = paired_user or "smtp_user"
                uri = "https://myaccount.google.com/apppasswords"
                key_id = f"smtp_app_password_{project_tag}_{fp[:8]}"
            elif is_login_key:
                name = f"{project_tag} Handshake Login Key ({k}){warn_suffix}"
                cat = f"{project_tag} Custom Login Token"
                uname = k
                uri = ""
                key_id = f"login_key_{project_tag}_{k.lower()}_{fp[:8]}"
            else:
                name = f"{project_tag} {k}{warn_suffix}"
                cat = "Infrastructure Secret"
                uname = paired_user or k
                uri = ""
                key_id = f"env_{project_tag}_{k.lower()}_{fp[:8]}"

            item: Dict[str, Any] = {
                "key_id": key_id,
                "rule_id": "dotenv_secret_var",
                "fingerprint": fp,
                "name": name,
                "category": cat,
                "username": uname,
                "source": source_label,
                "masked": _mask_secret(v),
                "confidence": 0.95 if (is_smtp_pass or is_login_key) else 0.90,
                "notes": f"Env key: {k}" + (" (ALERT: Unchanged from .env.example)" if matches_example else ""),
                "uri": uri,
            }
            if include_raw:
                item["secret"] = v
            discovered.append(item)

        return discovered

    def _extract_json_credentials(self, path: Path, source_label: str, include_raw: bool) -> List[Dict[str, Any]]:
        txt, err = self.safe_read_text(path)
        if err or not txt:
            if err and err not in ("not_a_file", "empty_file"):
                self._last_report["skipped"].append({"source": source_label, "reason": err})
            return []
        try:
            raw = json.loads(txt)
        except Exception as e:
            self._last_report["errors"].append({"source": source_label, "error": f"json_parse_error:{type(e).__name__}"})
            return []

        discovered: List[Dict[str, Any]] = []
        root_email = ""
        if isinstance(raw, dict):
            root_email = str(
                raw.get("id_token_email")
                or raw.get("client_email")
                or raw.get("username")
                or raw.get("email")
                or ""
            )

        def _walk(node: Any, path_prefix: str = "", inherited_user: str = "") -> None:
            if isinstance(node, dict):
                local_user = str(
                    node.get("client_id")
                    or node.get("client_email")
                    or node.get("id_token_email")
                    or node.get("username")
                    or node.get("email")
                    or node.get("account")
                    or inherited_user
                    or root_email
                    or ""
                )
                proj_id = str(node.get("project_id") or "")
                node_type = str(node.get("type") or "")
                scope_str = str(node.get("scope") or "")
                is_spotify_node = (
                    "spotify" in path.name.lower()
                    or "SPOTIFY" in node_type.upper()
                    or "user-modify-playback-state" in scope_str
                    or "user-read-playback-state" in scope_str
                )
                for k, v in node.items():
                    cur_key = f"{path_prefix}.{k}" if path_prefix else k
                    if isinstance(v, (dict, list)):
                        _walk(v, cur_key, local_user)
                    elif isinstance(v, str) and v.strip():
                        val = v.strip()
                        if k == "client_secret" and not self._is_placeholder_or_noise(val, is_password_field=True):
                            fp = self._fingerprint(val)
                            item: Dict[str, Any] = {
                                "key_id": f"google_oauth_client_secret_{fp[:8]}",
                                "rule_id": "oauth_client_secret_json",
                                "fingerprint": fp,
                                "name": "Google Cloud OAuth 2.0 Client Secret",
                                "category": "Google Cloud OAuth",
                                "username": local_user or "oauth_client",
                                "source": source_label,
                                "masked": _mask_secret(val),
                                "confidence": 0.99,
                                "notes": f"Project ID: {proj_id or 'unknown'} ({cur_key})",
                                "uri": "https://console.cloud.google.com/apis/credentials",
                            }
                            if include_raw:
                                item["secret"] = val
                            discovered.append(item)
                        elif k == "private_key" and "BEGIN" in val and "PRIVATE KEY" in val:
                            fp = self._fingerprint(val)
                            item = {
                                "key_id": f"service_account_privkey_{fp[:8]}",
                                "rule_id": "gcp_service_account_key",
                                "fingerprint": fp,
                                "name": f"Service Account Private Key ({proj_id or path.name})",
                                "category": "Cloud Service Account",
                                "username": local_user or "service_account",
                                "source": source_label,
                                "masked": _mask_secret(val),
                                "confidence": 0.99,
                                "notes": f"Service Account key in {source_label}",
                                "uri": "https://console.cloud.google.com/iam-admin/serviceaccounts",
                            }
                            if include_raw:
                                item["secret"] = val
                            discovered.append(item)
                        elif k == "credentials" and ("SPOTIFY" in node_type.upper() or is_spotify_node):
                            fp = self._fingerprint(val)
                            item = {
                                "key_id": f"spotify_stored_creds_{fp[:8]}",
                                "rule_id": "spotify_librespot_credentials",
                                "fingerprint": fp,
                                "name": "Spotify Stored Account Credentials (Librespot)",
                                "category": "Spotify OAuth & Playback",
                                "username": local_user or "spotify_user",
                                "source": source_label,
                                "masked": _mask_secret(val),
                                "confidence": 0.99,
                                "notes": f"Stored {node_type or 'Spotify'} blob in {source_label}",
                                "uri": "https://developer.spotify.com/dashboard",
                            }
                            if include_raw:
                                item["secret"] = val
                            discovered.append(item)
                        elif _SECRET_KEY_NAME_RE.search(k) and not self._is_placeholder_or_noise(val, is_password_field=True):
                            fp = self._fingerprint(val)
                            if is_spotify_node and k in ("access_token", "refresh_token"):
                                tok_kind = "Access Token" if k == "access_token" else "Refresh Token"
                                name = f"Spotify OAuth 2.0 {tok_kind}"
                                cat = "Spotify OAuth & Playback"
                                uri = "https://developer.spotify.com/dashboard"
                                rule_id = f"spotify_oauth_{k}"
                                notes = f"Scope: {scope_str}" if scope_str else f"JSON field '{cur_key}' from {source_label}"
                            elif val.startswith("ya29."):
                                name = f"Google OAuth 2.0 Access Token ({path.name})"
                                cat = "Google OAuth Token"
                                uri = "https://console.cloud.google.com/apis/credentials"
                                rule_id = "google_oauth_access_token"
                                notes = f"OAuth access_token in {source_label}"
                            elif val.startswith("1//"):
                                name = f"Google OAuth 2.0 Refresh Token ({path.name})"
                                cat = "Google OAuth Token"
                                uri = "https://console.cloud.google.com/apis/credentials"
                                rule_id = "google_oauth_refresh_token"
                                notes = f"OAuth refresh_token in {source_label}"
                            else:
                                name = f"JSON Credential ({k} in {path.name})"
                                cat = "API Key / Token"
                                uri = ""
                                rule_id = "json_secret_field"
                                notes = f"JSON field '{cur_key}' from {source_label}"
                            item = {
                                "key_id": f"{rule_id}_{fp[:8]}",
                                "rule_id": rule_id,
                                "fingerprint": fp,
                                "name": name,
                                "category": cat,
                                "username": local_user or k,
                                "source": source_label,
                                "masked": _mask_secret(val),
                                "confidence": 0.98 if (is_spotify_node or val.startswith(("ya29.", "1//"))) else 0.91,
                                "notes": notes,
                                "uri": uri,
                            }
                            if include_raw:
                                item["secret"] = val
                            discovered.append(item)
            elif isinstance(node, list):
                for idx, elem in enumerate(node[:50]):
                    _walk(elem, f"{path_prefix}[{idx}]", inherited_user)

        _walk(raw)
        return discovered

    def _extract_eprofile_profiles(self, path: Path, source_label: str, include_raw: bool) -> List[Dict[str, Any]]:
        txt, err = self.safe_read_text(path)
        if err or not txt:
            return []
        try:
            raw = json.loads(txt)
        except Exception as e:
            self._last_report["errors"].append({"source": source_label, "error": f"json_parse_error:{type(e).__name__}"})
            return []

        profiles_map = raw.get("data", raw) if isinstance(raw, dict) else {}
        if not isinstance(profiles_map, dict):
            return []

        discovered: List[Dict[str, Any]] = []
        for token_sha256, meta in profiles_map.items():
            if not isinstance(meta, dict):
                continue
            uname = str(meta.get("username") or "unknown")
            label = str(meta.get("label") or "Profile")
            magic_uuid = str(meta.get("uuid") or "").strip()
            bypass_on = bool(meta.get("bypass_enabled", False))
            is_admin = bool(meta.get("is_admin", False))
            is_employer = bool(meta.get("is_employer", False))
            perms = meta.get("permissions", [])
            role_tag = "Root Admin" if is_admin else ("Employer" if is_employer else "User")

            if bypass_on and magic_uuid:
                fp_magic = self._fingerprint(magic_uuid)
                magic_item: Dict[str, Any] = {
                    "key_id": f"eprofile_magic_link_{uname.lower()}_{fp_magic[:8]}",
                    "rule_id": "eprofile_magic_link_token",
                    "fingerprint": fp_magic,
                    "name": f"e_profile Active Magic Link Token ({uname} / {label})",
                    "category": "e_profile Custom Login Token",
                    "username": f"{uname} ({role_tag})",
                    "source": source_label,
                    "masked": _mask_secret(magic_uuid),
                    "confidence": 0.99,
                    "notes": f"Passwordless /access/<uuid> bypass enabled; perms: {', '.join(perms[:5])}",
                    "uri": f"/access/{magic_uuid}",
                }
                if include_raw:
                    magic_item["secret"] = magic_uuid
                discovered.append(magic_item)

            if isinstance(token_sha256, str) and len(token_sha256) == 64:
                fp_hash = self._fingerprint(token_sha256)
                hash_item: Dict[str, Any] = {
                    "key_id": f"eprofile_login_hash_{uname.lower()}_{fp_hash[:8]}",
                    "rule_id": "eprofile_login_token_sha256",
                    "fingerprint": fp_hash,
                    "name": f"e_profile Login Token SHA-256 Verifier ({uname} / {label})",
                    "category": "e_profile Custom Login Token",
                    "username": f"{uname} ({role_tag})",
                    "source": source_label,
                    "masked": _mask_secret(token_sha256),
                    "confidence": 0.95,
                    "notes": f"SHA-256 token hash in profiles.json (bypass_enabled={bypass_on})",
                    "uri": "/login",
                }
                if include_raw:
                    hash_item["secret"] = token_sha256
                discovered.append(hash_item)

        return discovered

    def scan_report(self, include_raw: bool = False) -> Dict[str, Any]:
        self._last_report = {"findings": [], "errors": [], "skipped": [], "stats": {}}
        t0 = time.monotonic()
        raw_findings: List[Dict[str, Any]] = []
        files_checked = 0

        docs = self.user_root / "Documents"
        downloads = self.user_root / "Downloads"

        oauth_file = downloads / "credentials.json"
        if oauth_file.is_file():
            files_checked += 1
            raw_findings.extend(self._extract_json_credentials(oauth_file, "Downloads/credentials.json", include_raw))

        known_scripts = [
            (docs / "describe" / "t.py", "Documents/describe/t.py", "Google Gemini Generative Language API Key (describe)"),
            (docs / "tts+gemeni" / "streamTTS.py", "Documents/tts+gemeni/streamTTS.py", "Google Gemini 2.5 Flash TTS API Key"),
            (docs / "Audio_pllayback_suite" / "t.py", "Documents/Audio_pllayback_suite/t.py", "Spotify Web API Client Secret (Audio_pllayback_suite)"),
        ]
        for fp, src_label, custom_title in known_scripts:
            if fp.is_file():
                files_checked += 1
                txt, err = self.safe_read_text(fp)
                if txt:
                    hits = self.scan_text(txt, source_label=src_label, include_raw=include_raw, default_username="API_Key")
                    for idx, h in enumerate(hits):
                        if idx == 0 and custom_title:
                            h["name"] = custom_title
                        raw_findings.append(h)
                elif err:
                    self._last_report["skipped"].append({"source": src_label, "reason": err})

        for tok_path, label, src_label, cat, uname, uri in [
            (
                docs / "DevCore" / "antigravity-oauth-token",
                "Google Antigravity OAuth Token (DevCore)",
                "Documents/DevCore/antigravity-oauth-token",
                "Google OAuth Token",
                "antigravity-oauth",
                "",
            ),
            (
                self.wsl_home / ".gemini" / "antigravity-cli" / "antigravity-oauth-token",
                "Google Antigravity CLI OAuth Token",
                "~/.gemini/antigravity-cli/antigravity-oauth-token",
                "Google OAuth Token",
                "antigravity-oauth",
                "",
            ),
            (
                docs / "e_profile" / "gethub_token.txt",
                "GitHub Personal Access Token (e_profile)",
                "Documents/e_profile/gethub_token.txt",
                "Git & Deployment",
                "github_pat",
                "https://github.com/settings/tokens",
            ),
            (
                docs / "DevCore" / ".devcore_master.key",
                "DevCore Hardware Master Key (.devcore_master.key)",
                "Documents/DevCore/.devcore_master.key",
                "DevCore Core Security",
                "DevCore_Root_Hardware_Key",
                "",
            ),
            (
                docs / "e_profile" / "cache" / ".eprofile_master.key",
                "e_profile Local KMS Master Key (.eprofile_master.key)",
                "Documents/e_profile/cache/.eprofile_master.key",
                "e_profile Custom Login Token",
                "eprofile_kms_master",
                "",
            ),
        ]:
            if tok_path.is_file():
                files_checked += 1
                txt, err = self.safe_read_text(tok_path)
                if txt:
                    stripped = txt.strip()
                    if stripped.startswith("{"):
                        json_hits = self._extract_json_credentials(tok_path, src_label, include_raw)
                        if json_hits:
                            raw_findings.extend(json_hits)
                            continue
                    first_non_empty = next(
                        (ln.strip() for ln in txt.splitlines() if ln.strip() and not ln.strip().startswith("#")),
                        "",
                    )
                    if first_non_empty and not self._is_placeholder_or_noise(first_non_empty, is_password_field=True):
                        fp_hash = self._fingerprint(first_non_empty)
                        item: Dict[str, Any] = {
                            "key_id": f"token_file_{fp_hash[:8]}",
                            "rule_id": "dedicated_token_file",
                            "fingerprint": fp_hash,
                            "name": label,
                            "category": cat,
                            "username": uname,
                            "source": src_label,
                            "masked": _mask_secret(first_non_empty),
                            "confidence": 0.99,
                            "notes": f"Dedicated token/key file ({src_label})",
                            "uri": uri,
                        }
                        if include_raw:
                            item["secret"] = first_non_empty
                        raw_findings.append(item)
                    else:
                        self._last_report["skipped"].append({"source": src_label, "reason": "format_mismatch_or_placeholder"})
                elif err:
                    self._last_report["skipped"].append({"source": src_label, "reason": err})

        eprofile_profiles = docs / "e_profile" / "profiles.json"
        if eprofile_profiles.is_file():
            files_checked += 1
            raw_findings.extend(
                self._extract_eprofile_profiles(eprofile_profiles, "Documents/e_profile/profiles.json", include_raw)
            )

        jit_lease_file = docs / "DevCore" / "security" / ".jit_elevation_lease.json"
        if jit_lease_file.is_file():
            files_checked += 1
            txt, _ = self.safe_read_text(jit_lease_file)
            if txt:
                try:
                    lease = json.loads(txt)
                    if isinstance(lease, dict) and lease.get("token_sha256"):
                        exp_at = float(lease.get("expires_at") or 0)
                        is_live = exp_at > time.time()
                        fp_jit = self._fingerprint(str(lease["token_sha256"]))
                        jit_item: Dict[str, Any] = {
                            "key_id": f"devcore_jit_lease_{fp_jit[:8]}",
                            "rule_id": "raugus_jit_lease_sha256",
                            "fingerprint": fp_jit,
                            "name": f"DevCore Super Admin JIT Lease ({'ACTIVE' if is_live else 'EXPIRED'})",
                            "category": "DevCore Core Security",
                            "username": str(lease.get("lease_id") or "jit_admin"),
                            "source": "Documents/DevCore/security/.jit_elevation_lease.json",
                            "masked": _mask_secret(str(lease["token_sha256"])),
                            "confidence": 0.98,
                            "notes": f"Issued by {lease.get('issued_by', 'cli')}, scope={lease.get('scope')}",
                            "uri": "",
                        }
                        if include_raw:
                            jit_item["secret"] = str(lease["token_sha256"])
                        raw_findings.append(jit_item)
                except Exception:
                    pass

        helpline_doc = docs / "thecyberhelpline" / "New Text Document.txt"
        if helpline_doc.is_file():
            files_checked += 1
            txt, err = self.safe_read_text(helpline_doc)
            if txt:
                code_lines = [ln.strip() for ln in txt.splitlines() if ln.strip() and len(ln.strip()) <= 32]
                if code_lines:
                    clean_block = "\n".join(code_lines)
                    fp_hash = self._fingerprint(clean_block)
                    item = {
                        "key_id": f"cyber_helpline_2fa_{fp_hash[:8]}",
                        "rule_id": "backup_codes_block",
                        "fingerprint": fp_hash,
                        "name": "The Cyber Helpline 2FA Backup Codes",
                        "category": "2FA Backup Codes",
                        "username": "TheCyberHelpline",
                        "source": "Documents/thecyberhelpline/New Text Document.txt",
                        "masked": _mask_secret(code_lines[0]),
                        "confidence": 0.95,
                        "notes": f"Emergency 2FA recovery codes ({len(code_lines)} codes)",
                        "uri": "https://www.thecyberhelpline.com",
                    }
                    if include_raw:
                        item["secret"] = clean_block
                    raw_findings.append(item)

        links_doc = docs / "links.txt"
        if links_doc.is_file():
            files_checked += 1
            txt, err = self.safe_read_text(links_doc)
            if txt and txt.strip():
                clean_val = txt.strip()
                uri_match = re.search(r"(https?://[^\s\"'<>]+)", clean_val)
                extracted_uri = uri_match.group(1) if uri_match else ""
                fp_hash = self._fingerprint(clean_val)
                item = {
                    "key_id": f"absa_portal_links_{fp_hash[:8]}",
                    "rule_id": "portal_credential_note",
                    "fingerprint": fp_hash,
                    "name": "ABSA Portal & Saved Links Credential",
                    "category": "Portal Login",
                    "username": "ABSA_Portal",
                    "source": "Documents/links.txt",
                    "masked": _mask_secret(clean_val.splitlines()[0]),
                    "confidence": 0.90,
                    "notes": "Harvested from Documents/links.txt",
                    "uri": extracted_uri,
                }
                if include_raw:
                    item["secret"] = clean_val
                raw_findings.append(item)

        if docs.is_dir():
            candidate_dirs = [docs]
            try:
                for entry in os.scandir(docs):
                    if entry.is_dir(follow_symlinks=False) and entry.name not in self.PRUNE_DIRS and not entry.name.startswith("."):
                        candidate_dirs.append(Path(entry.path))
            except Exception:
                pass

            for dpath in candidate_dirs[:40]:
                if time.monotonic() - t0 > 3.0 or files_checked > 220:
                    break
                try:
                    for entry in os.scandir(dpath):
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        fname = entry.name
                        lower_name = fname.lower()
                        fpath = Path(entry.path)
                        try:
                            rel_label = f"Documents/{fpath.relative_to(docs).as_posix()}"
                        except Exception:
                            rel_label = fname

                        if lower_name == ".env" or (lower_name.startswith(".env.") and not lower_name.endswith((".example", ".sample", ".template", ".vault"))):
                            files_checked += 1
                            raw_findings.extend(self._extract_dotenv_file(fpath, rel_label, include_raw))
                        elif lower_name in ("credentials.json", "client_secret.json", "service_account.json", ".spotify_token_cache") or lower_name.startswith(".spotify_token_cache"):
                            files_checked += 1
                            raw_findings.extend(self._extract_json_credentials(fpath, rel_label, include_raw))
                        elif lower_name.endswith(".pem"):
                            files_checked += 1
                            txt, _ = self.safe_read_text(fpath)
                            if txt and "PRIVATE KEY" in txt:
                                raw_findings.extend(self.scan_text(txt, source_label=rel_label, include_raw=include_raw))
                except Exception:
                    pass

        deduped_map: Dict[str, Dict[str, Any]] = {}
        for f in raw_findings:
            fp_key = f.get("fingerprint") or f.get("key_id") or str(uuid.uuid4())
            if fp_key not in deduped_map:
                f["sources"] = [f["source"]]
                deduped_map[fp_key] = f
            else:
                existing = deduped_map[fp_key]
                if f["source"] not in existing["sources"]:
                    existing["sources"].append(f["source"])
                    extra_count = len(existing["sources"]) - 1
                    existing["source"] = f"{existing['sources'][0]} (+{extra_count} duplicate location{'s' if extra_count > 1 else ''})"

        final_list = list(deduped_map.values())
        self._last_report["findings"] = final_list
        self._last_report["stats"] = {
            "files_inspected": files_checked,
            "raw_matches": len(raw_findings),
            "unique_secrets": len(final_list),
            "skipped_count": len(self._last_report["skipped"]),
            "error_count": len(self._last_report["errors"]),
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
        return self._last_report

    def scan(self, include_raw: bool = False) -> List[Dict[str, Any]]:
        report = self.scan_report(include_raw=include_raw)
        return report["findings"]


class UnifiedVaultService:
    """Coordinates Bitwarden CLI (`bw`), Local X_SHI3LD_X `.vault`, KMS Keychain, and Transit Envelopes."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent).resolve()
        self.vault_file = self.base_dir / "cache" / "vault_store.json.vault"
        self.transit = TransitCryptoEnvelope()
        self.keychain = EProfileKeychain(self.base_dir)
        self.shield = ShieldVaultContainer(self.vault_file)
        self.bw = BitwardenCliBridge(shield_fallback=self.shield)
        self.harvester = MachineSecretHarvester()

    def get_protected_files_inventory(self) -> List[Dict[str, Any]]:
        targets = [
            ("profiles.json", self.base_dir / "profiles.json"),
            ("gethub_token.txt", self.base_dir / "gethub_token.txt"),
            (".env", self.base_dir / ".env"),
            ("cache/bridge_queue.json", self.base_dir / "cache" / "bridge_queue.json"),
        ]
        out = []
        for label, p in targets:
            v_p = Path(str(p) + ".vault")
            out.append({
                "label": label,
                "source_exists": p.is_file(),
                "vault_exists": v_p.is_file(),
                "vault_name": v_p.name if v_p.is_file() else f"{p.name}.vault",
                "vault_size_bytes": v_p.stat().st_size if v_p.is_file() else 0,
            })
        return out

    def _try_hardware_unlock_local(self) -> bool:
        if self.shield.is_unlocked():
            return True
        if not self.shield.exists():
            return False
        try:
            raw_master = self.keychain.master_key_path.read_text(encoding="utf-8").strip()
            if raw_master:
                self.shield.unlock("admin", f"devcore_{raw_master[:16]}")
                return True
        except Exception:
            pass
        return False

    def get_overview(self) -> Dict[str, Any]:
        self._try_hardware_unlock_local()
        bw_stat = self.bw.get_status()
        shield_stat = self.shield.get_status()
        kms_stat = self.keychain.get_status()
        if bw_stat["installed"] and bw_stat["session_active"]:
            active_engine = "bitwarden_cli"
        elif shield_stat["unlocked"]:
            active_engine = "shield_vault"
        elif bw_stat["installed"]:
            active_engine = "bitwarden_cli_locked"
        else:
            active_engine = "shield_vault_fallback"

        return {
            "active_engine": active_engine,
            "bitwarden": bw_stat,
            "shield_vault": shield_stat,
            "kms_keychain": kms_stat,
            "protected_files": self.get_protected_files_inventory(),
            "transit_encryption": {
                "protocol": "AES-256-GCM + PBKDF2-HMAC-SHA256",
                "anti_replay_window_seconds": TRANSIT_WINDOW_SECONDS,
                "at_rest_protocol": "MRSV ||X_SHI3LD_X|| Fernet + Split-Key Shadow Recovery",
            },
        }

    def list_all_items(self, search: str = "") -> List[Dict[str, Any]]:
        self._try_hardware_unlock_local()
        items: List[Dict[str, Any]] = []
        if self.bw.get_status().get("session_active"):
            items.extend(self.bw.list_items(search=search))
        if self.shield.is_unlocked():
            bw_names = {x.get("name") for x in items}
            for sh_it in self.shield.list_items(search=search):
                if sh_it.get("name") not in bw_names:
                    items.append(sh_it)
        return items

    def add_item(
        self,
        name: str,
        secret: str,
        category: str = "API Key",
        username: str = "",
        notes: str = "",
        uri: str = "",
        target_engine: str = "auto",
    ) -> Dict[str, Any]:
        bw_unlocked = self.bw.get_status().get("session_active")
        shield_unlocked = self.shield.is_unlocked()

        results = {}
        if target_engine in ("auto", "both", "shield_vault") and shield_unlocked:
            results["shield_vault"] = self.shield.upsert_item(
                name=name, secret=secret, category=category, username=username, notes=notes, uri=uri
            )
        if target_engine in ("auto", "both", "bitwarden_cli") and bw_unlocked:
            results["bitwarden_cli"] = self.bw.create_item(
                name=name, secret=secret, category=category, username=username, notes=notes, uri=uri
            )
        if not results:
            raise PermissionError("No vault is currently unlocked. Unlock Bitwarden CLI or Local .vault first.")
        return results

    def reveal_item(self, item_id: str) -> Dict[str, Any]:
        if item_id.startswith("sv_"):
            return self.shield.reveal_item(item_id)
        if self.bw.get_status().get("session_active"):
            try:
                return self.bw.reveal_item(item_id)
            except Exception:
                pass
        return self.shield.reveal_item(item_id)

    def delete_item(self, item_id: str) -> bool:
        if item_id.startswith("sv_"):
            return self.shield.delete_item(item_id)
        return False

    def harvest_into_vault(self, target_engine: str = "auto") -> Dict[str, Any]:
        bw_unlocked = self.bw.get_status().get("session_active")
        shield_unlocked = self.shield.is_unlocked()
        if not (bw_unlocked or shield_unlocked):
            raise PermissionError("Unlock Bitwarden CLI or Local .vault before importing discovered secrets.")

        raw_items = self.harvester.scan(include_raw=True)
        imported_shield = 0
        imported_bw = 0
        existing_bw_names = set()
        if bw_unlocked:
            existing_bw_names = {x.get("name") for x in self.bw.list_items()}

        for it in raw_items:
            sec = it.get("secret", "")
            if not sec:
                continue
            if shield_unlocked and target_engine in ("auto", "both", "shield_vault"):
                self.shield.upsert_item(
                    name=it["name"],
                    secret=sec,
                    category=it["category"],
                    username=it.get("username", ""),
                    notes=f"{it.get('notes', '')} | Source: {it.get('source', '')}".strip(" |"),
                    uri=it.get("uri", ""),
                )
                imported_shield += 1
            if bw_unlocked and target_engine in ("auto", "both", "bitwarden_cli"):
                if it["name"] not in existing_bw_names:
                    try:
                        self.bw.create_item(
                            name=it["name"],
                            secret=sec,
                            category=it["category"],
                            username=it.get("username", ""),
                            notes=f"{it.get('notes', '')} | Source: {it.get('source', '')}".strip(" |"),
                            uri=it.get("uri", ""),
                        )
                        imported_bw += 1
                    except Exception:
                        pass

        return {
            "scanned_count": len(raw_items),
            "imported_shield_vault": imported_shield,
            "imported_bitwarden_cli": imported_bw,
            "sources_preserved": True,
        }


vault_service = UnifiedVaultService()
vault_bp = Blueprint("vault_bp", __name__)


def _require_admin() -> bool:
    return bool(session.get("admin", False) or session.get("is_admin", False))


@vault_bp.after_request
def _apply_vault_no_store_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@vault_bp.route("/admin/api/vault/handshake", methods=["POST"])
def api_vault_handshake():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    actor = session.get("username", "admin")
    hs = vault_service.transit.issue_handshake(actor_id=actor)
    return jsonify({"ok": True, "handshake": hs})


@vault_bp.route("/admin/api/vault/status", methods=["GET"])
def api_vault_status():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    return jsonify({"ok": True, **vault_service.get_overview()})


@vault_bp.route("/admin/api/vault/bw/login", methods=["POST"])
def api_vault_bw_login():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        ok, msg = vault_service.bw.login(
            email=data.get("email", ""),
            password=data.get("password", ""),
            code=data.get("code", ""),
            method=data.get("method", "0"),
            client_id=data.get("client_id", ""),
            client_secret=data.get("client_secret", ""),
        )
        return jsonify({"ok": ok, "message": msg, "status": vault_service.get_overview()}), (200 if ok else 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/bw/unlock", methods=["POST"])
def api_vault_bw_unlock():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        ok, msg = vault_service.bw.unlock(password=data.get("password", ""))
        return jsonify({"ok": ok, "message": msg, "status": vault_service.get_overview()}), (200 if ok else 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/bw/lock", methods=["POST"])
def api_vault_bw_lock():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    ok, msg = vault_service.bw.lock()
    return jsonify({"ok": ok, "message": msg, "status": vault_service.get_overview()})


@vault_bp.route("/admin/api/vault/bw/sync", methods=["POST"])
def api_vault_bw_sync():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    ok, msg = vault_service.bw.sync()
    return jsonify({"ok": ok, "message": msg, "status": vault_service.get_overview()}), (200 if ok else 400)


@vault_bp.route("/admin/api/vault/local/init", methods=["POST"])
def api_vault_local_init():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        username = data.get("username") or session.get("username") or "admin"
        password = data.get("password") or ""
        st = vault_service.shield.initialize(username=username, password=password, allow_recovery=True)
        return jsonify({"ok": True, "message": "Local X_SHI3LD_X .vault initialized and unlocked.", "shield_vault": st, "status": vault_service.get_overview()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/local/unlock", methods=["POST"])
def api_vault_local_unlock():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        username = data.get("username") or session.get("username") or "admin"
        password = data.get("password") or ""
        st = vault_service.shield.unlock(username=username, password=password)
        return jsonify({"ok": True, "message": f"Local .vault unlocked for '{username}'.", "shield_vault": st, "status": vault_service.get_overview()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/local/lock", methods=["POST"])
def api_vault_local_lock():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    st = vault_service.shield.lock()
    return jsonify({"ok": True, "message": "Local .vault locked in memory.", "shield_vault": st, "status": vault_service.get_overview()})


@vault_bp.route("/admin/api/vault/local/user", methods=["POST"])
def api_vault_local_add_user():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        st = vault_service.shield.add_or_update_user(
            target_username=data.get("target_username", ""),
            target_password=data.get("target_password", ""),
        )
        return jsonify({"ok": True, "message": "Team member access updated and recovery bridge rotated.", "shield_vault": st})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/local/recovery-challenge", methods=["POST"])
def api_vault_local_recovery_challenge():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        ch = vault_service.shield.get_recovery_challenge(verify_username=data.get("username", "admin"))
        return jsonify({"ok": True, "challenge": ch})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/local/recover", methods=["POST"])
def api_vault_local_recover():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        st = vault_service.shield.emergency_recover(
            verify_username=data.get("username", "admin"),
            recovery_token=data.get("recovery_token", ""),
            new_password=data.get("new_password", ""),
        )
        return jsonify({"ok": True, "message": "Emergency Split-Key Recovery succeeded and cipher rotated.", "shield_vault": st, "status": vault_service.get_overview()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/local/rotate-kms", methods=["POST"])
def api_vault_rotate_kms():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        new_id = vault_service.keychain.rotate_key()
        return jsonify({"ok": True, "message": f"Rotated KMS Keychain to active DEK '{new_id}'.", "kms_keychain": vault_service.keychain.get_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/local/protect-file", methods=["POST"])
def api_vault_protect_file():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        rel_target = (data.get("target") or "").strip().lstrip("/")
        allowed = {"profiles.json", "gethub_token.txt", ".env", "cache/bridge_queue.json"}
        if rel_target not in allowed:
            return jsonify({"ok": False, "error": f"Target must be one of {sorted(allowed)}"}), 400
        username = data.get("username") or session.get("username") or "admin"
        password = data.get("password") or ""
        if not password or len(password) < 4:
            return jsonify({"ok": False, "error": "Vault password (min 4 chars) required to encrypt file at rest."}), 400
        res = vault_service.shield.encrypt_external_file(vault_service.base_dir / rel_target, username=username, password=password)
        return jsonify({"ok": True, "message": f"Created encrypted at-rest container '{res['vault_file']}'.", "result": res, "protected_files": vault_service.get_protected_files_inventory()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/items", methods=["GET", "POST"])
def api_vault_items():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    if request.method == "GET":
        q = request.args.get("q", "")
        return jsonify({"ok": True, "items": vault_service.list_all_items(search=q)})
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        saved = vault_service.add_item(
            name=data.get("name", ""),
            secret=data.get("secret", ""),
            category=data.get("category", "API Key"),
            username=data.get("username", ""),
            notes=data.get("notes", ""),
            uri=data.get("uri", ""),
            target_engine=data.get("target_engine", "auto"),
        )
        return jsonify({"ok": True, "message": "Credential encrypted and stored in vault.", "saved": saved, "items": vault_service.list_all_items()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/items/<item_id>", methods=["DELETE"])
def api_vault_delete_item(item_id: str):
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        deleted = vault_service.delete_item(item_id)
        return jsonify({"ok": deleted, "items": vault_service.list_all_items()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/items/<item_id>/reveal", methods=["POST"])
def api_vault_reveal_item(item_id: str):
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        key_id = raw.get("key_id") or ""
        revealed = vault_service.reveal_item(item_id)
        if key_id:
            enc = vault_service.transit.encrypt_for_transit(key_id, revealed)
            return jsonify({"ok": True, "envelope": enc})
        return jsonify({"ok": True, "item": revealed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@vault_bp.route("/admin/api/vault/harvest/scan", methods=["GET"])
def api_vault_harvest_scan():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    report = vault_service.harvester.scan_report(include_raw=False)
    items = report["findings"]
    return jsonify({
        "ok": True,
        "count": len(items),
        "discovered": items,
        "stats": report["stats"],
        "skipped": report["skipped"],
        "errors": report["errors"],
    })


@vault_bp.route("/admin/api/vault/harvest/import", methods=["POST"])
def api_vault_harvest_import():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Administrator clearance required."}), 403
    try:
        raw = request.get_json(silent=True) or {}
        data = vault_service.transit.decrypt_from_transit(raw)
        summary = vault_service.harvest_into_vault(target_engine=data.get("target_engine", "auto"))
        return jsonify({
            "ok": True,
            "message": f"Harvested {summary['scanned_count']} secrets into vault (Local .vault: {summary['imported_shield_vault']}, Bitwarden CLI: {summary['imported_bitwarden_cli']}). Original files preserved.",
            "summary": summary,
            "items": vault_service.list_all_items(),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
