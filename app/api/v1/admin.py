import datetime
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.employee import Employee
from app.models.organization import Location, Department
from app.models.leave import LeaveType, LeavePolicy, AccrualPolicy, EmployeeAccrual, AccrualFrequency
from app.services.audit_service import AuditService
from app.schemas.admin import (
    CreateLeaveTypeRequest,
    UpdateLeaveTypeRequest,
    UpdateAccrualPolicyRequest,
    UpdateLeavePolicyRequest,
    AdjustBalanceRequest,
    FullLeaveTypeConfiguration,
    AccrualPolicyDetail,
    LeavePolicyDetail,
    LeaveConfigOverview,
)

router = APIRouter(prefix="/admin", tags=["Admin, Policies & Audit"])


class AuditLogOut(BaseModel := type("AuditLogOut", (), {})):
    pass

from pydantic import BaseModel


class AuditLogOutput(BaseModel):
    id: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    previous_state: Optional[Any] = None
    new_state: Optional[Any] = None
    ai_rationale: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime.datetime


# =========================================================================
# 1. Full Leave & Accrual Configuration Overview
# =========================================================================

@router.get("/leave-configurations", response_model=LeaveConfigOverview)
def get_leave_configurations(
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieves all leave types, location accrual policies, and rule policies for HR Admins."""
    leave_types = db.query(LeaveType).order_by(LeaveType.created_at.asc()).all()
    locations = db.query(Location).order_by(Location.name.asc()).all()
    loc_map = {l.id: l.name for l in locations}

    accrual_policies = db.query(AccrualPolicy).all()
    leave_policies = db.query(LeavePolicy).all()

    configs: List[FullLeaveTypeConfiguration] = []
    for lt in leave_types:
        lt_accruals = [
            AccrualPolicyDetail(
                id=ap.id,
                location_id=ap.location_id,
                location_name=loc_map.get(ap.location_id, "All Locations"),
                frequency=ap.frequency.value,
                annual_entitlement=ap.annual_entitlement,
                max_carry_forward=ap.max_carry_forward,
            )
            for ap in accrual_policies
            if ap.leave_type_id == lt.id
        ]

        lt_policies = [
            LeavePolicyDetail(
                id=lp.id,
                location_id=lp.location_id,
                location_name=loc_map.get(lp.location_id, "All Locations"),
                max_consecutive_days=lp.max_consecutive_days,
                requires_document_after_days=lp.requires_document_after_days,
                advance_notice_days=lp.advance_notice_days,
                carry_forward_limit=lp.carry_forward_limit,
                allow_negative_balance=lp.allow_negative_balance,
                is_active=lp.is_active,
            )
            for lp in leave_policies
            if lp.leave_type_id == lt.id
        ]

        configs.append(
            FullLeaveTypeConfiguration(
                id=lt.id,
                name=lt.name,
                code=lt.code,
                description=lt.description,
                is_paid=lt.is_paid,
                color_code=lt.color_code,
                is_active=lt.is_active,
                accrual_policies=lt_accruals,
                leave_policies=lt_policies,
            )
        )

    return LeaveConfigOverview(
        leave_types=configs,
        locations=[{"id": l.id, "name": l.name, "country": l.country} for l in locations],
    )


# =========================================================================
# 2. Create New Leave Type
# =========================================================================

@router.post("/leave-types", response_model=FullLeaveTypeConfiguration)
def create_leave_type(
    req: CreateLeaveTypeRequest,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Creates a new enterprise leave type, initializes location policies and active employee accruals."""
    audit_service = AuditService(db)
    clean_code = req.code.strip().upper()

    # Check for existing code/name
    existing = db.query(LeaveType).filter((LeaveType.code == clean_code) | (LeaveType.name == req.name.strip())).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A leave type with name '{req.name}' or code '{clean_code}' already exists.",
        )

    new_lt = LeaveType(
        name=req.name.strip(),
        code=clean_code,
        description=req.description,
        is_paid=req.is_paid,
        color_code=req.color_code,
        is_active=True,
    )
    db.add(new_lt)
    db.flush()

    locations = db.query(Location).all()
    created_accruals = []
    created_policies = []

    for loc in locations:
        ap = AccrualPolicy(
            leave_type_id=new_lt.id,
            location_id=loc.id,
            frequency=req.frequency,
            annual_entitlement=req.annual_entitlement,
            max_carry_forward=req.max_carry_forward,
        )
        db.add(ap)
        db.flush()
        created_accruals.append(
            AccrualPolicyDetail(
                id=ap.id,
                location_id=loc.id,
                location_name=loc.name,
                frequency=ap.frequency.value,
                annual_entitlement=ap.annual_entitlement,
                max_carry_forward=ap.max_carry_forward,
            )
        )

        lp = LeavePolicy(
            leave_type_id=new_lt.id,
            location_id=loc.id,
            max_consecutive_days=req.max_consecutive_days,
            advance_notice_days=req.advance_notice_days,
            requires_document_after_days=req.requires_document_after_days,
            carry_forward_limit=req.max_carry_forward,
            allow_negative_balance=req.allow_negative_balance,
            is_active=True,
        )
        db.add(lp)
        db.flush()
        created_policies.append(
            LeavePolicyDetail(
                id=lp.id,
                location_id=loc.id,
                location_name=loc.name,
                max_consecutive_days=lp.max_consecutive_days,
                requires_document_after_days=lp.requires_document_after_days,
                advance_notice_days=lp.advance_notice_days,
                carry_forward_limit=lp.carry_forward_limit,
                allow_negative_balance=lp.allow_negative_balance,
                is_active=lp.is_active,
            )
        )

    # Initialize current-year accrual record for all active employees
    current_year = datetime.datetime.now().year
    employees = db.query(Employee).all()
    for emp in employees:
        db.add(
            EmployeeAccrual(
                employee_id=emp.id,
                leave_type_id=new_lt.id,
                year=current_year,
                annual_entitlement=req.annual_entitlement,
                carried_over=0.0,
                manual_adjustments=0.0,
            )
        )

    # Audit Log
    audit_service.log_event(
        action="LEAVE_TYPE_CREATE",
        entity_type="LEAVE_TYPE",
        entity_id=new_lt.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        new_state={
            "name": new_lt.name,
            "code": new_lt.code,
            "annual_entitlement": req.annual_entitlement,
            "max_carry_forward": req.max_carry_forward,
            "frequency": req.frequency.value,
        },
    )

    db.commit()

    return FullLeaveTypeConfiguration(
        id=new_lt.id,
        name=new_lt.name,
        code=new_lt.code,
        description=new_lt.description,
        is_paid=new_lt.is_paid,
        color_code=new_lt.color_code,
        is_active=new_lt.is_active,
        accrual_policies=created_accruals,
        leave_policies=created_policies,
    )


# =========================================================================
# 3. Update Leave Type
# =========================================================================

@router.put("/leave-types/{leave_type_id}")
def update_leave_type(
    leave_type_id: str,
    req: UpdateLeaveTypeRequest,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Updates basic leave type metadata (name, description, color, active status)."""
    audit_service = AuditService(db)
    lt = db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    prev = {"name": lt.name, "description": lt.description, "is_paid": lt.is_paid, "color_code": lt.color_code, "is_active": lt.is_active}

    if req.name is not None:
        lt.name = req.name.strip()
    if req.description is not None:
        lt.description = req.description
    if req.is_paid is not None:
        lt.is_paid = req.is_paid
    if req.color_code is not None:
        lt.color_code = req.color_code
    if req.is_active is not None:
        lt.is_active = req.is_active

    audit_service.log_event(
        action="LEAVE_TYPE_UPDATE",
        entity_type="LEAVE_TYPE",
        entity_id=lt.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        previous_state=prev,
        new_state={"name": lt.name, "description": lt.description, "is_paid": lt.is_paid, "color_code": lt.color_code, "is_active": lt.is_active},
    )

    db.commit()
    return {"message": f"Leave type '{lt.name}' updated successfully."}


# =========================================================================
# 4. Update Accrual Policy (Entitlement & Carry Forward)
# =========================================================================

@router.put("/accrual-policies/{policy_id}")
def update_accrual_policy(
    policy_id: str,
    req: UpdateAccrualPolicyRequest,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Updates location-based accrual entitlement & carry forward cap, and optionally syncs active employees."""
    audit_service = AuditService(db)
    ap = db.query(AccrualPolicy).filter(AccrualPolicy.id == policy_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Accrual policy not found")

    prev = {
        "annual_entitlement": ap.annual_entitlement,
        "max_carry_forward": ap.max_carry_forward,
        "frequency": ap.frequency.value,
    }

    ap.annual_entitlement = req.annual_entitlement
    ap.max_carry_forward = req.max_carry_forward
    ap.frequency = req.frequency

    # Also update associated LeavePolicy carry_forward_limit
    lp = db.query(LeavePolicy).filter(LeavePolicy.leave_type_id == ap.leave_type_id, LeavePolicy.location_id == ap.location_id).first()
    if lp:
        lp.carry_forward_limit = req.max_carry_forward

    # Optionally synchronize active employee balances for the current year
    employees_updated = 0
    if req.sync_existing_employees:
        current_year = datetime.datetime.now().year
        emp_accruals = (
            db.query(EmployeeAccrual)
            .join(Employee, EmployeeAccrual.employee_id == Employee.id)
            .filter(
                EmployeeAccrual.leave_type_id == ap.leave_type_id,
                EmployeeAccrual.year == current_year,
                Employee.location_id == ap.location_id,
            )
            .all()
        )
        for ea in emp_accruals:
            ea.annual_entitlement = req.annual_entitlement
            employees_updated += 1

    audit_service.log_event(
        action="ACCRUAL_POLICY_UPDATE",
        entity_type="ACCRUAL_POLICY",
        entity_id=ap.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        previous_state=prev,
        new_state={
            "annual_entitlement": ap.annual_entitlement,
            "max_carry_forward": ap.max_carry_forward,
            "frequency": ap.frequency.value,
            "employees_synced": employees_updated,
        },
    )

    db.commit()
    return {
        "message": "Accrual policy updated successfully.",
        "annual_entitlement": ap.annual_entitlement,
        "max_carry_forward": ap.max_carry_forward,
        "employees_synced": employees_updated,
    }


# =========================================================================
# 5. Update Leave Policy (Notice, Limits, Document Rules)
# =========================================================================

@router.put("/leave-policies/{policy_id}")
def update_leave_policy(
    policy_id: str,
    req: UpdateLeavePolicyRequest,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Updates policy validation parameters (max consecutive days, notice period, document triggers)."""
    audit_service = AuditService(db)
    lp = db.query(LeavePolicy).filter(LeavePolicy.id == policy_id).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Leave policy not found")

    prev = {
        "max_consecutive_days": lp.max_consecutive_days,
        "advance_notice_days": lp.advance_notice_days,
        "requires_document_after_days": lp.requires_document_after_days,
        "carry_forward_limit": lp.carry_forward_limit,
        "allow_negative_balance": lp.allow_negative_balance,
    }

    lp.max_consecutive_days = req.max_consecutive_days
    lp.advance_notice_days = req.advance_notice_days
    lp.requires_document_after_days = req.requires_document_after_days
    lp.carry_forward_limit = req.carry_forward_limit
    lp.allow_negative_balance = req.allow_negative_balance

    audit_service.log_event(
        action="LEAVE_POLICY_UPDATE",
        entity_type="LEAVE_POLICY",
        entity_id=lp.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        previous_state=prev,
        new_state={
            "max_consecutive_days": lp.max_consecutive_days,
            "advance_notice_days": lp.advance_notice_days,
            "requires_document_after_days": lp.requires_document_after_days,
            "carry_forward_limit": lp.carry_forward_limit,
            "allow_negative_balance": lp.allow_negative_balance,
        },
    )

    db.commit()
    return {"message": "Leave policy rules updated successfully."}


# =========================================================================
# 6. Manual Employee Balance Adjustment (Comp-off / Bonus Days)
# =========================================================================

@router.post("/adjust-employee-balance")
def adjust_employee_balance(
    req: AdjustBalanceRequest,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Allows HR Admins to award or deduct leave balance with audit reasoning."""
    audit_service = AuditService(db)
    emp = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    lt = db.query(LeaveType).filter(LeaveType.id == req.leave_type_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Leave type not found")

    target_year = req.year or datetime.datetime.now().year

    accrual = (
        db.query(EmployeeAccrual)
        .filter(
            EmployeeAccrual.employee_id == emp.id,
            EmployeeAccrual.leave_type_id == lt.id,
            EmployeeAccrual.year == target_year,
        )
        .first()
    )

    if not accrual:
        accrual = EmployeeAccrual(
            employee_id=emp.id,
            leave_type_id=lt.id,
            year=target_year,
            annual_entitlement=0.0,
            carried_over=0.0,
            manual_adjustments=req.adjustment_days,
        )
        db.add(accrual)
    else:
        prev_adj = accrual.manual_adjustments
        accrual.manual_adjustments += req.adjustment_days

    audit_service.log_event(
        action="BALANCE_ADJUSTMENT",
        entity_type="EMPLOYEE_ACCRUAL",
        entity_id=accrual.id if accrual.id else emp.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        previous_state={"manual_adjustments": prev_adj if "prev_adj" in locals() else 0.0},
        new_state={
            "employee_id": emp.id,
            "employee_name": emp.full_name,
            "leave_type": lt.name,
            "adjustment_days": req.adjustment_days,
            "new_manual_adjustments": accrual.manual_adjustments,
            "reason": req.reason,
        },
    )

    db.commit()
    return {
        "message": f"Successfully adjusted {req.adjustment_days:+.1f} days of {lt.name} for {emp.full_name}.",
        "new_manual_adjustments": accrual.manual_adjustments,
    }


# =========================================================================
# 7. Immutable Audit Trail
# =========================================================================

@router.get("/audit-trail", response_model=List[AuditLogOutput])
def get_audit_trail(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    """Chronological immutable audit log restricted exclusively to HR Administrators."""
    service = AuditService(db)
    logs = service.get_audit_trail(entity_type=entity_type, entity_id=entity_id, limit=limit)
    return [
        AuditLogOutput(
            id=l.id,
            actor_id=l.actor_id,
            actor_email=l.actor_email,
            action=l.action,
            entity_type=l.entity_type,
            entity_id=l.entity_id,
            previous_state=l.previous_state,
            new_state=l.new_state,
            ai_rationale=l.ai_rationale,
            ip_address=l.ip_address,
            created_at=l.created_at,
        )
        for l in logs
    ]
