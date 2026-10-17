from types import SimpleNamespace
from uuid import uuid4

import pytest

from packages.authz.constants import LEGACY_ENTERPRISE_ROLES, normalize_roles
from packages.authz.document_policy import can_access_document
from packages.authz.qdrant_filter import build_qdrant_permission_filter
from packages.authz.rbac import UserContext, can_run_benchmark, can_upload_document
from packages.authz.tool_policy import ALL_TOOLS, check_tool_permission
from packages.graphrag.graph_permissions import check_graph_query_permission
from packages.graphrag.graph_schema import QUERY_TYPES


def context(role="enterprise", tenant_id=None):
    return UserContext(
        uuid4(), tenant_id or uuid4(), "test@example.com", "logistics", [role]
    )


@pytest.mark.parametrize("role", sorted(LEGACY_ENTERPRISE_ROLES) + ["enterprise"])
def test_all_internal_jobs_have_same_business_access(role):
    user = context(role)
    assert user.roles == ["enterprise"]
    assert can_upload_document(user)
    assert not can_run_benchmark(user)
    for query in QUERY_TYPES:
        assert check_graph_query_permission(user, query).allowed
    for tool in ALL_TOOLS - {"export_benchmark_results"}:
        result = check_tool_permission(user, tool)
        assert result.allowed and not result.approval_required
    assert not check_tool_permission(user, "export_benchmark_results").allowed


@pytest.mark.parametrize("roles", [[], ["unknown"], ["external_supplier"]])
def test_no_implicit_promotion(roles):
    assert normalize_roles(roles) == []
    user = context(roles[0] if roles else "")
    assert not user.is_member
    assert not can_upload_document(user)
    assert not check_graph_query_permission(user, "supplier_impact").allowed
    assert not check_tool_permission(user, "query_supplier_profile").allowed
    with pytest.raises(PermissionError):
        build_qdrant_permission_filter(user)


@pytest.mark.parametrize("role", ["enterprise", "admin"])
def test_tenant_boundary_precedes_any_role_or_old_metadata(role):
    user = context(role)
    document = SimpleNamespace(
        tenant_id=user.tenant_id,
        access_scope="user_whitelist",
        allowed_roles=[],
        allowed_users=[],
        department="finance",
        security_level_rank=4,
    )
    assert can_access_document(user, document).allowed
    document.tenant_id = uuid4()
    assert not can_access_document(user, document).allowed
    data = build_qdrant_permission_filter(user).model_dump(exclude_none=True)
    assert data["must"] == [
        {"key": "tenant_id", "match": {"value": str(user.tenant_id)}}
    ]
    with pytest.raises(PermissionError):
        build_qdrant_permission_filter(user, extra_filters={"tenant_id": str(uuid4())})


def test_admin_precedence_and_unknown_tools():
    assert normalize_roles(["enterprise", "admin", "external_supplier"]) == ["admin"]
    assert can_run_benchmark(context("admin"))
    assert check_tool_permission(context("admin"), "export_benchmark_results").allowed
    assert not check_tool_permission(context("admin"), "delete_database").allowed
    assert not check_graph_query_permission(context("admin"), "raw_cypher").allowed
