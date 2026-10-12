from fastapi.routing import APIRouter

from .routers import ai_usage, meta, organizations, overview, users

router = APIRouter()

router.include_router(meta.router)
router.include_router(overview.router)
router.include_router(users.router)
router.include_router(organizations.router)
router.include_router(ai_usage.router)
