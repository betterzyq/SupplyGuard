"""Supplier model."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Supplier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_suppliers_tenant_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="supplier")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="supplier")
    portal_users: Mapped[list["User"]] = relationship(back_populates="supplier")
