import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_employee, get_current_user
from app.models.user import User
from app.models.employee import Employee
from app.models.leave import LeaveType, LeavePolicy
from app.models.request import LeaveRequest
from app.services.leave_service import LeaveService
from app.schemas.leave import (
    LeaveTypeOut,
    LeavePolicyOut,
    LeaveRequestCreate,
    LeaveRequestOut,
    ApprovalStepOut,
    WhatIfRequest,
    WhatIfResponse,
)
from app.schemas.validation import PreValidationRequest, PreValidationResponse

router = APIRouter(prefix="/leave", tags=["Leave Management"])


def _format_leave_request_out(req: LeaveRequest) -> LeaveRequestOut:
    steps = [
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
        for s in req.approval_steps
    ]

    return LeaveRequestOut(
        id=req.id,
        employee_id=req.employee_id,
        employee_name=req.employee.full_name,
        employee_email=req.employee.email,
        department_name=req.employee.department.name if req.employee.department else "General",
        location_name=req.employee.location.name if req.employee.location else "HQ",
        leave_type_id=req.leave_type_id,
        leave_type_name=req.leave_type.name,
        leave_type_code=req.leave_type.code,
        leave_type_color=req.leave_type.color_code,
        start_date=req.start_date,
        end_date=req.end_date,
        calendar_days=req.calendar_days,
        weekend_days=req.weekend_days,
        holiday_days=req.holiday_days,
        working_days=req.working_days,
        reason=req.reason,
        status=req.status,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
        updated_at=req.updated_at,
        approval_steps=steps,
    )


@router.get("/types", response_model=List[LeaveTypeOut])
def get_leave_types(db: Session = Depends(get_db)):
    types = db.query(LeaveType).filter(LeaveType.is_active == True).all()
    return [
        LeaveTypeOut(
            id=t.id,
            name=t.name,
            code=t.code,
            description=t.description,
            is_paid=t.is_paid,
            color_code=t.color_code,
            is_active=t.is_active,
        )
        for t in types
    ]


@router.get("/policies", response_model=List[LeavePolicyOut])
def get_leave_policies(
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    policies = (
        db.query(LeavePolicy)
        .filter(
            LeavePolicy.location_id == current_employee.location_id,
            LeavePolicy.is_active == True,
        )
        .all()
    )
    return [
        LeavePolicyOut(
            id=p.id,
            leave_type_id=p.leave_type_id,
            leave_type_name=p.leave_type.name,
            location_id=p.location_id,
            location_name=p.location.name,
            max_consecutive_days=p.max_consecutive_days,
            requires_document_after_days=p.requires_document_after_days,
            advance_notice_days=p.advance_notice_days,
            carry_forward_limit=p.carry_forward_limit,
            allow_negative_balance=p.allow_negative_balance,
        )
        for p in policies
    ]


@router.post("/validate", response_model=PreValidationResponse)
def validate_proposed_leave(
    req: PreValidationRequest,
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Real-time deterministic pre-validation calculating weekends, holidays,
    net working days, balance before/after, approval route, and team conflicts.
    """
    service = LeaveService(db)
    val_res = service.pre_validate(
        employee_id=current_employee.id,
        leave_type_id=req.leave_type_id,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    holidays_map = service.employee_service.get_location_holidays_map(
        current_employee.location_id, req.start_date.year
    )
    from app.domain.working_days import calculate_working_days
    breakdown = calculate_working_days(req.start_date, req.end_date, holidays_map)

    return PreValidationResponse(
        is_valid=val_res.is_valid,
        calendar_days=val_res.calendar_days,
        weekend_days=val_res.weekend_days,
        holiday_days=val_res.holiday_days,
        working_days=val_res.working_days,
        available_balance_before=val_res.available_balance_before,
        available_balance_after=val_res.available_balance_after,
        has_overlapping_request=val_res.has_overlapping_request,
        policy_violations=val_res.policy_violations,
        warnings=val_res.warnings,
        approval_route=val_res.approval_route,
        day_breakdown=breakdown.details,
        conflict_analysis=val_res.conflict_analysis,
    )


@router.post("/submit", response_model=LeaveRequestOut)
def submit_leave_request(
    data: LeaveRequestCreate,
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = LeaveService(db)
    created_request = service.submit_leave_request(
        employee_id=current_employee.id,
        leave_type_id=data.leave_type_id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
    )
    return _format_leave_request_out(created_request)


@router.get("/my-requests", response_model=List[LeaveRequestOut])
def get_my_leave_requests(
    status: Optional[str] = Query(None, description="Status filter: PENDING, APPROVED, REJECTED, CANCELLED, or ALL"),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = LeaveService(db)
    requests = service.get_employee_requests(current_employee.id, status)
    return [_format_leave_request_out(r) for r in requests]


@router.post("/what-if", response_model=WhatIfResponse)
def simulate_what_if_leave(
    req: WhatIfRequest,
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Read-only hypothetical projection of leave impact. Never mutates database records.
    """
    service = LeaveService(db)
    val_res = service.pre_validate(
        employee_id=current_employee.id,
        leave_type_id=req.leave_type_id,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    holidays_map = service.employee_service.get_location_holidays_map(
        current_employee.location_id, req.start_date.year
    )
    from app.domain.working_days import calculate_working_days
    breakdown = calculate_working_days(req.start_date, req.end_date, holidays_map)

    return WhatIfResponse(
        start_date=req.start_date,
        end_date=req.end_date,
        calendar_days=val_res.calendar_days,
        weekend_days=val_res.weekend_days,
        holiday_days=val_res.holiday_days,
        working_days=val_res.working_days,
        day_breakdown=breakdown.details,
        available_balance_before=val_res.available_balance_before,
        projected_available_after=val_res.available_balance_after,
        is_valid=val_res.is_valid,
        policy_violations=val_res.policy_violations,
        warnings=val_res.warnings,
        approval_route=val_res.approval_route,
        conflict_analysis=val_res.conflict_analysis,
    )


@router.post("/{request_id}/cancel", response_model=LeaveRequestOut)
def cancel_leave_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = LeaveService(db)
    cancelled = service.cancel_leave_request(
        request_id=request_id,
        employee_id=current_employee.id,
        actor_email=current_user.email,
    )
    return _format_leave_request_out(cancelled)
