from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.employee import router as employee_router
from app.api.v1.leave import router as leave_router
from app.api.v1.manager import router as manager_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.provisioning import router as provisioning_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(employee_router)
api_router.include_router(leave_router)
api_router.include_router(manager_router)
api_router.include_router(intelligence_router)
api_router.include_router(notifications_router)
api_router.include_router(admin_router)
api_router.include_router(ai_router)
api_router.include_router(provisioning_router)
