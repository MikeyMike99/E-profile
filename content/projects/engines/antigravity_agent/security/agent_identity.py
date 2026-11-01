"""
Agent identity credentials.

Every agent run (e.g. one `claude -p` brain turn) is issued its own signed,
short-lived credential, bound to the authenticated human principal who started
it. The Raugus Resolver MCP reads it from its *process environment*
(DEVCORE_AGENT_CREDENTIAL), never from a tool argument, so the agent cannot
choose, see or forge its own clearance: it acts with exactly the delegating
user's tier and grants, never more.

Format:  rac1.<b64url(json payload)>.<b64url(HMAC-SHA256)>
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import uuid

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

ENV_VAR = "DEVCORE_AGENT_CREDENTIAL"
PREFIX = "rac1"
DEFAULT_TTL_SECONDS = 900
MAX_TTL_SECONDS = 4 * 3600
_FALLBACK_SECRET_FILE = os.path.join(DEVCORE_ROOT, "security", ".agent_identity.key")

_BASE_SECRET = None


def _base_secret() -> bytes:
    """Server-held root secret. Derived from the hardware master key when it is
    present and valid; otherwise a random per-install secret (mode 0600)."""
    global _BASE_SECRET
    if _BASE_SECRET is not None:
        return _BASE_SECRET
    try:
        from security.jit_elevation import MASTER_KEY_FILE, EXPECTED_MASTER_HASH
        with open(MASTER_KEY_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if hmac.compare_digest(hashlib.sha256(raw.encode()).hexdigest(), EXPECTED_MASTER_HASH):
            _BASE_SECRET = hashlib.pbkdf2_hmac("sha256", raw.encode(), b"raugus_identity_base_v1", 50000)
            return _BASE_SECRET
    except Exception:
        pass
    try:
        with open(_FALLBACK_SECRET_FILE, "rb") as f:
            data = f.read()
        if len(data) >= 32:
            _BASE_SECRET = data[:64]
            return _BASE_SECRET
    except Exception:
        pass
    data = secrets.token_bytes(64)
    fd = os.open(_FALLBACK_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    _BASE_SECRET = data
    return _BASE_SECRET


def derive_key(purpose: str) -> bytes:
    """Purpose-separated subkey (agent credentials, access registry, ...)."""
    return hmac.new(_base_secret(), purpose.encode(), hashlib.sha256).digest()


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mint_agent_credential(user: dict, conversation_id: str = None, agent_kind: str = "agent",
                          ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """Issue a credential for an agent acting on behalf of `user` (an
    authenticated session dict). Only Siraugga's server process calls this."""
    from core.roles import tier_for_role
    if not user or not user.get("role"):
        raise PermissionError("An agent credential needs an authenticated principal.")
    now = time.time()
    ttl = max(30, min(int(ttl_seconds or DEFAULT_TTL_SECONDS), MAX_TTL_SECONDS))
    payload = {
        "v": 1,
        "agent_id": f"{agent_kind}-{uuid.uuid4().hex[:16]}",
        "agent_kind": agent_kind,
        "principal": user.get("key_id") or user.get("username") or "unknown",
        "username": user.get("username") or user.get("name") or "unknown",
        "role": str(user.get("role")),
        "tier": tier_for_role(user.get("role")),
        "conversation_id": conversation_id,
        "iat": round(now, 3),
        "exp": round(now + ttl, 3),
    }
    body = _b64e(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(derive_key("agent_credential_v1"), f"{PREFIX}.{body}".encode(), hashlib.sha256).digest())
    return f"{PREFIX}.{body}.{sig}"


def verify_agent_credential(token: str) -> dict:
    """Return the payload of a valid, unexpired credential; raise PermissionError otherwise."""
    if not token or not isinstance(token, str):
        raise PermissionError("No agent credential presented.")
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise PermissionError("Malformed agent credential.")
    expected = hmac.new(derive_key("agent_credential_v1"), f"{PREFIX}.{parts[1]}".encode(), hashlib.sha256).digest()
    try:
        actual = _b64d(parts[2])
    except Exception:
        raise PermissionError("Malformed agent credential signature.")
    if not hmac.compare_digest(expected, actual):
        raise PermissionError("Agent credential signature is invalid.")
    payload = json.loads(_b64d(parts[1]))
    if float(payload.get("exp", 0)) < time.time():
        raise PermissionError("Agent credential has expired.")
    from core.roles import tier_for_role
    # The tier is always recomputed from the role, never trusted from the payload alone.
    payload["tier"] = min(int(payload.get("tier", 1)), tier_for_role(payload.get("role")))
    return payload


def credential_from_env() -> dict:
    """The verified identity of the agent this process serves, or None."""
    tok = os.environ.get(ENV_VAR, "")
    if not tok:
        return None
    try:
        return verify_agent_credential(tok)
    except PermissionError:
        return None
