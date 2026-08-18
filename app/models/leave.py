import enum
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, Boolean, ForeignKey, Text, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.organization import Location
    from app.models.employee import Employee
    from app.models.request import LeaveRequest


class AccrualFrequency(str, enum.Enum):
    YEARLY = "YEARLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


class LeaveType(Base, TimestampMixin):
    __tablename__ = "leave_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)  # ANNUAL, SICK, CASUAL, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    color_code: Mapped[str] = mapped_column(String(20), default="#4f46e5", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    policies: Mapped[List["LeavePolicy"]] = relationship("LeavePolicy", back_populates="leave_type")
    accruals: Mapped[List["EmployeeAccrual"]] = relationship("EmployeeAccrual", back_populates="leave_type")
    leave_requests: Mapped[List["LeaveRequest"]] = relationship("LeaveRequest", back_populates="leave_type")


class LeavePolicy(Base, TimestampMixin):
    __tablename__ = "leave_policies"
    __table_args__ = (
        UniqueConstraint("leave_type_id", "location_id", "department_id", name="uq_leave_policy_loc_dept"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    leave_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    # Policy Rules
    max_consecutive_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=10)
    requires_document_after_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=2)
    advance_notice_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    carry_forward_limit: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    allow_negative_balance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    leave_type: Mapped["LeaveType"] = relationship("LeaveType", back_populates="policies")
    location: Mapped["Location"] = relationship("Location", back_populates="leave_policies")


class AccrualPolicy(Base, TimestampMixin):
    __tablename__ = "accrual_policies"
    __table_args__ = (
        UniqueConstraint("leave_type_id", "location_id", name="uq_accrual_policy_type_loc"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    leave_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frequency: Mapped[AccrualFrequency] = mapped_column(
        SQLEnum(AccrualFrequency), default=AccrualFrequency.YEARLY, nullable=False
    )
    annual_entitlement: Mapped[float] = mapped_column(Float, default=18.0, nullable=False)
    max_carry_forward: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)


class EmployeeAccrual(Base, TimestampMixin):
    __tablename__ = "employee_accruals"
    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_emp_accrual_year"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    annual_entitlement: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carried_over: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    manual_adjustments: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="accruals")
    leave_type: Mapped["LeaveType"] = relationship("LeaveType", back_populates="accruals")
