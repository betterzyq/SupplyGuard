#!/usr/bin/env python3
"""Seed MVP-2 demo data."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select  # noqa: E402

from packages.authz.constants import DEFAULT_ROLES, security_level_to_rank  # noqa: E402
from packages.common.db.models import (  # noqa: E402
    AgentNodeSpan,
    AgentRun,
    AuditLog,
    BenchmarkResult,
    BenchmarkRun,
    Document,
    DocumentChunk,
    GraphRetrievalLog,
    Memory,
    MemoryEventLog,
    Order,
    RetrievalLog,
    RiskEvent,
    Role,
    Supplier,
    Tenant,
    ToolCallLog,
    TraceRequest,
    User,
    UserRole,
)
from packages.common.db.session import get_session_factory  # noqa: E402
from packages.common.security.password import hash_password  # noqa: E402

TENANT_NAME = "Demo Manufacturing Co."
TENANT_CODE = "demo-mfg"

USERS = [
    ("admin@example.com", "平台管理员", "admin", "admin", None),
    ("enterprise@example.com", "企业用户", "enterprise", "enterprise", None),
]

SUPPLIERS = [
    ("SUP-001", "Alpha Components Ltd.", "CN", 1, Decimal("42.50")),
    ("SUP-002", "Beta Materials Inc.", "US", 1, Decimal("35.00")),
    ("SUP-003", "Gamma Logistics Parts", "DE", 2, Decimal("58.20")),
    ("SUP-004", "Delta Precision Co.", "JP", 2, Decimal("61.75")),
    ("SUP-005", "Epsilon Industrial", "VN", 3, Decimal("72.10")),
]


def _doc(
    slug: str,
    title: str,
    doc_type: str,
    security_level: str,
    access_scope: str,
    department: str,
    allowed_roles: list[str] | None = None,
    allowed_users: list | None = None,
    supplier_code: str | None = None,
) -> dict:
    return {
        "slug": slug,
        "title": title,
        "doc_type": doc_type,
        "security_level": security_level,
        "security_level_rank": security_level_to_rank(security_level),
        "access_scope": access_scope,
        "department": department,
        "allowed_roles": allowed_roles or [],
        "allowed_users": allowed_users or [],
        "supplier_code": supplier_code,
    }


DOCUMENTS = [
    _doc(
        "public-policy", "Public Supply Policy", "policy", "public", "public", "admin"
    ),
    _doc(
        "internal-procurement-guide",
        "Internal Procurement Guide",
        "policy",
        "internal",
        "role_based",
        "procurement",
        allowed_roles=["procurement_manager", "procurement_staff"],
    ),
    _doc(
        "department-logistics-report",
        "Logistics Delay Analysis Report",
        "risk_news",
        "department",
        "department",
        "logistics",
    ),
    _doc(
        "confidential-supplier-contract",
        "Confidential Supplier Framework Contract",
        "contract",
        "confidential",
        "role_based",
        "procurement",
        allowed_roles=["procurement_manager", "finance_manager", "admin"],
    ),
    _doc(
        "finance-pricing-terms",
        "Finance Pricing Terms",
        "financial",
        "confidential",
        "role_based",
        "finance",
        allowed_roles=["finance_manager", "admin"],
    ),
    _doc(
        "quality-report",
        "Supplier Quality Inspection Report",
        "quality_report",
        "internal",
        "role_based",
        "quality",
        allowed_roles=["quality_manager", "procurement_manager"],
    ),
    _doc(
        "executive-summary",
        "Executive Risk Summary",
        "policy",
        "executive",
        "executive_summary",
        "executive",
    ),
    _doc(
        "supplier-portal-sup001",
        "Supplier Portal Delivery Notice",
        "policy",
        "internal",
        "supplier_portal",
        "external",
        supplier_code="SUP-001",
    ),
    _doc(
        "supplier-portal-sup002",
        "Other Supplier Portal Notice",
        "policy",
        "internal",
        "supplier_portal",
        "external",
        supplier_code="SUP-002",
    ),
    _doc(
        "department-only-trap",
        "Finance Terms With Logistics Department Label",
        "financial",
        "internal",
        "role_based",
        "logistics",
        allowed_roles=["finance_manager"],
    ),
]


async def seed() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.code == TENANT_CODE))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=TENANT_NAME, code=TENANT_CODE, config={"env": "demo"})
            session.add(tenant)
            await session.flush()
        else:
            # Delete in FK-safe order (MVP-3 logs reference users).
            await session.execute(delete(BenchmarkResult))
            await session.execute(delete(BenchmarkRun))
            await session.execute(delete(ToolCallLog))
            await session.execute(delete(MemoryEventLog))
            await session.execute(delete(AgentNodeSpan))
            await session.execute(delete(TraceRequest))
            await session.execute(delete(GraphRetrievalLog))
            await session.execute(delete(Memory))
            await session.execute(delete(RetrievalLog))
            await session.execute(delete(AgentRun))
            await session.execute(delete(AuditLog))
            await session.execute(delete(DocumentChunk))
            await session.execute(delete(Document))
            await session.execute(delete(RiskEvent))
            await session.execute(delete(Order))
            await session.execute(delete(UserRole))
            await session.execute(delete(User))
            await session.execute(delete(Role))
            await session.execute(delete(Supplier))

        role_map: dict[str, Role] = {}
        for role_name, description in DEFAULT_ROLES:
            role = Role(tenant_id=tenant.id, name=role_name, description=description)
            session.add(role)
            role_map[role_name] = role
        await session.flush()

        supplier_map: dict[str, Supplier] = {}
        for code, name, country, tier, risk_score in SUPPLIERS:
            supplier = Supplier(
                tenant_id=tenant.id,
                code=code,
                name=name,
                country=country,
                tier=tier,
                risk_score=risk_score,
                status="active",
                metadata_={"seed": True},
            )
            session.add(supplier)
            supplier_map[code] = supplier
        await session.flush()

        user_map: dict[str, User] = {}
        password_hash = hash_password("password123")
        for email, full_name, department, role_name, supplier_code in USERS:
            user = User(
                tenant_id=tenant.id,
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                department=department,
                supplier_id=supplier_map[supplier_code].id if supplier_code else None,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=role_map[role_name].id))
            user_map[email] = user
        await session.flush()

        admin_user = user_map["admin@example.com"]
        doc_models: dict[str, Document] = {}
        for index, spec in enumerate(DOCUMENTS, start=1):
            supplier_id = (
                supplier_map[spec["supplier_code"]].id
                if spec.get("supplier_code")
                else None
            )
            document = Document(
                tenant_id=tenant.id,
                title=spec["title"],
                doc_type=spec["doc_type"],
                source_uri=f"data/raw/{spec['slug']}.txt",
                file_name=f"{spec['slug']}.txt",
                mime_type="text/plain",
                security_level=spec["security_level"],
                security_level_rank=spec["security_level_rank"],
                access_scope=spec["access_scope"],
                department=spec["department"],
                allowed_roles=spec["allowed_roles"],
                allowed_users=spec["allowed_users"],
                supplier_id=supplier_id,
                status="indexed",
                metadata_={"slug": spec["slug"], "seed": True},
                uploaded_by=admin_user.id,
            )
            session.add(document)
            doc_models[spec["slug"]] = document
        await session.flush()

        chunk_count = 0
        for slug, document in doc_models.items():
            for chunk_index in range(2):
                chunk_count += 1
                session.add(
                    DocumentChunk(
                        tenant_id=tenant.id,
                        document_id=document.id,
                        chunk_index=chunk_index,
                        content=f"{document.title} chunk {chunk_index}",
                        token_count=128,
                        embedding_id=None,
                        security_level=document.security_level,
                        security_level_rank=document.security_level_rank,
                        access_scope=document.access_scope,
                        department=document.department,
                        allowed_roles=document.allowed_roles,
                        allowed_users=document.allowed_users,
                        supplier_id=document.supplier_id,
                        metadata_={"slug": slug, "chunk_index": chunk_index},
                    )
                )

        for index in range(1, 11):
            supplier = list(supplier_map.values())[(index - 1) % len(supplier_map)]
            session.add(
                Order(
                    tenant_id=tenant.id,
                    order_no=f"PO-2024-{index:04d}",
                    supplier_id=supplier.id,
                    product_name=f"Product-{index}",
                    customer_name=f"Customer-{index}",
                    quantity=100 + index,
                    status="open" if index % 2 else "delayed",
                    expected_delivery_date=(
                        datetime.now(UTC) + timedelta(days=index)
                    ).date(),
                )
            )

        severities = ["low", "medium", "high", "critical"]
        for index in range(1, 11):
            supplier = list(supplier_map.values())[(index - 1) % len(supplier_map)]
            session.add(
                RiskEvent(
                    tenant_id=tenant.id,
                    supplier_id=supplier.id,
                    event_type=["delivery", "quality", "financial", "compliance"][
                        index % 4
                    ],
                    severity=severities[index % len(severities)],
                    title=f"Risk Event {index}",
                    description=f"Auto seeded risk event {index}",
                    source="seed",
                    detected_at=datetime.now(UTC) - timedelta(days=index),
                    metadata_={"seed": True},
                )
            )

        await session.commit()
        print(
            f"Seed complete: tenant={tenant.code}, documents={len(doc_models)}, chunks={chunk_count}"
        )


if __name__ == "__main__":
    asyncio.run(seed())
