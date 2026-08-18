import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.user import UserRole


class LocationOut(BaseModel):
    id: str
    name: str
    country: str
    timezone: str
    description: Optional[str] = None


class DepartmentOut(BaseModel):
    id: str
    name: str
    code: str
    description: Optional[str] = None


class HolidayOut(BaseModel):
    id: str
    name: str
    date: datetime.date
    is_mandatory: bool
    description: Optional[str] = None


class EmployeeProfileOut(BaseModel):
    id: str
    user_id: str
    employee_code: str
    first_name: str
    last_name: str
    full_name: str
    employee_name: Optional[str] = None
    email: str
    role: UserRole
    designation: str
    hire_date: datetime.date
    is_active: bool
    avatar_url: Optional[str] = None
    department: Optional[DepartmentOut] = None
    department_name: Optional[str] = None
    department_id: Optional[str] = None
    location: Optional[LocationOut] = None
    location_name: Optional[str] = None
    location_id: Optional[str] = None
    team_name: Optional[str] = None
    team_id: Optional[str] = None
    manager_name: Optional[str] = None
    manager_id: Optional[str] = None
