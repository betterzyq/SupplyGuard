"""Authorization constants and mappings."""

SECURITY_LEVEL_RANK: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "department": 2,
    "confidential": 3,
    "executive": 4,
}

ROLE_MAX_SECURITY_RANK: dict[str, int] = {
    "admin": 4,
    "executive": 4,
    "procurement_manager": 3,
    "finance_manager": 3,
    "quality_manager": 3,
    "logistics_manager": 2,
    "procurement_staff": 2,
    "external_supplier": 1,
}

DEFAULT_ROLES: list[tuple[str, str]] = [
    ("admin", "System administrator"),
    ("procurement_manager", "Procurement manager"),
    ("procurement_staff", "Procurement staff"),
    ("logistics_manager", "Logistics manager"),
    ("finance_manager", "Finance manager"),
    ("quality_manager", "Quality manager"),
    ("executive", "Executive"),
    ("external_supplier", "External supplier portal user"),
]


def security_level_to_rank(security_level: str) -> int:
    if security_level not in SECURITY_LEVEL_RANK:
        raise ValueError(f"Unknown security_level: {security_level}")
    return SECURITY_LEVEL_RANK[security_level]


def get_max_security_rank_for_roles(roles: list[str]) -> int:
    if not roles:
        return 0
    return max(ROLE_MAX_SECURITY_RANK.get(role, 0) for role in roles)
