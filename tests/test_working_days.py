import datetime
import pytest
from app.domain.working_days import calculate_working_days


def test_working_days_standard_workweek():
    # Monday 2026-08-17 to Friday 2026-08-21 (5 calendar days, 0 weekends)
    start = datetime.date(2026, 8, 17)
    end = datetime.date(2026, 8, 21)
    res = calculate_working_days(start, end, {})

    assert res.calendar_days == 5
    assert res.weekend_days == 0
    assert res.holiday_days == 0
    assert res.working_days == 5.0


def test_working_days_with_weekends_and_holidays():
    # Thursday 2026-08-20 to Tuesday 2026-08-25 (6 calendar days: Thu, Fri, Sat, Sun, Mon, Tue)
    # Sat(22) & Sun(23) are weekends (2 weekend days)
    # Fri(21) is a declared holiday (1 holiday day)
    # Net working days: Thu(20), Mon(24), Tue(25) = 3 working days
    start = datetime.date(2026, 8, 20)
    end = datetime.date(2026, 8, 25)
    holidays = {datetime.date(2026, 8, 21): "Regional Festival"}

    res = calculate_working_days(start, end, holidays)

    assert res.calendar_days == 6
    assert res.weekend_days == 2
    assert res.holiday_days == 1
    assert res.working_days == 3.0
    assert len(res.details) == 6


def test_working_days_holiday_on_weekend_no_double_deduction():
    # Saturday 2026-08-15 to Sunday 2026-08-16 (2 calendar days)
    # 2026-08-15 is Independence Day AND a Saturday
    start = datetime.date(2026, 8, 15)
    end = datetime.date(2026, 8, 16)
    holidays = {datetime.date(2026, 8, 15): "Independence Day"}

    res = calculate_working_days(start, end, holidays)

    assert res.calendar_days == 2
    assert res.weekend_days == 2
    assert res.holiday_days == 0  # Counted under weekend to prevent double subtraction
    assert res.working_days == 0.0


def test_invalid_date_order():
    start = datetime.date(2026, 8, 25)
    end = datetime.date(2026, 8, 20)
    with pytest.raises(ValueError):
        calculate_working_days(start, end, {})
