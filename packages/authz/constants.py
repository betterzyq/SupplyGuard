"""Two-role enterprise policy; legacy department labels are metadata only."""

AUTHORIZATION_POLICY_VERSION = "enterprise-v2"
SECURITY_LEVEL_RANK = {
    "public": 0,
    "internal": 1,
    "department": 2,
    "confidential": 3,
    "executive": 4,
}
LEGACY_ENTERPRISE_ROLES = frozenset(
    {
        "executive",
        "procurement_manager",
        "procurement_staff",
        "logistics_manager",
        "finance_manager",
        "quality_manager",
    }
)
ROLE_MAX_SECURITY_RANK = {"admin": 4, "enterprise": 4}
DEFAULT_ROLES = [("admin", "管理员（开发人员）"), ("enterprise", "企业用户")]


def normalize_roles(roles: list[str]) -> list[str]:
    """Do not elevate unknown or retired supplier-portal accounts."""
    if "admin" in roles:
        return ["admin"]
    if "enterprise" in roles or LEGACY_ENTERPRISE_ROLES.intersection(roles):
        return ["enterprise"]
    return []


def security_level_to_rank(security_level: str) -> int:
    if security_level not in SECURITY_LEVEL_RANK:
        raise ValueError(f"Unknown security_level: {security_level}")
    return SECURITY_LEVEL_RANK[security_level]


def get_max_security_rank_for_roles(roles: list[str]) -> int:
    return 4 if normalize_roles(roles) else 0
