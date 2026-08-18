import pytest
from app.domain.balance_engine import compute_dynamic_balance


def test_dynamic_balance_no_usage():
    summary = compute_dynamic_balance(
        leave_type_id="lt_1",
        leave_type_name="Annual Leave",
        leave_type_code="ANNUAL",
        annual_entitlement=18.0,
        carried_over=3.0,
        manual_adjustments=0.0,
        approved_working_days=0.0,
        pending_working_days=0.0,
    )
    assert summary.total_accrued == 21.0
    assert summary.approved_used == 0.0
    assert summary.pending_reserved == 0.0
    assert summary.available_balance == 21.0


def test_dynamic_balance_with_approved_and_pending():
    # 18 accrued + 2 carried over = 20 total.
    # 5 days approved + 3 days pending = 8 days committed.
    # Available = 20 - 5 - 3 = 12.0
    summary = compute_dynamic_balance(
        leave_type_id="lt_1",
        leave_type_name="Annual Leave",
        leave_type_code="ANNUAL",
        annual_entitlement=18.0,
        carried_over=2.0,
        manual_adjustments=0.0,
        approved_working_days=5.0,
        pending_working_days=3.0,
    )
    assert summary.total_accrued == 20.0
    assert summary.approved_used == 5.0
    assert summary.pending_reserved == 3.0
    assert summary.available_balance == 12.0


def test_dynamic_balance_cannot_drop_below_zero():
    summary = compute_dynamic_balance(
        leave_type_id="lt_1",
        leave_type_name="Annual Leave",
        leave_type_code="ANNUAL",
        annual_entitlement=5.0,
        carried_over=0.0,
        manual_adjustments=0.0,
        approved_working_days=4.0,
        pending_working_days=3.0,
    )
    assert summary.available_balance == 0.0
