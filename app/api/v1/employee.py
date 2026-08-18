from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_employee
from app.models.employee import Employee
from app.services.employee_service import EmployeeService
from app.schemas.employee import EmployeeProfileOut, HolidayOut, LocationOut, DepartmentOut
from app.schemas.leave import LeaveBalanceOut

router = APIRouter(prefix="/employee", tags=["Employee"])


@router.get("/profile", response_model=EmployeeProfileOut)
def get_my_profile(
    current_employee: Employee = Depends(get_current_employee),
):
    return EmployeeProfileOut(
        id=current_employee.id,
        user_id=current_employee.user_id,
        employee_code=current_employee.employee_code,
        first_name=current_employee.first_name,
        last_name=current_employee.last_name,
        full_name=current_employee.full_name,
        email=current_employee.email,
        role=current_employee.user.role,
        designation=current_employee.designation,
        hire_date=current_employee.hire_date,
        is_active=current_employee.is_active,
        avatar_url=current_employee.avatar_url,
        department=DepartmentOut(
            id=current_employee.department.id,
            name=current_employee.department.name,
            code=current_employee.department.code,
            description=current_employee.department.description,
        ),
        location=LocationOut(
            id=current_employee.location.id,
            name=current_employee.location.name,
            country=current_employee.location.country,
            timezone=current_employee.location.timezone,
            description=current_employee.location.description,
        ),
        manager_name=current_employee.manager.full_name if current_employee.manager else None,
        manager_id=current_employee.manager_id,
    )


@router.get("/balances", response_model=List[LeaveBalanceOut])
def get_my_balances(
    year: Optional[int] = Query(None, description="Calendar year for balances"),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)
    return service.get_employee_balances(current_employee.id, year)


@router.get("/holidays", response_model=List[HolidayOut])
def get_my_location_holidays(
    year: Optional[int] = Query(None, description="Calendar year for holidays"),
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)
    holidays = service.get_location_holidays_list(current_employee.location_id, year)
    return [
        HolidayOut(
            id=h.id,
            name=h.name,
            date=h.date,
            is_mandatory=h.is_mandatory,
            description=h.description,
        )
        for h in holidays
    ]


@router.get("/team", response_model=List[EmployeeProfileOut])
def get_my_team_members(
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    peers = (
        db.query(Employee)
        .filter(
            Employee.department_id == current_employee.department_id,
            Employee.location_id == current_employee.location_id,
            Employee.is_active == True,
        )
        .all()
    )

    return [
        EmployeeProfileOut(
            id=e.id,
            user_id=e.user_id,
            employee_code=e.employee_code,
            first_name=e.first_name,
            last_name=e.last_name,
            full_name=e.full_name,
            email=e.email,
            role=e.user.role,
            designation=e.designation,
            hire_date=e.hire_date,
            is_active=e.is_active,
            avatar_url=e.avatar_url,
            department=DepartmentOut(id=e.department.id, name=e.department.name, code=e.department.code),
            location=LocationOut(id=e.location.id, name=e.location.name, country=e.location.country, timezone=e.location.timezone),
            manager_name=e.manager.full_name if e.manager else None,
            manager_id=e.manager_id,
        )
        for e in peers
    ]
