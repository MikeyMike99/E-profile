import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import uuid

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

MASTER_KEY_FILE = os.path.join(DEVCORE_ROOT, ".devcore_master.key")
LEASE_FILE = os.path.join(DEVCORE_ROOT, "security", ".jit_elevation_lease.json")
EXPECTED_MASTER_HASH = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"
DEFAULT_TTL_SECONDS = 300
MAX_TTL_SECONDS = 1800
TOKEN_PREFIX = "raugus-jit-"
TOKEN_REGEX = re.compile(r"(raugus-jit-[0-9a-f]{32})")


def _log_jit_event(level: str, message: str):
    try:
        from security.central_logger import log_siem_event
        log_siem_event(
            level=level,
            message=f"[SECURITY_AUDIT] [JIT_ELEVATION] {message}",
            module_name="jit_elevation",
            logger_name="security.jit_elevation",
        )
    except Exception:
        pass


def _get_signing_key() -> bytes:
    """
    Verifies the local hardware .devcore_master.key against EXPECTED_MASTER_HASH
    and derives a 32-byte HMAC-SHA256 signing key.
    Raises PermissionError if the master key is missing or invalid.
    """
    if not os.path.exists(MASTER_KEY_FILE):
        raise PermissionError("Hardware master key (.devcore_master.key) is missing.")

    with open(MASTER_KEY_FILE, "r", encoding="utf-8") as f:
        raw_key = f.read().strip()

    actual_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(actual_hash, EXPECTED_MASTER_HASH):
        raise PermissionError("Hardware master key signature verification failed.")

    return hashlib.pbkdf2_hmac(
        "sha256",
        raw_key.encode("utf-8"),
        b"raugus_jit_super_admin_elevation_v1",
        50000,
    )


def _compute_lease_hmac(payload: dict, signing_key: bytes) -> str:
    canonical_fields = {
        "lease_id": payload.get("lease_id"),
        "token_sha256": payload.get("token_sha256"),
        "issued_at": payload.get("issued_at"),
        "expires_at": payload.get("expires_at"),
        "ttl_seconds": payload.get("ttl_seconds"),
        "scope": payload.get("scope"),
        "active_session_lift": payload.get("active_session_lift"),
        "issued_by": payload.get("issued_by"),
    }
    msg = json.dumps(canonical_fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(signing_key, msg, hashlib.sha256).hexdigest()


def extract_token_from_text(text: str) -> str:
    """Extracts a 'raugus-jit-<32hex>' token from any string or returns empty string."""
    if not text or not isinstance(text, str):
        return ""
    m = TOKEN_REGEX.search(text)
    return m.group(1) if m else ""


def mint_jit_token(
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    issued_by: str = "cli",
    active_session_lift: bool = True,
) -> dict:
    """
    Mints a new short-lived Super Admin JIT elevation token and writes the
    HMAC-signed lease to security/.jit_elevation_lease.json.
    """
    signing_key = _get_signing_key()
    ttl = max(10, min(int(ttl_seconds or DEFAULT_TTL_SECONDS), MAX_TTL_SECONDS))
    now = round(time.time(), 3)
    expires_at = round(now + ttl, 3)

    raw_token = TOKEN_PREFIX + secrets.token_hex(16)
    token_sha256 = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    lease_id = "jit-" + uuid.uuid4().hex[:10]

    lease_data = {
        "lease_id": lease_id,
        "token_sha256": token_sha256,
        "issued_at": now,
        "expires_at": expires_at,
        "ttl_seconds": ttl,
        "scope": ["core_security"],
        "active_session_lift": bool(active_session_lift),
        "issued_by": str(issued_by),
    }
    lease_data["signature"] = _compute_lease_hmac(lease_data, signing_key)

    os.makedirs(os.path.dirname(LEASE_FILE), exist_ok=True)
    with open(LEASE_FILE, "w", encoding="utf-8") as f:
        json.dump(lease_data, f, indent=2)

    _log_jit_event(
        "WARNING",
        f"Super Admin JIT Elevation Token minted (lease_id={lease_id}, ttl={ttl}s, issued_by={issued_by}).",
    )
    return {
        "success": True,
        "lease_id": lease_id,
        "token": raw_token,
        "issued_at": now,
        "expires_at": expires_at,
        "ttl_seconds": ttl,
        "remaining_seconds": ttl,
        "scope": lease_data["scope"],
        "issued_by": issued_by,
    }


def revoke_jit_token(revoked_by: str = "cli") -> dict:
    """Immediately revokes and deletes any active JIT elevation lease."""
    existed = False
    lease_id = None
    if os.path.exists(LEASE_FILE):
        existed = True
        try:
            with open(LEASE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lease_id = data.get("lease_id")
        except Exception:
            pass
        try:
            os.remove(LEASE_FILE)
        except Exception:
            pass

    if existed:
        _log_jit_event(
            "INFO",
            f"Super Admin JIT Elevation Lease revoked (lease_id={lease_id}, revoked_by={revoked_by}).",
        )
    return {
        "success": True,
        "revoked": existed,
        "lease_id": lease_id,
        "message": "JIT elevation lease revoked and core defences re-locked." if existed else "No active JIT lease found.",
    }


def verify_jit_elevation(candidate_token: str = None, consume: bool = False) -> dict:
    """
    Verifies whether a valid, non-expired Super Admin JIT Elevation Lease is active.
    - Checks hardware .devcore_master.key signature.
    - Checks HMAC-SHA256 integrity of security/.jit_elevation_lease.json.
    - Checks TTL expiration (auto-purges expired lease files).
    - If candidate_token contains a `raugus-jit-...` token, verifies its SHA-256 digest.
      Otherwise, checks whether `active_session_lift` is enabled on the lease.
    """
    if not os.path.exists(LEASE_FILE):
        return {"valid": False, "reason": "No active JIT elevation lease."}

    try:
        signing_key = _get_signing_key()
    except PermissionError as pe:
        return {"valid": False, "reason": str(pe)}

    try:
        with open(LEASE_FILE, "r", encoding="utf-8") as f:
            lease = json.load(f)
    except Exception as e:
        return {"valid": False, "reason": f"Malformed JIT lease file: {e}"}

    expected_sig = _compute_lease_hmac(lease, signing_key)
    actual_sig = str(lease.get("signature", ""))
    if not hmac.compare_digest(actual_sig, expected_sig):
        try:
            os.remove(LEASE_FILE)
        except Exception:
            pass
        _log_jit_event("ERROR", "Tampered JIT lease signature detected and purged!")
        return {"valid": False, "reason": "Invalid HMAC signature on JIT lease (purged)."}

    now = time.time()
    expires_at = float(lease.get("expires_at", 0))
    if now >= expires_at:
        lease_id = lease.get("lease_id")
        try:
            os.remove(LEASE_FILE)
        except Exception:
            pass
        _log_jit_event("INFO", f"JIT elevation lease '{lease_id}' expired automatically.")
        return {"valid": False, "reason": "JIT elevation lease has expired."}

    extracted_tok = extract_token_from_text(candidate_token) if candidate_token else ""
    if not extracted_tok:
        env_tok = extract_token_from_text(os.environ.get("RAUGUS_JIT_TOKEN", ""))
        if env_tok:
            extracted_tok = env_tok

    token_matched = False
    if extracted_tok:
        cand_hash = hashlib.sha256(extracted_tok.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(cand_hash, str(lease.get("token_sha256", ""))):
            _log_jit_event("WARNING", "Invalid JIT token presented during verification.")
            return {"valid": False, "reason": "Provided JIT token does not match the active lease."}
        token_matched = True
    elif not lease.get("active_session_lift", False):
        return {"valid": False, "reason": "Explicit JIT token string required for this lease."}

    remaining = max(0, int(round(expires_at - now)))
    lease_id = lease.get("lease_id", "unknown")

    if consume:
        revoke_jit_token(revoked_by="single_use_consume")

    return {
        "valid": True,
        "lease_id": lease_id,
        "token_matched": token_matched,
        "remaining_seconds": remaining,
        "expires_at": expires_at,
        "scope": lease.get("scope", ["core_security"]),
        "issued_by": lease.get("issued_by", "unknown"),
    }


def get_jit_status() -> dict:
    """Returns the current status of the Super Admin JIT Elevation Lease."""
    ver = verify_jit_elevation()
    if not ver.get("valid"):
        return {
            "active": False,
            "remaining_seconds": 0,
            "reason": ver.get("reason", "Locked"),
        }
    return {
        "active": True,
        "lease_id": ver.get("lease_id"),
        "remaining_seconds": ver.get("remaining_seconds"),
        "expires_at": ver.get("expires_at"),
        "scope": ver.get("scope"),
        "issued_by": ver.get("issued_by"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Raugus Human-in-the-Loop Super Admin JIT Elevation Token Manager"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--mint",
        action="store_true",
        help="Mint a short-lived Super Admin JIT token and activate the elevation window",
    )
    group.add_argument(
        "--revoke",
        action="store_true",
        help="Immediately revoke the active JIT token and re-lock all core security files",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Check whether a JIT elevation lease is currently active and view remaining TTL",
    )
    group.add_argument(
        "--verify",
        metavar="TOKEN",
        help="Verify a specific raugus-jit-<hex> token against the active lease",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=DEFAULT_TTL_SECONDS,
        help=f"Lease duration in seconds (default: {DEFAULT_TTL_SECONDS}, max: {MAX_TTL_SECONDS})",
    )
    parser.add_argument(
        "--token-only-mode",
        action="store_true",
        help="Require explicit token string in tool calls rather than session-wide window lift",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    args = parser.parse_args()

    try:
        if args.mint:
            res = mint_jit_token(
                ttl_seconds=args.ttl,
                issued_by="host_cli",
                active_session_lift=not args.token_only_mode,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print("==================================================================")
                print(" 🔓 RAUGUS SUPER ADMIN JIT ELEVATION ACTIVE (HUMAN-IN-THE-LOOP)")
                print("==================================================================")
                print(f" Token      : {res['token']}")
                print(f" Lease ID   : {res['lease_id']}")
                print(f" Duration   : {res['ttl_seconds']} seconds ({res['ttl_seconds'] // 60}m {res['ttl_seconds'] % 60}s)")
                print(f" Scope      : {', '.join(res['scope'])}")
                print("------------------------------------------------------------------")
                print(" Core security guard files (raugus_hook.py, raugus_resolver, etc.)")
                print(" are now unlocked for hot-patching until the timer expires.")
                print(" To re-lock early, run: python3 security/jit_elevation.py --revoke")
                print("==================================================================")
        elif args.revoke:
            res = revoke_jit_token(revoked_by="host_cli")
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"🔒 {res['message']}")
        elif args.status:
            res = get_jit_status()
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                if res["active"]:
                    print(
                        f"🔓 ACTIVE: Lease {res['lease_id']} ({res['remaining_seconds']}s remaining, issued by {res['issued_by']})"
                    )
                else:
                    print(f"🔒 LOCKED: {res['reason']}")
        elif args.verify:
            res = verify_jit_elevation(candidate_token=args.verify)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                if res.get("valid"):
                    print(f"✅ VALID: Lease {res['lease_id']} ({res['remaining_seconds']}s remaining)")
                else:
                    print(f"❌ INVALID: {res.get('reason')}")
                sys.exit(0 if res.get("valid") else 1)
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"❌ JIT Elevation Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
