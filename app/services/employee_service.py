import datetime
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session, joinedload
from app.models.employee import Employee
from app.models.organization import Location, Department, HolidayCalendar, Holiday
from app.models.leave import LeaveType, LeavePolicy, EmployeeAccrual
from app.models.request import LeaveRequest, LeaveRequestStatus
from app.domain.balance_engine import compute_dynamic_balance, LeaveBalanceSummary
from app.domain.working_days import calculate_working_days, WorkingDaysBreakdown


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db

    def get_employee_by_id(self, employee_id: str) -> Optional[Employee]:
        return (
            self.db.query(Employee)
            .options(
                joinedload(Employee.department),
                joinedload(Employee.location),
                joinedload(Employee.manager),
                joinedload(Employee.user),
            )
            .filter(Employee.id == employee_id, Employee.is_active == True)
            .first()
        )

    def get_location_holidays_map(self, location_id: str, year: Optional[int] = None) -> Dict[datetime.date, str]:
        target_year = year or datetime.date.today().year
        holidays = (
            self.db.query(Holiday)
            .join(HolidayCalendar)
            .filter(
                HolidayCalendar.location_id == location_id,
                HolidayCalendar.year == target_year,
            )
            .all()
        )
        return {h.date: h.name for h in holidays}

    def get_location_holidays_list(self, location_id: str, year: Optional[int] = None) -> List[Holiday]:
        target_year = year or datetime.date.today().year
        return (
            self.db.query(Holiday)
            .join(HolidayCalendar)
            .filter(
                HolidayCalendar.location_id == location_id,
                HolidayCalendar.year == target_year,
            )
            .order_by(Holiday.date.asc())
            .all()
        )

    def get_employee_balances(self, employee_id: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        target_year = year or datetime.date.today().year
        employee = self.get_employee_by_id(employee_id)
        if not employee:
            return []

        # Fetch all active leave types
        leave_types = self.db.query(LeaveType).filter(LeaveType.is_active == True).all()

        # Fetch employee accruals for target year
        accruals = (
            self.db.query(EmployeeAccrual)
            .filter(
                EmployeeAccrual.employee_id == employee_id,
                EmployeeAccrual.year == target_year,
            )
            .all()
        )
        accrual_map = {a.leave_type_id: a for a in accruals}

        # Fetch all leave requests in the current year
        year_start = datetime.date(target_year, 1, 1)
        year_end = datetime.date(target_year, 12, 31)

        requests = (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.start_date >= year_start,
                LeaveRequest.start_date <= year_end,
                LeaveRequest.status.in_([LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING]),
            )
            .all()
        )

        # Aggregate used and pending days per leave type
        approved_map: Dict[str, float] = {}
        pending_map: Dict[str, float] = {}
        for req in requests:
            lt_id = req.leave_type_id
            if req.status == LeaveRequestStatus.APPROVED:
                approved_map[lt_id] = approved_map.get(lt_id, 0.0) + req.working_days
            elif req.status == LeaveRequestStatus.PENDING:
                pending_map[lt_id] = pending_map.get(lt_id, 0.0) + req.working_days

        balance_summaries = []
        for lt in leave_types:
            acc = accrual_map.get(lt.id)
            annual_entitlement = acc.annual_entitlement if acc else 0.0
            carried_over = acc.carried_over if acc else 0.0
            manual_adjustments = acc.manual_adjustments if acc else 0.0

            approved_days = approved_map.get(lt.id, 0.0)
            pending_days = pending_map.get(lt.id, 0.0)

            summary = compute_dynamic_balance(
                leave_type_id=lt.id,
                leave_type_name=lt.name,
                leave_type_code=lt.code,
                annual_entitlement=annual_entitlement,
                carried_over=carried_over,
                manual_adjustments=manual_adjustments,
                approved_working_days=approved_days,
                pending_working_days=pending_days,
            )

            balance_summaries.append({
                **summary.model_dump(),
                "color_code": lt.color_code,
            })

        return balance_summaries

    def get_single_balance(self, employee_id: str, leave_type_id: str, year: Optional[int] = None) -> LeaveBalanceSummary:
        balances = self.get_employee_balances(employee_id, year)
        for b in balances:
            if b["leave_type_id"] == leave_type_id:
                return LeaveBalanceSummary(**b)

        # Fallback empty
        return LeaveBalanceSummary(
            leave_type_id=leave_type_id,
            leave_type_name="Unknown",
            leave_type_code="UNKNOWN",
            annual_entitlement=0.0,
            carried_over=0.0,
            manual_adjustments=0.0,
            total_accrued=0.0,
            approved_used=0.0,
            pending_reserved=0.0,
            available_balance=0.0,
        )
