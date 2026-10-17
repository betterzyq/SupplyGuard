"""Authenticated synthetic simulation API, no paid inference or DB migration."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path

from apps.api.deps import get_user_context
from packages.authz.rbac import UserContext
from packages.business.simulation import (
    ENGINE_VERSION,
    build_config,
    compare_simulations,
    run_simulation,
)
from packages.business.simulation_models import ComparisonRequest, SimulationRequest
from packages.business.simulation_store import read_snapshot, save_snapshot

router = APIRouter(prefix="/simulation", tags=["simulation"])


def execute(function, *args):
    try:
        return function(*args)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/templates")
def templates(
    scenario_id: str = "port-congestion",
    preset_id: Literal["manufacturing", "hand-check"] = "manufacturing",
    at_time: datetime | None = None,
    event_id: str | None = None,
    user: UserContext = Depends(get_user_context),
):
    if not user.is_member:
        raise HTTPException(status_code=403, detail="enterprise membership required")

    def load():
        request = SimulationRequest(
            scenario_id=scenario_id,
            preset_id=preset_id,
            at_time=at_time,
            event_ids=[event_id] if event_id else None,
        )
        config = build_config(request)
        target = (
            {
                "port-congestion": "MAT-01",
                "tier2-shutdown": "MAT-03",
                "regional-flood": "MAT-04",
            }[scenario_id]
            if preset_id == "manufacturing"
            else "MAT-01"
        )
        options = [o for o in config.options if o.material_id == target and o.certified]
        return {
            "tenant_id": str(user.tenant_id),
            "source_type": "synthetic",
            "engine_version": ENGINE_VERSION,
            "config": config.model_dump(mode="json"),
            "available_events": [
                e.model_dump(mode="json")
                for e in build_config(
                    request.model_copy(update={"event_ids": None})
                ).events
            ],
            "default_option_ids": [o.id for o in options[:2]],
            "target_material_id": target,
        }

    return execute(load)


@router.post("/run")
def run(request: SimulationRequest, user: UserContext = Depends(get_user_context)):
    result = execute(run_simulation, user, request)
    execute(save_snapshot, user, result)
    return result


@router.post("/comparison")
def comparison(
    request: ComparisonRequest, user: UserContext = Depends(get_user_context)
):
    result = execute(compare_simulations, user, request)
    execute(save_snapshot, user, result["baseline"])
    for plan in result["plans"]:
        execute(save_snapshot, user, plan["run"])
    execute(save_snapshot, user, result)
    return result


@router.get("/runs/{snapshot_id}")
def snapshot(
    snapshot_id: str = Path(pattern=r"^[a-f0-9]{64}$"),
    user: UserContext = Depends(get_user_context),
):
    return execute(read_snapshot, user, snapshot_id)
