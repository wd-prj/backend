from typing import List, Optional, Any
from pydantic import BaseModel
import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["Admin & Audit"])


class AuditLogOut(BaseModel):
    id: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    previous_state: Optional[Any] = None
    new_state: Optional[Any] = None
    ai_rationale: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime.datetime


@router.get("/audit-trail", response_model=List[AuditLogOut])
def get_audit_trail(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.HR_ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
):
    service = AuditService(db)
    logs = service.get_audit_trail(entity_type=entity_type, entity_id=entity_id, limit=limit)
    return [
        AuditLogOut(
            id=l.id,
            actor_id=l.actor_id,
            actor_email=l.actor_email,
            action=l.action,
            entity_type=l.entity_type,
            entity_id=l.entity_id,
            previous_state=l.previous_state,
            new_state=l.new_state,
            ai_rationale=l.ai_rationale,
            ip_address=l.ip_address,
            created_at=l.created_at,
        )
        for l in logs
    ]
