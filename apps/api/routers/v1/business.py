"""Business-facing APIs use local fixtures, authentication and no AI calls."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.deps import get_user_context
from packages.authz.rbac import UserContext
from packages.business.overview import business_overview, scenario_catalog
from packages.business.network import network_snapshot

router = APIRouter(prefix="/business", tags=["business"])


@router.get("/scenarios")
async def scenarios(user: UserContext = Depends(get_user_context)) -> dict:
    if not user.is_member:
        raise HTTPException(status_code=403, detail="enterprise membership required")
    return {"items": scenario_catalog(), "source_type": "synthetic"}


@router.get("/overview")
async def overview(
    scenario_id: str = Query(default="port-congestion", min_length=1, max_length=64),
    user: UserContext = Depends(get_user_context),
) -> dict:
    try:
        return business_overview(user, scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown scenario") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def load_network(user, scenario_id, at_time, supplier_id, mode, q, risk_only):
    try:
        return network_snapshot(
            user, scenario_id, at_time, supplier_id, mode, q, risk_only
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/network")
async def network(
    scenario_id: str = Query(default="port-congestion", max_length=64),
    at_time: datetime | None = None,
    supplier_id: str | None = None,
    mode: Literal["ocean", "road", "rail", "air"] | None = None,
    q: str = Query(default="", max_length=100),
    risk_only: bool = False,
    user: UserContext = Depends(get_user_context),
) -> dict:
    return load_network(user, scenario_id, at_time, supplier_id, mode, q, risk_only)


@router.get("/shipments")
async def shipments(
    scenario_id: str = "port-congestion",
    at_time: datetime | None = None,
    supplier_id: str | None = None,
    mode: Literal["ocean", "road", "rail", "air"] | None = None,
    q: str = Query(default="", max_length=100),
    risk_only: bool = False,
    user: UserContext = Depends(get_user_context),
) -> dict:
    data = load_network(user, scenario_id, at_time, supplier_id, mode, q, risk_only)
    return {
        "tenant_id": data["tenant_id"],
        "as_of": data["as_of"],
        "source_type": "synthetic",
        "items": data["shipments"],
    }


@router.get("/shipments/{shipment_id}")
async def shipment_detail(
    shipment_id: str,
    scenario_id: str = "port-congestion",
    at_time: datetime | None = None,
    user: UserContext = Depends(get_user_context),
) -> dict:
    data = load_network(user, scenario_id, at_time, None, None, "", False)
    shipment = next((s for s in data["shipments"] if s["id"] == shipment_id), None)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Unknown shipment")
    return {
        "tenant_id": data["tenant_id"],
        "as_of": data["as_of"],
        "source_type": "synthetic",
        "shipment": shipment,
        "orders": [o for o in data["orders"] if o["id"] in shipment["order_ids"]],
    }
