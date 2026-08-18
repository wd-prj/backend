import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Date, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.leave import LeavePolicy, AccrualPolicy


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="location")
    holiday_calendars: Mapped[List["HolidayCalendar"]] = relationship(
        "HolidayCalendar", back_populates="location", cascade="all, delete-orphan"
    )
    leave_policies: Mapped[List["LeavePolicy"]] = relationship("LeavePolicy", back_populates="location")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="department")


class HolidayCalendar(Base, TimestampMixin):
    __tablename__ = "holiday_calendars"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="holiday_calendars")
    holidays: Mapped[List["Holiday"]] = relationship(
        "Holiday", back_populates="calendar", cascade="all, delete-orphan"
    )


class Holiday(Base, TimestampMixin):
    __tablename__ = "holidays"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("holiday_calendars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    calendar: Mapped["HolidayCalendar"] = relationship("HolidayCalendar", back_populates="holidays")
