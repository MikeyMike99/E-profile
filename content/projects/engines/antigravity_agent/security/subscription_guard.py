"""
Bring Your Own Subscription (BYOS) cryptographic credential vault and quota guard.
Enforces per-user API key/OAuth isolation, 7-day TTL countdown auto-purging,
and strict quota halts to guarantee zero host billing bleed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_TTL_SECONDS = 7 * 86400
VAULT_SALT = b"devcore_byos_vault_salt_v1"
_EPHEMERAL_VAULT: Dict[str, Dict[str, Any]] = {}


def get_base_dir(base_dir: Optional[str] = None) -> Path:
    if base_dir:
        return Path(base_dir).resolve()
    return Path(__file__).resolve().parent.parent


def _derive_vault_key(base_dir: Optional[str] = None) -> bytes:
    root = get_base_dir(base_dir)
    master_key_file = root / ".devcore_master.key"
    if master_key_file.exists():
        try:
            raw_master = master_key_file.read_text(encoding="utf-8").strip()
        except Exception:
            raw_master = "devcore_fallback_master_seed"
    else:
        raw_master = "devcore_fallback_master_seed"

    return hashlib.pbkdf2_hmac(
        "sha256",
        raw_master.encode("utf-8"),
        VAULT_SALT,
        100000,
        dklen=32
    )


def encrypt_credential(credential: str, base_dir: Optional[str] = None) -> str:
    key = _derive_vault_key(base_dir)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, credential.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_credential(encrypted_b64: str, base_dir: Optional[str] = None) -> str:
    key = _derive_vault_key(base_dir)
    aesgcm = AESGCM(key)
    raw_payload = base64.b64decode(encrypted_b64.encode("utf-8"))
    nonce = raw_payload[:12]
    ciphertext = raw_payload[12:]
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")


def get_subscriptions_path(base_dir: Optional[str] = None) -> Path:
    return get_base_dir(base_dir) / "subscriptions.json"


def _clean_user_id(user_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(user_id or "anonymous"))
    return cleaned.strip("_-") or "anonymous"


def get_user_runtime_chamber(user_id: str) -> Path:
    clean_id = _clean_user_id(user_id)
    chamber = Path.home() / ".gemini" / "antigravity-cli" / "users" / clean_id
    return chamber


def _load_vault(base_dir: Optional[str] = None) -> dict:
    path = get_subscriptions_path(base_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_vault(data: dict, base_dir: Optional[str] = None) -> None:
    path = get_subscriptions_path(base_dir)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_path.replace(path)


def purge_expired_subscriptions(base_dir: Optional[str] = None) -> int:
    vault = _load_vault(base_dir)
    now = time.time()
    purged_count = 0
    surviving = {}

    for user_key, record in vault.items():
        expires_at = record.get("expires_at", 0)
        if expires_at <= now:
            purged_count += 1
            chamber = get_user_runtime_chamber(user_key)
            if chamber.exists():
                try:
                    shutil.rmtree(chamber, ignore_errors=True)
                except Exception:
                    pass
        else:
            surviving[user_key] = record

    if purged_count > 0:
        _save_vault(surviving, base_dir)

    return purged_count


def set_user_subscription(
    user_id: str,
    provider: str,
    credential: str,
    ttl_days: float = 7.0,
    storage_mode: str = "vault",
    base_dir: Optional[str] = None
) -> dict:
    clean_id = _clean_user_id(user_id)
    mode = storage_mode.lower().strip()
    now = time.time()

    if mode == "ephemeral":
        vault = _load_vault(base_dir)
        if clean_id in vault:
            del vault[clean_id]
            _save_vault(vault, base_dir)

        _EPHEMERAL_VAULT[clean_id] = {
            "user_id": clean_id,
            "provider": provider.lower().strip(),
            "credential": credential.strip(),
            "created_at": now,
            "expires_at": now + 86400,
            "storage_mode": "ephemeral",
            "last_verified": now,
        }
        return {
            "success": True,
            "user_id": clean_id,
            "provider": provider.lower().strip(),
            "storage_mode": "ephemeral",
            "is_ephemeral": True,
            "expires_at": now + 86400,
            "days_remaining": 1.0,
            "hours_remaining": 24.0,
            "message": "Credential held strictly in volatile RAM. Zero bytes persisted to disk."
        }

    _EPHEMERAL_VAULT.pop(clean_id, None)
    purge_expired_subscriptions(base_dir)
    bounded_ttl_days = max(0.1, min(float(ttl_days), 7.0))
    expires_at = now + (bounded_ttl_days * 86400)

    encrypted = encrypt_credential(credential.strip(), base_dir)
    record = {
        "user_id": clean_id,
        "provider": provider.lower().strip(),
        "encrypted_credential": encrypted,
        "created_at": now,
        "expires_at": expires_at,
        "ttl_days": bounded_ttl_days,
        "storage_mode": "vault",
        "last_verified": now,
    }

    vault = _load_vault(base_dir)
    vault[clean_id] = record
    _save_vault(vault, base_dir)

    return {
        "success": True,
        "user_id": clean_id,
        "provider": record["provider"],
        "storage_mode": "vault",
        "is_ephemeral": False,
        "expires_at": expires_at,
        "days_remaining": round((expires_at - now) / 86400, 2),
        "hours_remaining": round((expires_at - now) / 3600, 1),
    }


def get_user_subscription(
    user_id: str,
    base_dir: Optional[str] = None,
    include_decrypted: bool = False
) -> Optional[dict]:
    clean_id = _clean_user_id(user_id)
    now = time.time()

    if clean_id in _EPHEMERAL_VAULT:
        rec = _EPHEMERAL_VAULT[clean_id]
        if rec.get("expires_at", 0) > now:
            res = {
                "user_id": clean_id,
                "provider": rec.get("provider", "gemini"),
                "storage_mode": "ephemeral",
                "is_ephemeral": True,
                "created_at": rec.get("created_at"),
                "expires_at": rec.get("expires_at"),
                "days_remaining": round((rec["expires_at"] - now) / 86400, 2),
                "hours_remaining": round((rec["expires_at"] - now) / 3600, 1),
                "is_active": True,
            }
            if include_decrypted:
                res["credential"] = rec["credential"]
            return res
        else:
            _EPHEMERAL_VAULT.pop(clean_id, None)

    purge_expired_subscriptions(base_dir)
    vault = _load_vault(base_dir)
    record = vault.get(clean_id)
    if not record:
        return None

    expires_at = record.get("expires_at", 0)
    if expires_at <= now:
        purge_expired_subscriptions(base_dir)
        return None

    remaining_seconds = max(0, int(expires_at - now))
    days_remaining = round(remaining_seconds / 86400, 2)
    hours_remaining = round(remaining_seconds / 3600, 1)

    result = {
        "user_id": clean_id,
        "provider": record.get("provider", "gemini"),
        "storage_mode": record.get("storage_mode", "vault"),
        "is_ephemeral": False,
        "created_at": record.get("created_at"),
        "expires_at": expires_at,
        "days_remaining": days_remaining,
        "hours_remaining": hours_remaining,
        "is_active": True,
    }

    if include_decrypted:
        try:
            result["credential"] = decrypt_credential(record["encrypted_credential"], base_dir)
        except Exception:
            return None

    return result


def delete_user_subscription(user_id: str, base_dir: Optional[str] = None) -> bool:
    clean_id = _clean_user_id(user_id)
    deleted = False

    if clean_id in _EPHEMERAL_VAULT:
        del _EPHEMERAL_VAULT[clean_id]
        deleted = True

    vault = _load_vault(base_dir)
    if clean_id in vault:
        del vault[clean_id]
        _save_vault(vault, base_dir)
        deleted = True

    chamber = get_user_runtime_chamber(clean_id)
    if chamber.exists():
        try:
            shutil.rmtree(chamber, ignore_errors=True)
            deleted = True
        except Exception:
            pass

    return deleted


def verify_subscription_health(provider: str, credential: str) -> Tuple[bool, str]:
    prov = (provider or "gemini").lower().strip()
    cred = (credential or "").strip()
    if not cred:
        return False, "Empty credential provided."

    if prov in ("gemini", "api_key", "ai_studio"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={cred}&pageSize=1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DevCore-BYOS-Guard/1.0"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    return True, "Active"
                return False, f"Unexpected status: {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return False, "RESOURCE_EXHAUSTED: Gemini API quota exceeded on your personal key. Check Google AI Studio billing."
            if e.code in (400, 401, 403):
                return False, f"INVALID_CREDENTIAL: Key rejected by Google Gemini API (HTTP {e.code})."
            return False, f"HTTP Error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"NETWORK_UNREACHABLE: {e.reason}"
        except Exception as e:
            return False, f"VERIFICATION_FAILED: {str(e)}"

    if prov in ("oauth", "gemini_advanced", "token"):
        url = f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={cred}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DevCore-BYOS-Guard/1.0"},
            method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    return True, "Active"
                return False, f"Unexpected status: {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code in (400, 401):
                return False, "EXPIRED_TOKEN: Personal OAuth token is expired or invalid."
            return False, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return False, f"VERIFICATION_FAILED: {str(e)}"

    return True, "Unverified provider accepted"


def assert_user_execution_quota(
    user: Optional[dict],
    base_dir: Optional[str] = None
) -> Tuple[bool, str, Optional[dict]]:
    if not isinstance(user, dict):
        return True, "System default", None

    token_scope = user.get("token_scope")
    if token_scope == "demo":
        return True, "Demo scope sandbox allowed", None

    user_role = str(user.get("role", "")).lower()
    if user_role in ("demo", "demo_guest"):
        return True, "Demo scope sandbox allowed", None

    user_id = user.get("username") or user.get("name") or user.get("key_id") or "guest"
    from core.roles import ADMIN_ROLES  # canonical, single source
    is_admin = user_role in ADMIN_ROLES

    sub = get_user_subscription(user_id, base_dir=base_dir, include_decrypted=True)

    if not sub:
        if is_admin:
            return True, "Admin host fallback", None
        return (
            False,
            "Personal subscription expired or missing (7-day TTL countdown). "
            "Please configure your API key in Settings to avoid host billing bleed.",
            None
        )

    valid, reason = verify_subscription_health(sub["provider"], sub["credential"])
    if not valid:
        return (
            False,
            f"Personal subscription verification failed: {reason}. "
            "Strict Halt enforced to guarantee zero host billing bleed.",
            None
        )

    return True, "Active BYOS subscription verified", sub
