import datetime
from typing import List, Optional
from pydantic import BaseModel


class DepartmentLeaveStat(BaseModel):
    department_id: str
    department_name: str
    total_employees: int
    active_absences: int
    utilization_rate: float
    total_days_taken: float


class LocationLeaveStat(BaseModel):
    location_id: str
    location_name: str
    total_employees: int
    active_absences: int
    total_days_taken: float


class LeaveTypeDistribution(BaseModel):
    leave_type_name: str
    color_code: str
    total_requests: int
    total_working_days: float


class UpcomingAbsenceItem(BaseModel):
    id: str
    employee_name: str
    employee_email: str
    designation: str
    department_name: str
    location_name: str
    leave_type_name: str
    leave_type_color: str
    start_date: datetime.date
    end_date: datetime.date
    working_days: float
    status: str


class CoverageRiskAlert(BaseModel):
    department_name: str
    location_name: str
    start_date: datetime.date
    end_date: datetime.date
    absent_count: int
    team_size: int
    absence_percentage: float
    risk_level: str
    message: str


class WorkforceIntelligenceOverview(BaseModel):
    total_employees: int
    currently_on_leave: int
    pending_approvals_count: int
    avg_annual_leave_utilization: float
    department_stats: List[DepartmentLeaveStat]
    location_stats: List[LocationLeaveStat]
    leave_type_distribution: List[LeaveTypeDistribution]
    upcoming_absences: List[UpcomingAbsenceItem]
    coverage_risk_alerts: List[CoverageRiskAlert]
