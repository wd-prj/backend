from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_employee, require_role
from app.models.user import User, UserRole
from app.models.employee import Employee
from app.models.request import ApprovalStep, LeaveRequest
from app.services.approval_service import ApprovalService
from app.schemas.leave import ApprovalStepOut, LeaveRequestOut, ApprovalActionRequest
from app.api.v1.leave import _format_leave_request_out

router = APIRouter(prefix="/manager", tags=["Manager & Approvals"])


@router.get("/approvals", response_model=List[ApprovalStepOut])
def get_pending_approvals_inbox(
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = ApprovalService(db)
    steps = service.get_pending_approvals(current_employee.id)
    return [
        ApprovalStepOut(
            id=s.id,
            step_order=s.step_order,
            required_role=s.required_role,
            approver_id=s.approver_id,
            approver_name=s.approver.full_name if s.approver else "Approver",
            approver_email=s.approver.email if s.approver else "",
            status=s.status,
            comments=s.comments,
            actioned_at=s.actioned_at,
        )
        for s in steps
    ]


@router.get("/pending-requests", response_model=List[LeaveRequestOut])
def get_pending_leave_requests_details(
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = ApprovalService(db)
    steps = service.get_pending_approvals(current_employee.id)
    requests = [s.leave_request for s in steps]
    return [_format_leave_request_out(r) for r in requests]


@router.post("/approvals/{step_id}/action", response_model=LeaveRequestOut)
def action_pending_step(
    step_id: str,
    action_data: ApprovalActionRequest,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = ApprovalService(db)
    updated_request = service.action_approval_step(
        step_id=step_id,
        approver_employee_id=current_employee.id,
        action=action_data.action,
        comments=action_data.comments,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
    )
    return _format_leave_request_out(updated_request)


@router.get("/team-requests", response_model=List[LeaveRequestOut])
def get_team_requests(
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = ApprovalService(db)
    requests = service.get_all_requests_for_manager(current_employee.id)
    return [_format_leave_request_out(r) for r in requests]
