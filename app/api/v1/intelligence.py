from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.services.intelligence_service import IntelligenceService
from app.schemas.intelligence import WorkforceIntelligenceOverview

router = APIRouter(prefix="/intelligence", tags=["Workforce Intelligence"])


@router.get("/overview", response_model=WorkforceIntelligenceOverview)
def get_workforce_intelligence(
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    service = IntelligenceService(db)
    return service.get_overview()
