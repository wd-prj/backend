import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole, UserStatus


class InviteManagerRequest(BaseModel):
    full_name: str
    email: EmailStr
    department_id: str
    team_name: str
    location_id: str
    designation: str = "Engineering Manager"


class InviteEmployeeRequest(BaseModel):
    full_name: str
    email: EmailStr
    department_id: str
    team_id: str
    location_id: str
    designation: str = "Software Engineer"
    primary_manager_id: Optional[str] = None


class ResendInviteRequest(BaseModel):
    user_id: str


class InvitationDetailsResponse(BaseModel):
    invitation_id: str
    email: str
    full_name: str
    role: UserRole
    department_name: str
    team_name: str
    manager_name: Optional[str] = None
    location_name: str
    designation: str
    expires_at: datetime.datetime


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str


class TeamMemberInfo(BaseModel):
    id: str
    user_id: str
    employee_code: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    role: UserRole
    status: UserStatus
    department_id: str
    department_name: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    primary_manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    location_id: str
    location_name: str
    designation: str
    hire_date: datetime.date
    created_at: datetime.datetime


class TeamInfo(BaseModel):
    id: str
    name: str
    code: str
    department_id: str
    department_name: str
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    member_count: int = 0
