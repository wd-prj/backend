import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from app.models.employee import Employee
from app.models.organization import Location, Department
from app.models.leave import LeaveType, EmployeeAccrual
from app.models.request import LeaveRequest, LeaveRequestStatus
from app.schemas.intelligence import (
    WorkforceIntelligenceOverview,
    DepartmentLeaveStat,
    LocationLeaveStat,
    LeaveTypeDistribution,
    UpcomingAbsenceItem,
    CoverageRiskAlert,
)


class IntelligenceService:
    def __init__(self, db: Session):
        self.db = db

    def get_overview(self) -> WorkforceIntelligenceOverview:
        today = datetime.date.today()
        year = today.year

        # 1. Total employees
        total_employees = self.db.query(Employee).filter(Employee.is_active == True).count()

        # 2. Currently on leave today
        on_leave_today_count = (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
            )
            .count()
        )

        # 3. Pending approvals count
        pending_count = (
            self.db.query(LeaveRequest)
            .filter(LeaveRequest.status == LeaveRequestStatus.PENDING)
            .count()
        )

        # 4. Department stats
        departments = self.db.query(Department).all()
        dept_stats: List[DepartmentLeaveStat] = []

        for dept in departments:
            emp_count = self.db.query(Employee).filter(Employee.department_id == dept.id, Employee.is_active == True).count()
            
            # Active absences
            active_absences = (
                self.db.query(LeaveRequest)
                .join(Employee, LeaveRequest.employee_id == Employee.id)
                .filter(
                    Employee.department_id == dept.id,
                    LeaveRequest.status == LeaveRequestStatus.APPROVED,
                    LeaveRequest.start_date <= today,
                    LeaveRequest.end_date >= today,
                )
                .count()
            )

            # Total days taken in current year
            dept_requests = (
                self.db.query(LeaveRequest)
                .join(Employee, LeaveRequest.employee_id == Employee.id)
                .filter(
                    Employee.department_id == dept.id,
                    LeaveRequest.status == LeaveRequestStatus.APPROVED,
                    LeaveRequest.start_date >= datetime.date(year, 1, 1),
                    LeaveRequest.start_date <= datetime.date(year, 12, 31),
                )
                .all()
            )
            total_days = sum(r.working_days for r in dept_requests)
            
            # Total annual accrued for department employees
            dept_accruals = (
                self.db.query(EmployeeAccrual)
                .join(Employee, EmployeeAccrual.employee_id == Employee.id)
                .filter(
                    Employee.department_id == dept.id,
                    EmployeeAccrual.year == year,
                )
                .all()
            )
            total_accrued = sum(a.annual_entitlement + a.carried_over for a in dept_accruals) or 1.0
            utilization = round((total_days / total_accrued) * 100, 1)

            dept_stats.append(
                DepartmentLeaveStat(
                    department_id=dept.id,
                    department_name=dept.name,
                    total_employees=emp_count,
                    active_absences=active_absences,
                    utilization_rate=utilization,
                    total_days_taken=total_days,
                )
            )

        # 5. Location stats
        locations = self.db.query(Location).all()
        loc_stats: List[LocationLeaveStat] = []

        for loc in locations:
            emp_count = self.db.query(Employee).filter(Employee.location_id == loc.id, Employee.is_active == True).count()
            active_absences = (
                self.db.query(LeaveRequest)
                .join(Employee, LeaveRequest.employee_id == Employee.id)
                .filter(
                    Employee.location_id == loc.id,
                    LeaveRequest.status == LeaveRequestStatus.APPROVED,
                    LeaveRequest.start_date <= today,
                    LeaveRequest.end_date >= today,
                )
                .count()
            )
            loc_requests = (
                self.db.query(LeaveRequest)
                .join(Employee, LeaveRequest.employee_id == Employee.id)
                .filter(
                    Employee.location_id == loc.id,
                    LeaveRequest.status == LeaveRequestStatus.APPROVED,
                    LeaveRequest.start_date >= datetime.date(year, 1, 1),
                    LeaveRequest.start_date <= datetime.date(year, 12, 31),
                )
                .all()
            )
            total_days = sum(r.working_days for r in loc_requests)

            loc_stats.append(
                LocationLeaveStat(
                    location_id=loc.id,
                    location_name=loc.name,
                    total_employees=emp_count,
                    active_absences=active_absences,
                    total_days_taken=total_days,
                )
            )

        # 6. Leave type distribution
        leave_types = self.db.query(LeaveType).filter(LeaveType.is_active == True).all()
        distribution: List[LeaveTypeDistribution] = []
        for lt in leave_types:
            type_requests = (
                self.db.query(LeaveRequest)
                .filter(
                    LeaveRequest.leave_type_id == lt.id,
                    LeaveRequest.status == LeaveRequestStatus.APPROVED,
                    LeaveRequest.start_date >= datetime.date(year, 1, 1),
                    LeaveRequest.start_date <= datetime.date(year, 12, 31),
                )
                .all()
            )
            distribution.append(
                LeaveTypeDistribution(
                    leave_type_name=lt.name,
                    color_code=lt.color_code,
                    total_requests=len(type_requests),
                    total_working_days=sum(r.working_days for r in type_requests),
                )
            )

        # 7. Upcoming absences (next 30 days)
        future_limit = today + datetime.timedelta(days=30)
        upcoming_reqs = (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.employee).joinedload(Employee.department),
                joinedload(LeaveRequest.employee).joinedload(Employee.location),
                joinedload(LeaveRequest.leave_type),
            )
            .filter(
                LeaveRequest.status.in_([LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING]),
                LeaveRequest.end_date >= today,
                LeaveRequest.start_date <= future_limit,
            )
            .order_by(LeaveRequest.start_date.asc())
            .all()
        )

        upcoming_absences = [
            UpcomingAbsenceItem(
                id=r.id,
                employee_name=r.employee.full_name,
                employee_email=r.employee.email,
                designation=r.employee.designation,
                department_name=r.employee.department.name,
                location_name=r.employee.location.name,
                leave_type_name=r.leave_type.name,
                leave_type_color=r.leave_type.color_code,
                start_date=r.start_date,
                end_date=r.end_date,
                working_days=r.working_days,
                status=r.status.value,
            )
            for r in upcoming_reqs
        ]

        # 8. Coverage risk alerts (scan department clusters)
        risk_alerts: List[CoverageRiskAlert] = []
        for dept in departments:
            dept_emp_count = self.db.query(Employee).filter(Employee.department_id == dept.id, Employee.is_active == True).count()
            if dept_emp_count == 0:
                continue

            dept_upcoming = [u for u in upcoming_absences if u.department_name == dept.name]
            # Check overlap clusters
            for i, u1 in enumerate(dept_upcoming):
                overlapping = [
                    u2 for j, u2 in enumerate(dept_upcoming)
                    if j > i and max(u1.start_date, u2.start_date) <= min(u1.end_date, u2.end_date)
                ]
                if overlapping:
                    concurrent = len(overlapping) + 1
                    pct = round((concurrent / dept_emp_count) * 100, 1)
                    if pct >= 25.0:
                        risk_level = "HIGH" if pct >= 40.0 else "MEDIUM"
                        risk_alerts.append(
                            CoverageRiskAlert(
                                department_name=dept.name,
                                location_name=u1.location_name,
                                start_date=max(u1.start_date, overlapping[0].start_date),
                                end_date=min(u1.end_date, overlapping[0].end_date),
                                absent_count=concurrent,
                                team_size=dept_emp_count,
                                absence_percentage=pct,
                                risk_level=risk_level,
                                message=f"{concurrent} out of {dept_emp_count} members ({pct}%) in {dept.name} are scheduled to be away simultaneously.",
                            )
                        )

        # Average annual leave utilization
        avg_utilization = round(sum(d.utilization_rate for d in dept_stats) / max(1, len(dept_stats)), 1)

        return WorkforceIntelligenceOverview(
            total_employees=total_employees,
            currently_on_leave=on_leave_today_count,
            pending_approvals_count=pending_count,
            avg_annual_leave_utilization=avg_utilization,
            department_stats=dept_stats,
            location_stats=loc_stats,
            leave_type_distribution=distribution,
            upcoming_absences=upcoming_absences,
            coverage_risk_alerts=risk_alerts,
        )
