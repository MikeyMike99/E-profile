"""Host administrative recovery utility for rotating or resetting administrator PINs/tokens in profiles.json."""

import argparse
import getpass
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def compute_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def resolve_profiles_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "profiles.json",
        Path.cwd() / "profiles.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def load_profile_store(file_path: Path) -> tuple[dict, dict]:
    if not file_path.exists():
        raise FileNotFoundError(f"Profiles file not found at: {file_path}")
    raw_data = json.loads(file_path.read_text(encoding="utf-8"))
    if "data" in raw_data and isinstance(raw_data["data"], dict):
        return raw_data, raw_data["data"]
    return {"metadata": {"schema_version": 2, "last_migrated": datetime.now().isoformat()}, "data": raw_data}, raw_data


def persist_profile_store(file_path: Path, envelope: dict, profiles: dict) -> None:
    backup_path = file_path.with_suffix(".json.bak")
    shutil.copy2(file_path, backup_path)
    envelope["data"] = profiles
    envelope.setdefault("metadata", {})["last_migrated"] = datetime.now().isoformat()
    file_path.write_text(json.dumps(envelope, indent=4), encoding="utf-8")


def reset_admin_token(target_username: str | None, new_pin: str, profiles_path: Path | None = None) -> bool:
    target_path = profiles_path or resolve_profiles_path()
    envelope, profiles = load_profile_store(target_path)

    admin_hashes = [h for h, u in profiles.items() if u.get("is_admin", False)]
    if not admin_hashes:
        print("[ERROR] No administrator profiles detected in profile store.", file=sys.stderr)
        return False

    matched_hash = None
    if target_username:
        for h in admin_hashes:
            if profiles[h].get("username", "").strip().lower() == target_username.strip().lower():
                matched_hash = h
                break
        if not matched_hash:
            print(f"[ERROR] Administrator profile with username '{target_username}' was not found.", file=sys.stderr)
            return False
    else:
        matched_hash = admin_hashes[0]

    if len(new_pin) < 4:
        print("[ERROR] New PIN / token must be at least 4 characters long.", file=sys.stderr)
        return False

    new_hash = compute_token_hash(new_pin)
    if new_hash in profiles and new_hash != matched_hash:
        print("[ERROR] The specified PIN is already assigned to another profile.", file=sys.stderr)
        return False

    user_record = profiles.pop(matched_hash)
    profiles[new_hash] = user_record
    persist_profile_store(target_path, envelope, profiles)
    print(f"[SUCCESS] PIN reset for administrator '{user_record.get('username')}' ({target_path}).")
    return True


def list_profiles(profiles_path: Path | None = None) -> None:
    target_path = profiles_path or resolve_profiles_path()
    _, profiles = load_profile_store(target_path)
    print(f"\nActive Profiles ({target_path}):")
    print(f"{'USERNAME':<20} {'LABEL':<20} {'ROLE':<15} {'BYPASS':<10}")
    print("-" * 65)
    for data in profiles.values():
        role = "SYS_ADMIN" if data.get("is_admin") else ("EMPLOYER" if data.get("is_employer") else "STANDARD")
        bypass = "ENABLED" if data.get("bypass_enabled") else "DISABLED"
        print(f"{data.get('username', 'N/A'):<20} {data.get('label', 'N/A'):<20} {role:<15} {bypass:<10}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Emergency Admin Recovery & PIN Reset Tool")
    parser.add_argument("--username", "-u", help="Username of the administrator account to reset")
    parser.add_argument("--pin", "-p", help="New PIN / password to assign")
    parser.add_argument("--list", "-l", action="store_true", help="List all configured profiles")
    parser.add_argument("--file", "-f", help="Explicit path to profiles.json")
    args = parser.parse_args()

    explicit_path = Path(args.file) if args.file else None

    if args.list:
        list_profiles(explicit_path)
        return

    target_user = args.username
    pin = args.pin

    if not pin:
        if not target_user:
            target_user = input("Enter admin username to reset (leave empty for primary admin): ").strip() or None
        pin = getpass.getpass("Enter new PIN / Token (min 4 chars): ")
        confirm_pin = getpass.getpass("Confirm new PIN / Token: ")
        if pin != confirm_pin:
            print("[ERROR] Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    success = reset_admin_token(target_user, pin, explicit_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
