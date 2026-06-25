"""Audit log repository wrapper."""

from packages.authz.audit import write_audit_log

__all__ = ["write_audit_log"]
