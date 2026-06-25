"""Tenant model."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    roles: Mapped[list["Role"]] = relationship(back_populates="tenant")
