"""Tenant boundary is mandatory; obsolete document role metadata is ignored."""

from typing import Any

from qdrant_client.http import models as qmodels

from packages.authz.rbac import UserContext


def build_qdrant_permission_filter(
    user_context: UserContext,
    *,
    extra_filters: dict[str, Any] | None = None,
) -> qmodels.Filter:
    if not user_context.is_member:
        raise PermissionError("enterprise membership required")
    must = [
        qmodels.FieldCondition(
            key="tenant_id",
            match=qmodels.MatchValue(value=str(user_context.tenant_id)),
        )
    ]
    for key, value in (extra_filters or {}).items():
        if value is None:
            continue
        if key == "tenant_id":
            if str(value) != str(user_context.tenant_id):
                raise PermissionError("tenant filter cannot be overridden")
            continue
        must.append(
            qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=str(value)))
        )
    return qmodels.Filter(must=must)
