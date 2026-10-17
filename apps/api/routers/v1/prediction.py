"""P4 public-data validation; tenant membership still required."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from apps.api.deps import get_user_context, require_admin
from packages.authz.rbac import UserContext
from packages.prediction import runtime

router = APIRouter(prefix="/prediction", tags=["prediction"])


def member(user):
    if not user.is_member:
        raise HTTPException(403, "enterprise membership required")


def artifact_call(fn, *args):
    try:
        return fn(*args)
    except FileNotFoundError as exc:
        raise HTTPException(
            503, "Prediction experiment unavailable; run make phase4-train"
        ) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/report")
def report(user: UserContext = Depends(get_user_context)):
    member(user)
    return {"tenant_id": str(user.tenant_id), **artifact_call(runtime.report)}


@router.get("/cases")
def cases(user: UserContext = Depends(get_user_context)):
    member(user)
    return {
        "tenant_id": str(user.tenant_id),
        "source_type": "public_historical",
        "items": artifact_call(runtime.cases),
    }


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(default="dataco-retail-historical", max_length=64)
    case_id: str = Field(min_length=1, max_length=64)


@router.post("/predict")
def predict(payload: PredictRequest, user: UserContext = Depends(get_user_context)):
    member(user)
    return {
        "tenant_id": str(user.tenant_id),
        **artifact_call(runtime.predict, payload.case_id, payload.domain),
    }


@router.get("/artifacts/{name}")
def artifact(name: str, user: UserContext = Depends(get_user_context)):
    member(user)
    if name not in {
        "report.json",
        "precision-recall.png",
        "calibration.png",
        "split-manifest.json",
        "audit.json",
        "selection.json",
        "protocol.json",
        "order-splits.csv",
        "source-hashes.json",
    }:
        raise HTTPException(404, "Artifact not public")
    path = artifact_call(runtime.checked_file, name)
    return FileResponse(path, filename=name)


@router.get("/evaluation-contracts")
def contracts(user: UserContext = Depends(require_admin)):
    from packages.benchmarks.enterprise_validation import validate

    return {"tenant_id": str(user.tenant_id), **validate()}
