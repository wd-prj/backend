from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.employee import Employee
from app.schemas.auth import LoginRequest, TokenResponse, PersonaOption

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .options(
            joinedload(User.employee).joinedload(Employee.department),
            joinedload(User.employee).joinedload(Employee.location),
        )
        .filter(User.email == login_data.email.lower().strip())
        .first()
    )

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    emp_id = user.employee.id if user.employee else None
    token = create_access_token(subject=user.id, role=user.role.value, employee_id=emp_id)

    # Set HTTP-only secure cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )

    emp = user.employee
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        employee_id=emp.id if emp else None,
        employee_name=emp.full_name if emp else None,
        location_id=emp.location_id if emp else None,
        location_name=emp.location.name if emp and emp.location else None,
        department_id=emp.department_id if emp else None,
        department_name=emp.department.name if emp and emp.department else None,
        designation=emp.designation if emp else None,
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=TokenResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    emp = current_user.employee
    token = create_access_token(
        subject=current_user.id,
        role=current_user.role.value,
        employee_id=emp.id if emp else None,
    )
    return TokenResponse(
        access_token=token,
        user_id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        employee_id=emp.id if emp else None,
        employee_name=emp.full_name if emp else None,
        location_id=emp.location_id if emp else None,
        location_name=emp.location.name if emp and emp.location else None,
        department_id=emp.department_id if emp else None,
        department_name=emp.department.name if emp and emp.department else None,
        designation=emp.designation if emp else None,
    )


@router.get("/personas", response_model=List[PersonaOption])
def list_personas(db: Session = Depends(get_db)):
    """
    Returns pre-configured enterprise personas for quick demo switching.
    """
    employees = (
        self_employees := db.query(Employee)
        .options(
            joinedload(Employee.user),
            joinedload(Employee.department),
            joinedload(Employee.location),
        )
        .order_by(Employee.hire_date.asc())
        .all()
    )

    personas = []
    descriptions = {
        "arun.kumar@company.com": "Software Engineer in Chennai (IC). Tests individual leave applications and location holidays.",
        "priya.sharma@company.com": "Senior Engineer in Bangalore (IC). Tests Bangalore policy differences and team conflict detection.",
        "rajesh.nair@company.com": "Engineering Manager in Chennai. Reviews and actions tier-1 leave approval requests.",
        "ananya.deshmukh@company.com": "VP of Engineering in Bangalore. Multi-tier approver and workforce oversight.",
        "sarah.jenkins@company.com": "HR Lead / Admin in Bangalore. Policy management and workforce intelligence access.",
    }

    for emp in employees:
        if emp.user:
            personas.append(
                PersonaOption(
                    id=emp.user.id,
                    name=emp.full_name,
                    email=emp.email,
                    role=emp.user.role,
                    designation=emp.designation,
                    department_name=emp.department.name if emp.department else "Engineering",
                    location_name=emp.location.name if emp.location else "Chennai",
                    avatar_url=emp.avatar_url,
                    description=descriptions.get(emp.email, f"{emp.designation} in {emp.department.name}"),
                )
            )

    return personas


@router.post("/switch-persona/{user_id}", response_model=TokenResponse)
def switch_persona(
    user_id: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    1-Click Demo Persona switcher that immediately updates the session cookie.
    """
    user = (
        db.query(User)
        .options(
            joinedload(User.employee).joinedload(Employee.department),
            joinedload(User.employee).joinedload(Employee.location),
        )
        .filter(User.id == user_id, User.is_active == True)
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="Persona user not found")

    emp_id = user.employee.id if user.employee else None
    token = create_access_token(subject=user.id, role=user.role.value, employee_id=emp_id)

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )

    emp = user.employee
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        employee_id=emp.id if emp else None,
        employee_name=emp.full_name if emp else None,
        location_id=emp.location_id if emp else None,
        location_name=emp.location.name if emp and emp.location else None,
        department_id=emp.department_id if emp else None,
        department_name=emp.department.name if emp and emp.department else None,
        designation=emp.designation if emp else None,
    )
