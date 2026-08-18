import datetime
import pytest
from app.domain.working_days import WorkingDaysBreakdown
from app.domain.balance_engine import LeaveBalanceSummary
from app.domain.workflow_engine import WorkflowStepPlan
from app.domain.policy_rules import validate_leave_request_rules
from app.models.request import ApprovalRole


def test_leave_validation_valid():
    breakdown = WorkingDaysBreakdown(
        start_date=datetime.date(2026, 8, 20),
        end_date=datetime.date(2026, 8, 25),
        calendar_days=6,
        weekend_days=2,
        holiday_days=1,
        working_days=3.0,
        details=[],
    )
    balance = LeaveBalanceSummary(
        leave_type_id="lt_1",
        leave_type_name="Annual Leave",
        leave_type_code="ANNUAL",
        annual_entitlement=18.0,
        carried_over=0.0,
        manual_adjustments=0.0,
        total_accrued=18.0,
        approved_used=0.0,
        pending_reserved=0.0,
        available_balance=18.0,
    )
    approval_chain = [
        WorkflowStepPlan(
            step_order=1,
            required_role=ApprovalRole.MANAGER,
            approver_employee_id="emp_mgr",
            approver_name="Rajesh Nair",
            approver_email="rajesh@company.com",
            description="Manager Approval",
        )
    ]

    res = validate_leave_request_rules(
        start_date=datetime.date(2026, 8, 20),
        end_date=datetime.date(2026, 8, 25),
        working_days_breakdown=breakdown,
        balance_summary=balance,
        policy_max_consecutive_days=10,
        policy_advance_notice_days=0,
        policy_allow_negative_balance=False,
        existing_employee_requests=[],
        approval_chain=approval_chain,
        current_date=datetime.date(2026, 8, 1),
    )

    assert res.is_valid is True
    assert res.working_days == 3.0
    assert res.available_balance_before == 18.0
    assert res.available_balance_after == 15.0
    assert len(res.policy_violations) == 0


def test_leave_validation_insufficient_balance():
    breakdown = WorkingDaysBreakdown(
        start_date=datetime.date(2026, 8, 17),
        end_date=datetime.date(2026, 8, 21),
        calendar_days=5,
        weekend_days=0,
        holiday_days=0,
        working_days=5.0,
        details=[],
    )
    balance = LeaveBalanceSummary(
        leave_type_id="lt_1",
        leave_type_name="Annual Leave",
        leave_type_code="ANNUAL",
        annual_entitlement=2.0,
        carried_over=0.0,
        manual_adjustments=0.0,
        total_accrued=2.0,
        approved_used=0.0,
        pending_reserved=0.0,
        available_balance=2.0,
    )

    res = validate_leave_request_rules(
        start_date=datetime.date(2026, 8, 17),
        end_date=datetime.date(2026, 8, 21),
        working_days_breakdown=breakdown,
        balance_summary=balance,
        policy_max_consecutive_days=10,
        policy_advance_notice_days=0,
        policy_allow_negative_balance=False,
        existing_employee_requests=[],
        approval_chain=[],
        current_date=datetime.date(2026, 8, 1),
    )

    assert res.is_valid is False
    assert any("Insufficient leave balance" in v for v in res.policy_violations)


def test_leave_validation_overlapping_request():
    breakdown = WorkingDaysBreakdown(
        start_date=datetime.date(2026, 8, 18),
        end_date=datetime.date(2026, 8, 22),
        calendar_days=5,
        weekend_days=1,
        holiday_days=0,
        working_days=4.0,
        details=[],
    )
    balance = LeaveBalanceSummary(
        leave_type_id="lt_1",
        leave_type_name="Annual",
        leave_type_code="ANNUAL",
        annual_entitlement=20.0,
        carried_over=0.0,
        manual_adjustments=0.0,
        total_accrued=20.0,
        approved_used=0.0,
        pending_reserved=0.0,
        available_balance=20.0,
    )
    existing_requests = [
        {"start_date": datetime.date(2026, 8, 20), "end_date": datetime.date(2026, 8, 25), "status": "APPROVED"}
    ]

    res = validate_leave_request_rules(
        start_date=datetime.date(2026, 8, 18),
        end_date=datetime.date(2026, 8, 22),
        working_days_breakdown=breakdown,
        balance_summary=balance,
        policy_max_consecutive_days=10,
        policy_advance_notice_days=0,
        policy_allow_negative_balance=False,
        existing_employee_requests=existing_requests,
        approval_chain=[],
        current_date=datetime.date(2026, 8, 1),
    )

    assert res.is_valid is False
    assert res.has_overlapping_request is True
    assert any("Overlapping request exists" in v for v in res.policy_violations)
