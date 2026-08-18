from typing import Optional, List
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    designation: Optional[str] = "Software Engineer"
    department_id: Optional[str] = None
    location_id: Optional[str] = None
    role: Optional[UserRole] = UserRole.EMPLOYEE


class OrgOption(BaseModel):
    id: str
    name: str


class OrgMetaResponse(BaseModel):
    departments: List[OrgOption]
    locations: List[OrgOption]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: UserRole
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    designation: Optional[str] = None


class PersonaOption(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    designation: str
    department_name: str
    location_name: str
    avatar_url: Optional[str] = None
    description: str
