from typing import List, Optional
from pydantic import BaseModel
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    type: str
    is_read: bool
    link_url: Optional[str] = None
    created_at: datetime.datetime


@router.get("", response_model=List[NotificationOut])
@router.get("/", response_model=List[NotificationOut])
def get_my_notifications(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NotificationService(db)
    notifs = service.get_user_notifications(current_user.id, limit)
    return [
        NotificationOut(
            id=n.id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            link_url=n.link_url,
            created_at=n.created_at,
        )
        for n in notifs
    ]


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NotificationService(db)
    success = service.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Marked as read"}


@router.post("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NotificationService(db)
    count = service.mark_all_as_read(current_user.id)
    return {"marked_count": count}
