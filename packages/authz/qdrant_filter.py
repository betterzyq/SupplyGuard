"""Qdrant permission filter builder."""

from typing import Any

from qdrant_client.http import models as qmodels

from packages.authz.rbac import UserContext


def build_qdrant_permission_filter(
    user_context: UserContext,
    *,
    extra_filters: dict[str, Any] | None = None,
) -> qmodels.Filter:
    must: list[qmodels.Condition] = [
        qmodels.FieldCondition(
            key="tenant_id",
            match=qmodels.MatchValue(value=str(user_context.tenant_id)),
        ),
        qmodels.FieldCondition(
            key="security_level_rank",
            range=qmodels.Range(lte=user_context.max_security_rank),
        ),
    ]

    if user_context.is_admin:
        filter_obj = qmodels.Filter(must=must)
        return _apply_extra_filters(filter_obj, extra_filters)

    should: list[qmodels.Condition] = [
        qmodels.FieldCondition(key="access_scope", match=qmodels.MatchValue(value="public")),
    ]

    if user_context.department:
        should.append(
            qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="access_scope",
                        match=qmodels.MatchValue(value="department"),
                    ),
                    qmodels.FieldCondition(
                        key="department",
                        match=qmodels.MatchValue(value=user_context.department),
                    ),
                ]
            )
        )

    if user_context.roles:
        should.append(
            qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="access_scope",
                        match=qmodels.MatchValue(value="role_based"),
                    ),
                    qmodels.FieldCondition(
                        key="allowed_roles",
                        match=qmodels.MatchAny(any=list(user_context.roles)),
                    ),
                ]
            )
        )

    should.append(
        qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="access_scope",
                    match=qmodels.MatchValue(value="user_whitelist"),
                ),
                qmodels.FieldCondition(
                    key="allowed_users",
                    match=qmodels.MatchAny(any=[str(user_context.user_id)]),
                ),
            ]
        )
    )

    if user_context.is_admin or "executive" in user_context.roles:
        should.append(
            qmodels.FieldCondition(
                key="access_scope",
                match=qmodels.MatchValue(value="executive_summary"),
            )
        )

    if user_context.is_external_supplier and user_context.supplier_id:
        should.append(
            qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="access_scope",
                        match=qmodels.MatchValue(value="supplier_portal"),
                    ),
                    qmodels.FieldCondition(
                        key="supplier_id",
                        match=qmodels.MatchValue(value=str(user_context.supplier_id)),
                    ),
                ]
            )
        )

    filter_obj = qmodels.Filter(
        must=must,
        min_should=qmodels.MinShould(conditions=should, min_count=1),
    )
    return _apply_extra_filters(filter_obj, extra_filters)


def _apply_extra_filters(
    base_filter: qmodels.Filter,
    extra_filters: dict[str, Any] | None,
) -> qmodels.Filter:
    if not extra_filters:
        return base_filter

    extra_must: list[qmodels.Condition] = list(base_filter.must or [])
    for key, value in extra_filters.items():
        if value is None:
            continue
        if key == "department":
            extra_must.append(
                qmodels.FieldCondition(key="department", match=qmodels.MatchValue(value=str(value)))
            )
        elif key == "doc_type":
            extra_must.append(
                qmodels.FieldCondition(key="doc_type", match=qmodels.MatchValue(value=str(value)))
            )
        elif key == "supplier_id":
            extra_must.append(
                qmodels.FieldCondition(key="supplier_id", match=qmodels.MatchValue(value=str(value)))
            )
        else:
            extra_must.append(
                qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=str(value)))
            )

    return qmodels.Filter(
        must=extra_must,
        should=base_filter.should,
        min_should=base_filter.min_should,
        must_not=base_filter.must_not,
    )
