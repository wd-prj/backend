import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.domain.working_days import WorkingDaysBreakdown
from app.domain.balance_engine import LeaveBalanceSummary
from app.domain.conflict_detector import ConflictAnalysis
from app.domain.workflow_engine import WorkflowStepPlan


class LeaveValidationResult(BaseModel):
    is_valid: bool
    working_days: float
    calendar_days: int
    weekend_days: int
    holiday_days: int
    available_balance_before: float
    available_balance_after: float
    has_overlapping_request: bool
    policy_violations: List[str]
    warnings: List[str]
    approval_route: List[str]
    approval_plan: List[WorkflowStepPlan]
    conflict_analysis: Optional[ConflictAnalysis] = None


def validate_leave_request_rules(
    start_date: datetime.date,
    end_date: datetime.date,
    working_days_breakdown: WorkingDaysBreakdown,
    balance_summary: LeaveBalanceSummary,
    policy_max_consecutive_days: Optional[int],
    policy_advance_notice_days: int,
    policy_allow_negative_balance: bool,
    existing_employee_requests: List[Dict[str, Any]],
    approval_chain: List[WorkflowStepPlan],
    conflict_analysis: Optional[ConflictAnalysis] = None,
    current_date: Optional[datetime.date] = None,
) -> LeaveValidationResult:
    """
    Deterministically validates leave requests against HR policies, balances,
    advance notice rules, and existing overlapping requests.
    """
    today = current_date or datetime.date.today()
    violations: List[str] = []
    warnings: List[str] = []

    # 1. Date order sanity
    if start_date > end_date:
        violations.append("Start date cannot be after end date.")

    # 2. Check if zero working days
    if working_days_breakdown.working_days <= 0:
        violations.append("Selected date range contains 0 working days (all selected days are weekends or holidays).")

    # 3. Advance notice requirement
    days_in_advance = (start_date - today).days
    if policy_advance_notice_days > 0 and days_in_advance < policy_advance_notice_days:
        violations.append(
            f"Policy requires at least {policy_advance_notice_days} days advance notice. Requested start date is {days_in_advance} days away."
        )

    # 4. Maximum consecutive working days
    if policy_max_consecutive_days and working_days_breakdown.working_days > policy_max_consecutive_days:
        violations.append(
            f"Requested leave of {working_days_breakdown.working_days} working days exceeds the policy maximum limit of {policy_max_consecutive_days} consecutive days."
        )

    # 5. Balance sufficiency
    available_before = balance_summary.available_balance
    available_after = available_before - working_days_breakdown.working_days

    if not policy_allow_negative_balance and working_days_breakdown.working_days > available_before:
        violations.append(
            f"Insufficient leave balance: You have {available_before} days available, but requested {working_days_breakdown.working_days} working days."
        )

    # 6. Overlapping request check for same employee
    has_overlap = False
    for req in existing_employee_requests:
        status = req.get("status")
        if status in ("PENDING", "APPROVED"):
            r_start = req["start_date"]
            r_end = req["end_date"]
            if max(start_date, r_start) <= min(end_date, r_end):
                has_overlap = True
                violations.append(
                    f"Overlapping request exists: You already have a {status} leave from {r_start} to {r_end}."
                )
                break

    # 7. Add warnings from conflict analysis
    if conflict_analysis and conflict_analysis.has_conflicts:
        warnings.append(conflict_analysis.risk_summary)

    # Format human-readable approval route
    approval_route_names = [step.approver_name for step in approval_chain]

    return LeaveValidationResult(
        is_valid=len(violations) == 0,
        working_days=working_days_breakdown.working_days,
        calendar_days=working_days_breakdown.calendar_days,
        weekend_days=working_days_breakdown.weekend_days,
        holiday_days=working_days_breakdown.holiday_days,
        available_balance_before=available_before,
        available_balance_after=max(0.0, available_after) if not policy_allow_negative_balance else available_after,
        has_overlapping_request=has_overlap,
        policy_violations=violations,
        warnings=warnings,
        approval_route=approval_route_names,
        approval_plan=approval_chain,
        conflict_analysis=conflict_analysis,
    )
