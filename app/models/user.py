import enum
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.audit import Notification, AuditLog
    from app.models.invitation import Invitation


class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    HR_ADMIN = "HR_ADMIN"


class UserStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False, index=True
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
