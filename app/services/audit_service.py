from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.audit import AuditLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        ai_rationale: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            previous_state=previous_state,
            new_state=new_state,
            ai_rationale=ai_rationale,
            ip_address=ip_address,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_audit_trail(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditLog]:
        query = self.db.query(AuditLog)
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)

        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
