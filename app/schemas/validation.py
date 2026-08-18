import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.domain.working_days import DayDetail
from app.domain.conflict_detector import ConflictAnalysis


class PreValidationRequest(BaseModel):
    leave_type_id: str
    start_date: datetime.date
    end_date: datetime.date


class PreValidationResponse(BaseModel):
    is_valid: bool
    calendar_days: int
    weekend_days: int
    holiday_days: int
    working_days: float
    available_balance_before: float
    available_balance_after: float
    has_overlapping_request: bool
    policy_violations: List[str]
    warnings: List[str]
    approval_route: List[str]
    day_breakdown: List[DayDetail]
    conflict_analysis: Optional[ConflictAnalysis] = None
