import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User


class Invitation(Base, TimestampMixin):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    invited_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_by_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Relationships
    invited_user: Mapped["User"] = relationship("User", foreign_keys=[invited_user_id])
    invited_by: Mapped["User"] = relationship("User", foreign_keys=[invited_by_id])
