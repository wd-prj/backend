from typing import List, Optional
from pydantic import BaseModel


class LeaveBalanceSummary(BaseModel):
    leave_type_id: str
    leave_type_name: str
    leave_type_code: str
    annual_entitlement: float
    carried_over: float
    manual_adjustments: float
    total_accrued: float
    approved_used: float
    pending_reserved: float
    available_balance: float


def compute_dynamic_balance(
    leave_type_id: str,
    leave_type_name: str,
    leave_type_code: str,
    annual_entitlement: float,
    carried_over: float,
    manual_adjustments: float,
    approved_working_days: float,
    pending_working_days: float,
) -> LeaveBalanceSummary:
    """
    Computes dynamic leave balance:
    Available Leave = Accrued Entitlement - Approved/Used Leave - Pending Reserved Leave.
    Never relies on a statically stored editable balance column.
    """
    total_accrued = annual_entitlement + carried_over + manual_adjustments
    available = max(0.0, total_accrued - approved_working_days - pending_working_days)

    return LeaveBalanceSummary(
        leave_type_id=leave_type_id,
        leave_type_name=leave_type_name,
        leave_type_code=leave_type_code,
        annual_entitlement=annual_entitlement,
        carried_over=carried_over,
        manual_adjustments=manual_adjustments,
        total_accrued=total_accrued,
        approved_used=approved_working_days,
        pending_reserved=pending_working_days,
        available_balance=available,
    )
