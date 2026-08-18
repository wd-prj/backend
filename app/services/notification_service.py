from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.audit import Notification


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str = "INFO",
        link_url: Optional[str] = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            link_url=link_url,
            is_read=False,
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def get_user_notifications(self, user_id: str, limit: int = 20) -> List[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        notif = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notif:
            notif.is_read = True
            self.db.commit()
            return True
        return False

    def mark_all_as_read(self, user_id: str) -> int:
        count = (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .update({"is_read": True})
        )
        self.db.commit()
        return count
