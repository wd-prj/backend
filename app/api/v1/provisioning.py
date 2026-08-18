import secrets
import hashlib
import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole, UserStatus
from app.models.employee import Employee
from app.models.organization import Department, Team, Location
from app.models.invitation import Invitation
from app.models.leave import LeaveType, EmployeeAccrual
from app.models.audit import AuditLog
from app.services.email.service import email_service
from app.schemas.provisioning import (
    InviteManagerRequest,
    InviteEmployeeRequest,
    ResendInviteRequest,
    TeamMemberInfo,
    TeamInfo,
)

router = APIRouter(prefix="/provisioning", tags=["Provisioning & Team Management"])


def generate_invitation_token() -> tuple[str, str]:
    """Generates a secure raw token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


@router.post("/invite-manager", response_model=dict)
def invite_manager(
    req: InviteManagerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only HR Admins can provision manager accounts."""
    if current_user.role != UserRole.HR_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only HR Administrators can provision manager accounts.",
        )

    # Check if email exists
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email {req.email} already exists.",
        )

    # Validate department and location
    dept = db.query(Department).filter(Department.id == req.department_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    loc = db.query(Location).filter(Location.id == req.location_id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Create User with INVITED status
    new_user = User(
        email=req.email,
        password_hash="",  # Placeholder until invitation acceptance
        role=UserRole.MANAGER,
        status=UserStatus.INVITED,
        is_active=False,
    )
    db.add(new_user)
    db.flush()

    # Split name
    parts = req.full_name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    # Create Team if not exists, or find existing
    team = db.query(Team).filter(Team.department_id == dept.id, Team.name == req.team_name).first()
    if not team:
        team_code = f"{dept.code}-{req.team_name[:4].upper()}"
        team = Team(
            name=req.team_name,
            code=team_code,
            department_id=dept.id,
            description=f"Managed by {req.full_name}",
        )
        db.add(team)
        db.flush()

    # Find department leadership or fallback to current admin
    dept_head_emp = (
        db.query(Employee)
        .join(User)
        .filter(
            Employee.department_id == dept.id,
            User.role == UserRole.MANAGER,
        )
        .order_by(Employee.created_at.asc())
        .first()
    )
    reporting_lead_id = dept_head_emp.id if dept_head_emp else (current_user.employee.id if current_user.employee else None)

    # Create Employee
    emp_code = f"MGR-{uuid.uuid4().hex[:6].upper()}"
    emp = Employee(
        user_id=new_user.id,
        employee_code=emp_code,
        first_name=first_name,
        last_name=last_name,
        email=req.email,
        department_id=dept.id,
        team_id=team.id,
        location_id=loc.id,
        primary_manager_id=reporting_lead_id,
        manager_id=reporting_lead_id,
        designation=req.designation,
        hire_date=datetime.date.today(),
        is_active=False,
    )
    db.add(emp)
    db.flush()

    # Set manager on team
    team.manager_id = emp.id

    # Create default leave accruals
    leave_types = db.query(LeaveType).all()
    current_year = datetime.datetime.now().year
    for lt in leave_types:
        entitlement = 18.0 if lt.code == "ANNUAL" else 12.0 if lt.code == "CASUAL" else 10.0 if lt.code == "SICK" else 0.0
        db.add(EmployeeAccrual(
            employee_id=emp.id,
            leave_type_id=lt.id,
            year=current_year,
            annual_entitlement=entitlement,
            carried_over=0.0,
            manual_adjustments=0.0,
        ))

    # Generate Secure Invitation Token
    raw_token, token_hash = generate_invitation_token()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=settings.INVITATION_EXPIRE_HOURS
    )
    invitation = Invitation(
        token_hash=token_hash,
        expires_at=expires_at,
        invited_user_id=new_user.id,
        invited_by_id=current_user.id,
    )
    db.add(invitation)

    # Audit log
    db.add(AuditLog(
        entity_type="EMPLOYEE",
        entity_id=emp.id,
        action="PROVISION_MANAGER_INVITED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        new_state={"email": req.email, "role": "MANAGER", "team": team.name, "dept": dept.name},
    ))

    db.commit()

    # Dispatch Invitation Email via Resend
    email_res = email_service.send_invitation_email(
        to_email=req.email,
        name=req.full_name,
        role="Manager",
        department=dept.name,
        team=team.name,
        manager=current_user.employee.full_name if current_user.employee else "HR Leadership",
        location=loc.name,
        raw_token=raw_token,
    )

    invite_url = f"{settings.APP_URL}/accept-invitation?token={raw_token}"
    return {
        "message": f"Invitation dispatched to {req.email}",
        "employee_id": emp.id,
        "invitation_id": invitation.id,
        "team_id": team.id,
        "invite_url": invite_url,
    }


@router.post("/invite-employee", response_model=dict)
def invite_employee(
    req: InviteEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Managers provision employees within their team; HR Admins can provision to any team."""
    if current_user.role not in [UserRole.MANAGER, UserRole.HR_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only Managers and HR Administrators can provision employee accounts.",
        )

    manager_emp = current_user.employee

    # Resolve team: if omitted by a manager, use the team managed by them or their assigned team
    target_team_id = req.team_id
    if not target_team_id and current_user.role == UserRole.MANAGER and manager_emp:
        managed_team = db.query(Team).filter(Team.manager_id == manager_emp.id).first()
        target_team_id = managed_team.id if managed_team else manager_emp.team_id

    if not target_team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned team is required")

    # Check team existence
    team = db.query(Team).filter(Team.id == target_team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # If manager, verify authorization (must manage this team or department)
    if current_user.role == UserRole.MANAGER and manager_emp:
        if team.manager_id != manager_emp.id and team.department_id != manager_emp.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Managers can only provision employees for their authorized teams.",
            )

    # Check email uniqueness
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email {req.email} already exists.",
        )

    # Auto-resolve department and location if not provided
    target_dept_id = req.department_id or (manager_emp.department_id if manager_emp else team.department_id)
    target_loc_id = req.location_id or (manager_emp.location_id if manager_emp else None)
    if not target_loc_id:
        first_loc = db.query(Location).first()
        target_loc_id = first_loc.id if first_loc else None

    dept = db.query(Department).filter(Department.id == target_dept_id).first()
    loc = db.query(Location).filter(Location.id == target_loc_id).first()
    if not dept or not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department or Location not found")

    # Authoritative Primary Manager ID
    primary_manager_id = (
        manager_emp.id
        if current_user.role == UserRole.MANAGER and manager_emp
        else req.primary_manager_id or team.manager_id or (manager_emp.id if manager_emp else None)
    )

    # Create User with INVITED status
    new_user = User(
        email=req.email,
        password_hash="",
        role=UserRole.EMPLOYEE,
        status=UserStatus.INVITED,
        is_active=False,
    )
    db.add(new_user)
    db.flush()

    parts = req.full_name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    emp_code = f"EMP-{uuid.uuid4().hex[:6].upper()}"
    emp = Employee(
        user_id=new_user.id,
        employee_code=emp_code,
        first_name=first_name,
        last_name=last_name,
        email=req.email,
        department_id=dept.id,
        team_id=team.id,
        location_id=loc.id,
        primary_manager_id=primary_manager_id,
        manager_id=primary_manager_id,
        designation=req.designation,
        hire_date=datetime.date.today(),
        is_active=False,
    )
    db.add(emp)
    db.flush()

    # Create default leave accruals
    leave_types = db.query(LeaveType).all()
    current_year = datetime.datetime.now().year
    for lt in leave_types:
        entitlement = 18.0 if lt.code == "ANNUAL" else 12.0 if lt.code == "CASUAL" else 10.0 if lt.code == "SICK" else 0.0
        db.add(EmployeeAccrual(
            employee_id=emp.id,
            leave_type_id=lt.id,
            year=current_year,
            annual_entitlement=entitlement,
            carried_over=0.0,
            manual_adjustments=0.0,
        ))

    # Generate Secure Invitation Token
    raw_token, token_hash = generate_invitation_token()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=settings.INVITATION_EXPIRE_HOURS
    )
    invitation = Invitation(
        token_hash=token_hash,
        expires_at=expires_at,
        invited_user_id=new_user.id,
        invited_by_id=current_user.id,
    )
    db.add(invitation)

    # Audit log
    db.add(AuditLog(
        entity_type="EMPLOYEE",
        entity_id=emp.id,
        action="PROVISION_EMPLOYEE_INVITED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        new_state={"email": req.email, "role": "EMPLOYEE", "team": team.name, "dept": dept.name},
    ))

    db.commit()

    # Determine Manager Name for Email
    manager_obj = db.query(Employee).filter(Employee.id == primary_manager_id).first() if primary_manager_id else None
    manager_name = manager_obj.full_name if manager_obj else "Direct Lead"

    # Dispatch Email via Resend
    email_res = email_service.send_invitation_email(
        to_email=req.email,
        name=req.full_name,
        role="Employee",
        department=dept.name,
        team=team.name,
        manager=manager_name,
        location=loc.name,
        raw_token=raw_token,
    )

    invite_url = f"{settings.APP_URL}/accept-invitation?token={raw_token}"
    return {
        "message": f"Invitation dispatched to {req.email}",
        "employee_id": emp.id,
        "invitation_id": invitation.id,
        "invite_url": invite_url,
    }


@router.get("/members", response_model=List[TeamMemberInfo])
def list_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists provisioned and active members within caller's scope."""
    query = db.query(Employee).join(User, Employee.user_id == User.id)

    if current_user.role == UserRole.MANAGER:
        manager_emp = current_user.employee
        if manager_emp:
            # Manager sees direct reports or team members
            query = query.filter(
                (Employee.primary_manager_id == manager_emp.id) |
                (Employee.manager_id == manager_emp.id) |
                (Employee.team_id.in_(
                    db.query(Team.id).filter(Team.manager_id == manager_emp.id)
                ))
            )
    elif current_user.role == UserRole.EMPLOYEE:
        # IC only sees themselves
        query = query.filter(Employee.user_id == current_user.id)

    employees = query.order_by(Employee.created_at.desc()).all()

    result = []
    for emp in employees:
        mgr = db.query(Employee).filter(Employee.id == emp.primary_manager_id).first() if emp.primary_manager_id else None
        result.append(TeamMemberInfo(
            id=emp.id,
            user_id=emp.user_id,
            employee_code=emp.employee_code,
            first_name=emp.first_name,
            last_name=emp.last_name,
            full_name=emp.full_name,
            email=emp.email,
            role=emp.user.role if emp.user else UserRole.EMPLOYEE,
            status=emp.user.status if emp.user else UserStatus.ACTIVE,
            department_id=emp.department_id,
            department_name=emp.department.name if emp.department else "",
            team_id=emp.team_id,
            team_name=emp.team.name if emp.team else "General",
            primary_manager_id=emp.primary_manager_id,
            manager_name=mgr.full_name if mgr else None,
            location_id=emp.location_id,
            location_name=emp.location.name if emp.location else "",
            designation=emp.designation,
            hire_date=emp.hire_date,
            created_at=emp.created_at,
        ))

    return result


@router.get("/teams", response_model=List[TeamInfo])
def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists organization teams."""
    teams = db.query(Team).all()
    result = []
    for t in teams:
        member_cnt = db.query(Employee).filter(Employee.team_id == t.id).count()
        result.append(TeamInfo(
            id=t.id,
            name=t.name,
            code=t.code,
            department_id=t.department_id,
            department_name=t.department.name if t.department else "",
            manager_id=t.manager_id,
            manager_name=t.manager.full_name if t.manager else None,
            member_count=member_cnt,
        ))
    return result


@router.post("/resend-invite", response_model=dict)
def resend_invite(
    req: ResendInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend a fresh invitation token email to an invited user."""
    if current_user.role not in [UserRole.MANAGER, UserRole.HR_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.status != UserStatus.INVITED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already active.")

    emp = target_user.employee
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee record not found")

    # Generate new token
    raw_token, token_hash = generate_invitation_token()
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=settings.INVITATION_EXPIRE_HOURS
    )

    # Invalidate previous unaccepted invites
    db.query(Invitation).filter(
        Invitation.invited_user_id == target_user.id,
        Invitation.used_at.is_(None),
    ).delete()

    new_invite = Invitation(
        token_hash=token_hash,
        expires_at=expires_at,
        invited_user_id=target_user.id,
        invited_by_id=current_user.id,
    )
    db.add(new_invite)
    db.commit()

    # Determine Manager Name
    mgr = db.query(Employee).filter(Employee.id == emp.primary_manager_id).first() if emp.primary_manager_id else None

    # Resend email
    email_res = email_service.send_invitation_email(
        to_email=target_user.email,
        name=emp.full_name,
        role=target_user.role.value.capitalize(),
        department=emp.department.name if emp.department else "",
        team=emp.team.name if emp.team else "General",
        manager=mgr.full_name if mgr else "Direct Lead",
        location=emp.location.name if emp.location else "",
        raw_token=raw_token,
    )

    invite_url = f"{settings.APP_URL}/accept-invitation?token={raw_token}"
    return {
        "message": f"Invitation dispatched to {target_user.email}",
        "invite_url": invite_url,
    }
