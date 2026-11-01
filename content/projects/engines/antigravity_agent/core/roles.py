"""Canonical super-admin / root role names and matcher.

Single source of truth so the admin-role list isn't copied (and drifting, with
inconsistent casing) across modules. Pure leaf module — imports nothing from the
project — so any module can import it without a circular dependency.
"""

ADMIN_ROLES = frozenset({"admin", "super_admin", "super admin", "root", "tier5_sysadmin"})

# Raugus clearance tier per role (5 = super-admin). Unknown roles get tier 1.
ROLE_TIERS = {
    "gamedev": 3,
    "dev": 3,
    "developer": 3,
    "modder": 2,
    "mod": 2,
    "guest": 1,
}

GRANTABLE_ROLES = ("gamedev", "modder", "guest")


def is_admin_role(role) -> bool:
    """Case-insensitive check of a single role name against the admin/root set."""
    return str(role or "").strip().lower() in ADMIN_ROLES


def tier_for_role(role) -> int:
    r = str(role or "").strip().lower()
    if r in ADMIN_ROLES:
        return 5
    return ROLE_TIERS.get(r, 1)
