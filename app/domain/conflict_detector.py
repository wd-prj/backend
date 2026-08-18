import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class PeerAbsence(BaseModel):
    employee_id: str
    employee_name: str
    leave_type_name: str
    start_date: datetime.date
    end_date: datetime.date
    working_days: float
    status: str


class ConflictAnalysis(BaseModel):
    has_conflicts: bool
    conflicting_absences: List[PeerAbsence]
    team_total_members: int
    concurrent_absences_count: int
    team_absence_percentage: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    risk_summary: str


def analyze_team_conflicts(
    requester_id: str,
    start_date: datetime.date,
    end_date: datetime.date,
    team_absences: List[Dict[str, Any]],
    team_size: int,
) -> ConflictAnalysis:
    """
    Analyzes whether any team members in the same department/location have active
    (PENDING or APPROVED) leaves overlapping with the requested window.
    """
    conflicts: List[PeerAbsence] = []

    for item in team_absences:
        emp_id = item["employee_id"]
        # Skip requester themselves
        if emp_id == requester_id:
            continue

        item_start = item["start_date"]
        item_end = item["end_date"]

        # Check date overlap: max(start1, start2) <= min(end1, end2)
        if max(start_date, item_start) <= min(end_date, item_end):
            conflicts.append(
                PeerAbsence(
                    employee_id=emp_id,
                    employee_name=item["employee_name"],
                    leave_type_name=item["leave_type_name"],
                    start_date=item_start,
                    end_date=item_end,
                    working_days=item["working_days"],
                    status=item["status"],
                )
            )

    concurrent_count = len({c.employee_id for c in conflicts})
    effective_team_size = max(1, team_size)
    absence_pct = round((concurrent_count / effective_team_size) * 100, 1)

    if absence_pct >= 40.0:
        risk_level = "HIGH"
        risk_summary = f"High coverage risk: {concurrent_count} team members ({absence_pct}%) are scheduled to be absent during this period."
    elif absence_pct >= 20.0 or concurrent_count >= 1:
        risk_level = "MEDIUM"
        risk_summary = f"Moderate team overlap: {concurrent_count} team member(s) ({absence_pct}%) have scheduled leave during this window."
    else:
        risk_level = "LOW"
        risk_summary = "No significant team coverage conflicts detected."

    return ConflictAnalysis(
        has_conflicts=len(conflicts) > 0,
        conflicting_absences=conflicts,
        team_total_members=effective_team_size,
        concurrent_absences_count=concurrent_count,
        team_absence_percentage=absence_pct,
        risk_level=risk_level,
        risk_summary=risk_summary,
    )
