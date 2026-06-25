"""Re-export base classes for models."""

from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

__all__ = ["Base", "TimestampMixin", "UUIDPrimaryKeyMixin"]
