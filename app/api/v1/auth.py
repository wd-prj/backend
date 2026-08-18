import hashlib
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.deps import get_current_user
from app.models.user import User, UserRole, UserStatus
from app.models.employee import Employee
from app.models.organization import Department, Team, Location
from app.models.invitation import Invitation
from app.models.audit import AuditLog
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    OrgMetaResponse,
    OrgOption,
)
from app.schemas.provisioning import (
    InvitationDetailsResponse,
    AcceptInvitationRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/org-metadata", response_model=OrgMetaResponse)
def get_org_metadata(db: Session = Depends(get_db)):
    """Returns available departments and locations for provisioning."""
    depts = db.query(Department).order_by(Department.name.asc()).all()
    locs = db.query(Location).order_by(Location.name.asc()).all()
    return OrgMetaResponse(
        departments=[OrgOption(id=d.id, name=d.name) for d in depts],
        locations=[OrgOption(id=l.id, name=f"{l.name} ({l.country})") for l in locs],
    )


@router.get("/invitation-details", response_model=InvitationDetailsResponse)
def get_invitation_details(
    token: str,
    db: Session = Depends(get_db),
):
    """Public endpoint to validate an invitation token and view organizational assignment."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token is required.",
        )

    token_hash = hashlib.sha256(token.strip().encode()).hexdigest()
    now = datetime.datetime.now(datetime.timezone.utc)

    invitation = (
        db.query(Invitation)
        .options(
            joinedload(Invitation.invited_user)
            .joinedload(User.employee)
            .joinedload(Employee.department),
            joinedload(Invitation.invited_user)
            .joinedload(User.employee)
            .joinedload(Employee.location),
            joinedload(Invitation.invited_user)
            .joinedload(User.employee)
            .joinedload(Employee.team),
        )
        .filter(Invitation.token_hash == token_hash)
        .first()
    )

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token. Please check your invitation link.",
        )

    if invitation.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has already been accepted. Please sign in with your credentials.",
        )

    if invitation.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired (valid for 48 hours). Please contact your administrator for a new invitation.",
        )

    user = invitation.invited_user
    emp = user.employee
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Employee profile not found for invited user.",
        )

    mgr = (
        db.query(Employee).filter(Employee.id == emp.primary_manager_id).first()
        if emp.primary_manager_id
        else None
    )

    return InvitationDetailsResponse(
        invitation_id=invitation.id,
        email=user.email,
        full_name=emp.full_name,
        role=user.role,
        department_name=emp.department.name if emp.department else "General",
        team_name=emp.team.name if emp.team else "General",
        manager_name=mgr.full_name if mgr else None,
        location_name=emp.location.name if emp.location else "HQ",
        designation=emp.designation,
        expires_at=invitation.expires_at,
    )


@router.post("/accept-invitation", response_model=TokenResponse)
def accept_invitation(
    req: AcceptInvitationRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Accepts an organization invitation, sets secure password, and activates account."""
    if not req.token or not req.password or len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid invitation token and password (at least 6 characters) are required.",
        )

    token_hash = hashlib.sha256(req.token.strip().encode()).hexdigest()
    now = datetime.datetime.now(datetime.timezone.utc)

    invitation = (
        db.query(Invitation)
        .options(
            joinedload(Invitation.invited_user).joinedload(User.employee).joinedload(Employee.department),
            joinedload(Invitation.invited_user).joinedload(User.employee).joinedload(Employee.location),
        )
        .filter(Invitation.token_hash == token_hash)
        .first()
    )

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token.",
        )

    if invitation.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has already been accepted. Please sign in.",
        )

    if invitation.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired. Please ask your administrator to resend the invitation.",
        )

    user = invitation.invited_user
    emp = user.employee
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Employee profile missing.",
        )

    # 1. Update user password and activate
    user.password_hash = get_password_hash(req.password)
    user.status = UserStatus.ACTIVE
    user.is_active = True
    emp.is_active = True

    # 2. Mark invitation single-use redeemed
    invitation.used_at = now

    # 3. Log audit event
    db.add(AuditLog(
        entity_type="USER",
        entity_id=user.id,
        action="INVITATION_ACCEPTED",
        actor_id=user.id,
        actor_email=user.email,
        new_state={"email": user.email, "role": user.role.value, "status": "ACTIVE"},
    ))

    db.commit()
    db.refresh(user)
    db.refresh(emp)

    # 4. Issue JWT and set session cookie
    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        employee_id=emp.id,
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
        user_id=user.id,
        email=user.email,
        role=user.role,
        employee_id=emp.id,
        employee_name=emp.full_name,
        location_id=emp.location_id,
        location_name=emp.location.name if emp.location else None,
        department_id=emp.department_id,
        department_name=emp.department.name if emp.department else None,
        designation=emp.designation,
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

    if user.status == UserStatus.INVITED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your invitation has not been accepted yet. Please check your invitation email.",
        )

    if not user.is_active or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.value.lower()}. Please contact HR.",
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
