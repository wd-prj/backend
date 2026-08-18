import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.models.request import LeaveRequestStatus, ApprovalStepStatus, ApprovalRole
from app.domain.working_days import DayDetail
from app.domain.conflict_detector import ConflictAnalysis


class LeaveTypeOut(BaseModel):
    id: str
    name: str
    code: str
    description: Optional[str] = None
    is_paid: bool
    color_code: str
    is_active: bool


class LeavePolicyOut(BaseModel):
    id: str
    leave_type_id: str
    leave_type_name: str
    location_id: str
    location_name: str
    max_consecutive_days: Optional[int] = None
    requires_document_after_days: Optional[int] = None
    advance_notice_days: int
    carry_forward_limit: float
    allow_negative_balance: bool


class LeaveBalanceOut(BaseModel):
    leave_type_id: str
    leave_type_name: str
    leave_type_code: str
    color_code: str
    annual_entitlement: float
    carried_over: float
    manual_adjustments: float
    total_accrued: float
    approved_used: float
    pending_reserved: float
    available_balance: float


class LeaveRequestCreate(BaseModel):
    leave_type_id: str
    start_date: datetime.date
    end_date: datetime.date
    reason: str = Field(..., min_length=3, max_length=1000)


class ApprovalStepOut(BaseModel):
    id: str
    step_order: int
    required_role: ApprovalRole
    approver_id: str
    approver_name: str
    approver_email: str
    status: ApprovalStepStatus
    comments: Optional[str] = None
    actioned_at: Optional[datetime.datetime] = None


class LeaveRequestOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_email: str
    department_name: str
    location_name: str
    leave_type_id: str
    leave_type_name: str
    leave_type_code: str
    leave_type_color: str
    start_date: datetime.date
    end_date: datetime.date
    calendar_days: int
    weekend_days: int
    holiday_days: int
    working_days: float
    reason: str
    status: LeaveRequestStatus
    rejection_reason: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    approval_steps: List[ApprovalStepOut] = []


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    comments: Optional[str] = None


class WhatIfRequest(BaseModel):
    leave_type_id: str
    start_date: datetime.date
    end_date: datetime.date


class WhatIfResponse(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    calendar_days: int
    weekend_days: int
    holiday_days: int
    working_days: float
    day_breakdown: List[DayDetail]
    available_balance_before: float
    projected_available_after: float
    is_valid: bool
    policy_violations: List[str]
    warnings: List[str]
    approval_route: List[str]
    conflict_analysis: Optional[ConflictAnalysis] = None
