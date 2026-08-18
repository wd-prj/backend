import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.models.leave import AccrualFrequency


class CreateLeaveTypeRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    description: Optional[str] = None
    is_paid: bool = True
    color_code: str = "#4f46e5"
    annual_entitlement: float = Field(12.0, ge=0.0, le=365.0)
    max_carry_forward: float = Field(0.0, ge=0.0, le=100.0)
    frequency: AccrualFrequency = AccrualFrequency.YEARLY
    max_consecutive_days: Optional[int] = 10
    advance_notice_days: int = 1
    requires_document_after_days: Optional[int] = None
    allow_negative_balance: bool = False


class UpdateLeaveTypeRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_paid: Optional[bool] = None
    color_code: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateAccrualPolicyRequest(BaseModel):
    annual_entitlement: float = Field(..., ge=0.0, le=365.0)
    max_carry_forward: float = Field(..., ge=0.0, le=100.0)
    frequency: AccrualFrequency = AccrualFrequency.YEARLY
    sync_existing_employees: bool = True


class UpdateLeavePolicyRequest(BaseModel):
    max_consecutive_days: Optional[int] = None
    advance_notice_days: int = 0
    requires_document_after_days: Optional[int] = None
    carry_forward_limit: float = 5.0
    allow_negative_balance: bool = False


class AdjustBalanceRequest(BaseModel):
    employee_id: str
    leave_type_id: str
    adjustment_days: float
    year: Optional[int] = None
    reason: str = Field(..., min_length=3, max_length=500)


class AccrualPolicyDetail(BaseModel):
    id: str
    location_id: str
    location_name: str
    frequency: str
    annual_entitlement: float
    max_carry_forward: float


class LeavePolicyDetail(BaseModel):
    id: str
    location_id: str
    location_name: str
    max_consecutive_days: Optional[int] = None
    requires_document_after_days: Optional[int] = None
    advance_notice_days: int
    carry_forward_limit: float
    allow_negative_balance: bool
    is_active: bool


class FullLeaveTypeConfiguration(BaseModel):
    id: str
    name: str
    code: str
    description: Optional[str] = None
    is_paid: bool
    color_code: str
    is_active: bool
    accrual_policies: List[AccrualPolicyDetail] = []
    leave_policies: List[LeavePolicyDetail] = []


class LeaveConfigOverview(BaseModel):
    leave_types: List[FullLeaveTypeConfiguration]
    locations: List[dict]
