from fastapi import APIRouter, Depends
from .auth import router as auth_router
from .videos import router as videos_router
from .live import router as live_router
from .youtube import router as youtube_router
from .health import router as health_router
from .admin import router as admin_router
from .accounts import router as accounts_router
from ..core import require_admin

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(auth_router, dependencies=[Depends(require_admin)])
api_router.include_router(videos_router, dependencies=[Depends(require_admin)])
api_router.include_router(live_router, dependencies=[Depends(require_admin)])
api_router.include_router(youtube_router, dependencies=[Depends(require_admin)])
api_router.include_router(accounts_router, dependencies=[Depends(require_admin)])
api_router.include_router(health_router)
