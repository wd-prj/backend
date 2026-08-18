import datetime
from typing import Dict, List, Set, Optional
from pydantic import BaseModel


class DayDetail(BaseModel):
    date: datetime.date
    day_name: str
    is_weekend: bool
    is_holiday: bool
    holiday_name: Optional[str] = None
    is_working_day: bool


class WorkingDaysBreakdown(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    calendar_days: int
    weekend_days: int
    holiday_days: int
    working_days: float
    details: List[DayDetail]


def calculate_working_days(
    start_date: datetime.date,
    end_date: datetime.date,
    holidays_map: Optional[Dict[datetime.date, str]] = None,
) -> WorkingDaysBreakdown:
    """
    Deterministically calculates the working day impact for a requested leave date range.
    Weekends (Saturday=5, Sunday=6) and recognized location holidays are excluded.
    If a holiday falls on a weekend, it is counted as a weekend day without double deducting.
    """
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    holidays = holidays_map or {}
    current = start_date
    calendar_days = 0
    weekend_days = 0
    holiday_days = 0
    working_days = 0.0
    details: List[DayDetail] = []

    while current <= end_date:
        calendar_days += 1
        day_name = current.strftime("%A")
        is_weekend = current.weekday() in (5, 6)
        holiday_name = holidays.get(current)
        is_holiday = holiday_name is not None

        if is_weekend:
            weekend_days += 1
            is_working = False
        elif is_holiday:
            holiday_days += 1
            is_working = False
        else:
            working_days += 1.0
            is_working = True

        details.append(
            DayDetail(
                date=current,
                day_name=day_name,
                is_weekend=is_weekend,
                is_holiday=is_holiday,
                holiday_name=holiday_name,
                is_working_day=is_working,
            )
        )
        current += datetime.timedelta(days=1)

    return WorkingDaysBreakdown(
        start_date=start_date,
        end_date=end_date,
        calendar_days=calendar_days,
        weekend_days=weekend_days,
        holiday_days=holiday_days,
        working_days=working_days,
        details=details,
    )
