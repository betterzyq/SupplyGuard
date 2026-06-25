"""API v1 router aggregation."""

from fastapi import APIRouter

from apps.api.routers.v1.admin import router as admin_router
from apps.api.routers.v1.auth import router as auth_router
from apps.api.routers.v1.benchmarks import router as benchmarks_router
from apps.api.routers.v1.chat import router as chat_router
from apps.api.routers.v1.dashboard import router as dashboard_router
from apps.api.routers.v1.documents import router as documents_router
from apps.api.routers.v1.graphrag import router as graphrag_router
from apps.api.routers.v1.health import router as health_router
from apps.api.routers.v1.memory import router as memory_router
from apps.api.routers.v1.rag import router as rag_router
from apps.api.routers.v1.traces import router as traces_router
from apps.api.routers.v1.supply_chain import router as supply_chain_router
from apps.api.routers.v1.tools import router as tools_router
from apps.api.routers.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(admin_router)
v1_router.include_router(benchmarks_router)
v1_router.include_router(traces_router)
v1_router.include_router(tools_router)
v1_router.include_router(documents_router)
v1_router.include_router(rag_router)
v1_router.include_router(graphrag_router)
v1_router.include_router(memory_router)
v1_router.include_router(chat_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(supply_chain_router)
api_router.include_router(v1_router)
