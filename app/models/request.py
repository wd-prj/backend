import datetime
import enum
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Date, Float, Integer, ForeignKey, Text, Enum as SQLEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.leave import LeaveType


class LeaveRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ApprovalStepStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class ApprovalRole(str, enum.Enum):
    MANAGER = "MANAGER"
    DEPT_HEAD = "DEPT_HEAD"
    HR_ADMIN = "HR_ADMIN"


class LeaveRequest(Base, TimestampMixin):
    __tablename__ = "leave_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    
    # Exact breakdown computed deterministically
    calendar_days: Mapped[int] = mapped_column(Integer, nullable=False)
    weekend_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    holiday_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    working_days: Mapped[float] = mapped_column(Float, nullable=False)
    
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveRequestStatus] = mapped_column(
        SQLEnum(LeaveRequestStatus), default=LeaveRequestStatus.PENDING, nullable=False, index=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    employee: Mapped["Employee"] = relationship(
        "Employee", foreign_keys=[employee_id], back_populates="leave_requests"
    )
    leave_type: Mapped["LeaveType"] = relationship("LeaveType", back_populates="leave_requests")
    approval_steps: Mapped[List["ApprovalStep"]] = relationship(
        "ApprovalStep", back_populates="leave_request", cascade="all, delete-orphan", order_by="ApprovalStep.step_order"
    )


class ApprovalWorkflow(Base, TimestampMixin):
    """
    Configurable multi-level approval routing rules.
    e.g.
    1-2 days -> Step 1: MANAGER
    3-5 days -> Step 1: MANAGER, Step 2: DEPT_HEAD
    >5 days  -> Step 1: MANAGER, Step 2: DEPT_HEAD, Step 3: HR_ADMIN
    """
    __tablename__ = "approval_workflows"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_working_days: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    max_working_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    step_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    required_role: Mapped[ApprovalRole] = mapped_column(
        SQLEnum(ApprovalRole), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ApprovalStep(Base, TimestampMixin):
    __tablename__ = "approval_steps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    leave_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    required_role: Mapped[ApprovalRole] = mapped_column(
        SQLEnum(ApprovalRole), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[ApprovalStepStatus] = mapped_column(
        SQLEnum(ApprovalStepStatus), default=ApprovalStepStatus.PENDING, nullable=False, index=True
    )
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actioned_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    leave_request: Mapped["LeaveRequest"] = relationship("LeaveRequest", back_populates="approval_steps")
    approver: Mapped["Employee"] = relationship(
        "Employee", foreign_keys=[approver_id], back_populates="assigned_approval_steps"
    )
