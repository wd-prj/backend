import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Date, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Location, Department
    from app.models.leave import EmployeeAccrual
    from app.models.request import LeaveRequest, ApprovalStep


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    manager_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )

    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    hire_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="employee")
    department: Mapped["Department"] = relationship("Department", back_populates="employees")
    location: Mapped["Location"] = relationship("Location", back_populates="employees")
    
    # Manager / Direct Reports hierarchy
    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee", remote_side=[id], back_populates="direct_reports"
    )
    direct_reports: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="manager"
    )

    accruals: Mapped[List["EmployeeAccrual"]] = relationship(
        "EmployeeAccrual", back_populates="employee", cascade="all, delete-orphan"
    )
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(
        "LeaveRequest", foreign_keys="LeaveRequest.employee_id", back_populates="employee", cascade="all, delete-orphan"
    )
    assigned_approval_steps: Mapped[List["ApprovalStep"]] = relationship(
        "ApprovalStep", foreign_keys="ApprovalStep.approver_id", back_populates="approver"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
