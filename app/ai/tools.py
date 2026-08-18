import datetime
import json
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.services.employee_service import EmployeeService
from app.services.leave_service import LeaveService
from app.models.leave import LeaveType, LeavePolicy
from app.models.employee import Employee


def build_tool_registry(db: Session, current_employee_id: str):
    """
    Constructs bound LangChain function tools injected with authenticated DB session
    and caller context.
    """
    employee_service = EmployeeService(db)
    leave_service = LeaveService(db)

    # Get employee details for defaults
    emp = employee_service.get_employee_by_id(current_employee_id)
    default_location_id = emp.location_id if emp else ""
    default_dept_id = emp.department_id if emp else ""

    @tool
    def get_employee_profile(employee_id: Optional[str] = None) -> str:
        """Retrieves verified employee profile, designation, department, and location."""
        target_id = employee_id or current_employee_id
        employee = employee_service.get_employee_by_id(target_id)
        if not employee:
            return json.dumps({"error": "Employee not found"})
        return json.dumps({
            "employee_id": employee.id,
            "name": employee.full_name,
            "email": employee.email,
            "designation": employee.designation,
            "department": employee.department.name,
            "location": employee.location.name,
            "manager": employee.manager.full_name if employee.manager else "None",
        })

    @tool
    def get_leave_balance(employee_id: Optional[str] = None, year: Optional[int] = None) -> str:
        """Retrieves current verified dynamic leave balances (Annual, Casual, Sick, etc.) for the authenticated employee."""
        target_id = employee_id or current_employee_id
        balances = employee_service.get_employee_balances(target_id, year)
        return json.dumps(balances)

    @tool
    def get_leave_types() -> str:
        """Retrieves list of all active company leave types and their codes."""
        types = db.query(LeaveType).filter(LeaveType.is_active == True).all()
        return json.dumps([{"id": t.id, "name": t.name, "code": t.code, "is_paid": t.is_paid} for t in types])

    @tool
    def get_leave_policies(location_id: Optional[str] = None) -> str:
        """Retrieves authoritative leave policies (maximum consecutive days, advance notice requirements, carryover limits) for the employee's location."""
        loc_id = location_id or default_location_id
        policies = (
            db.query(LeavePolicy)
            .filter(LeavePolicy.location_id == loc_id, LeavePolicy.is_active == True)
            .all()
        )
        return json.dumps([
            {
                "leave_type": p.leave_type.name if p.leave_type else "All",
                "max_consecutive_days": p.max_consecutive_days,
                "advance_notice_days": p.advance_notice_days,
                "carry_forward_limit": p.carry_forward_limit,
                "allow_negative_balance": p.allow_negative_balance,
            }
            for p in policies
        ])

    @tool
    def get_holidays(location_id: Optional[str] = None, year: Optional[int] = None) -> str:
        """Retrieves official upcoming company and regional holidays for the employee's location."""
        loc_id = location_id or default_location_id
        holidays = employee_service.get_location_holidays_list(loc_id, year)
        return json.dumps([{"name": h.name, "date": str(h.date), "is_mandatory": h.is_mandatory} for h in holidays])

    @tool
    def calculate_leave_days(start_date: str, end_date: str, location_id: Optional[str] = None) -> str:
        """
        Deterministically computes calendar days, weekend days, location holidays,
        and net working leave days for a requested date range.
        Format: YYYY-MM-DD
        """
        try:
            s_date = datetime.date.fromisoformat(start_date)
            e_date = datetime.date.fromisoformat(end_date)
        except Exception as err:
            return json.dumps({"error": f"Invalid date format: {err}"})

        loc_id = location_id or default_location_id
        holidays_map = employee_service.get_location_holidays_map(loc_id, s_date.year)
        breakdown = leave_service.employee_service.get_location_holidays_map(loc_id, s_date.year)
        from app.domain.working_days import calculate_working_days
        res = calculate_working_days(s_date, e_date, holidays_map)
        return json.dumps({
            "start_date": str(res.start_date),
            "end_date": str(res.end_date),
            "calendar_days": res.calendar_days,
            "weekend_days": res.weekend_days,
            "holiday_days": res.holiday_days,
            "working_days": res.working_days,
        })

    @tool
    def validate_leave_request(
        start_date: str,
        end_date: str,
        leave_type_code: Optional[str] = "ANNUAL",
        leave_type_id: Optional[str] = None,
    ) -> str:
        """
        Performs full deterministic pre-validation of a proposed leave request against
        balances, policies, notice periods, weekends, holidays, team overlaps, and approval routing.
        """
        try:
            s_date = datetime.date.fromisoformat(start_date)
            e_date = datetime.date.fromisoformat(end_date)
        except Exception as err:
            return json.dumps({"error": f"Invalid date format: {err}"})

        lt_id = leave_type_id
        if not lt_id:
            # Look up by code
            lt = db.query(LeaveType).filter(LeaveType.code == leave_type_code).first()
            if not lt:
                lt = db.query(LeaveType).first()
            lt_id = lt.id if lt else ""

        if not lt_id:
            return json.dumps({"error": "Leave type not found"})

        try:
            val_result = leave_service.pre_validate(
                employee_id=current_employee_id,
                leave_type_id=lt_id,
                start_date=s_date,
                end_date=e_date,
            )
            return json.dumps({
                "is_valid": val_result.is_valid,
                "working_days": val_result.working_days,
                "calendar_days": val_result.calendar_days,
                "weekend_days": val_result.weekend_days,
                "holiday_days": val_result.holiday_days,
                "available_balance_before": val_result.available_balance_before,
                "available_balance_after": val_result.available_balance_after,
                "has_overlapping_request": val_result.has_overlapping_request,
                "policy_violations": val_result.policy_violations,
                "warnings": val_result.warnings,
                "approval_route": val_result.approval_route,
            })
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @tool
    def get_approval_workflow(working_days: float) -> str:
        """Retrieves the authoritative approval routing tiers for a specified number of working days."""
        emp = employee_service.get_employee_by_id(current_employee_id)
        if not emp:
            return json.dumps({"route": ["Manager"]})
        approvers = leave_service._resolve_approver_details(emp)
        workflows = leave_service._get_approval_workflows_list()
        from app.domain.workflow_engine import determine_approval_chain
        chain = determine_approval_chain(
            working_days=working_days,
            workflows=workflows,
            employee_manager_id=approvers["manager_id"],
            employee_manager_name=approvers["manager_name"],
            employee_manager_email=approvers["manager_email"],
            dept_head_id=approvers["dept_head_id"],
            dept_head_name=approvers["dept_head_name"],
            dept_head_email=approvers["dept_head_email"],
            hr_lead_id=approvers["hr_lead_id"],
            hr_lead_name=approvers["hr_lead_name"],
            hr_lead_email=approvers["hr_lead_email"],
        )
        return json.dumps([{"step_order": s.step_order, "role": s.required_role.value, "approver": s.approver_name} for s in chain])

    return [
        get_employee_profile,
        get_leave_balance,
        get_leave_types,
        get_leave_policies,
        get_holidays,
        calculate_leave_days,
        validate_leave_request,
        get_approval_workflow,
    ]
