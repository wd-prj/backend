import uuid
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.employee import Employee
from app.models.organization import Department, Location
from app.models.leave import LeaveType, LeavePolicy, AccrualPolicy, EmployeeAccrual
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    PersonaOption,
    OrgMetaResponse,
    OrgOption,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/org-metadata", response_model=OrgMetaResponse)
def get_org_metadata(db: Session = Depends(get_db)):
    """Returns available departments and locations for user registration."""
    depts = db.query(Department).order_by(Department.name.asc()).all()
    locs = db.query(Location).order_by(Location.name.asc()).all()
    return OrgMetaResponse(
        departments=[OrgOption(id=d.id, name=d.name) for d in depts],
        locations=[OrgOption(id=l.id, name=f"{l.name} ({l.country})") for l in locs],
    )


@router.post("/register", response_model=TokenResponse)
def register(
    register_data: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Registers a new user and employee profile, sets default leave accruals, and logs in."""
    email_clean = register_data.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this work email already exists.",
        )

    # Resolve department and location
    dept = None
    if register_data.department_id:
        dept = db.query(Department).filter(Department.id == register_data.department_id).first()
    if not dept:
        dept = db.query(Department).first()

    loc = None
    if register_data.location_id:
        loc = db.query(Location).filter(Location.id == register_data.location_id).first()
    if not loc:
        loc = db.query(Location).first()

    if not dept or not loc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization setup incomplete (missing department or location).",
        )

    # Find a default manager in the department if any
    manager = (
        db.query(Employee)
        .join(User)
        .filter(
            Employee.department_id == dept.id,
            User.role.in_([UserRole.MANAGER, UserRole.HR_ADMIN]),
        )
        .first()
    )

    # 1. Create User
    new_user = User(
        email=email_clean,
        password_hash=get_password_hash(register_data.password),
        role=register_data.role or UserRole.EMPLOYEE,
        is_active=True,
    )
    db.add(new_user)
    db.flush()

    # 2. Create Employee
    new_code = f"EMP-{uuid.uuid4().hex[:6].upper()}"
    new_employee = Employee(
        user_id=new_user.id,
        employee_code=new_code,
        email=email_clean,
        first_name=register_data.full_name.split()[0] if register_data.full_name else "Employee",
        last_name=" ".join(register_data.full_name.split()[1:]) if " " in register_data.full_name else "",
        designation=register_data.designation or "Team Member",
        department_id=dept.id,
        location_id=loc.id,
        manager_id=manager.id if manager else None,
        hire_date=datetime.date.today(),
        is_active=True,
    )
    db.add(new_employee)
    db.flush()

    # 3. Create default leave accruals for active leave types
    current_year = datetime.date.today().year
    leave_types = db.query(LeaveType).filter(LeaveType.is_active == True).all()
    default_entitlements = {
        "ANNUAL": 18.0,
        "CASUAL": 12.0,
        "SICK": 10.0,
        "PARENTAL": 0.0,
    }

    for lt in leave_types:
        entitlement = default_entitlements.get(lt.code, 10.0)
        accrual = EmployeeAccrual(
            employee_id=new_employee.id,
            leave_type_id=lt.id,
            year=current_year,
            annual_entitlement=entitlement,
            carried_over=0.0,
            manual_adjustments=0.0,
        )
        db.add(accrual)

    db.commit()
    db.refresh(new_user)
    db.refresh(new_employee)

    # Create session token and set cookie
    token = create_access_token(
        subject=new_user.id,
        role=new_user.role.value,
        employee_id=new_employee.id,
    )

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

    return TokenResponse(
        access_token=token,
        user_id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        employee_id=new_employee.id,
        employee_name=new_employee.full_name,
        location_id=new_employee.location_id,
        location_name=loc.name,
        department_id=new_employee.department_id,
        department_name=dept.name,
        designation=new_employee.designation,
    )


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
            detail="Invalid work email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

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
