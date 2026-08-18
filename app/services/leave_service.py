import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.models.employee import Employee
from app.models.organization import Location, Department
from app.models.leave import LeaveType, LeavePolicy
from app.models.request import (
    LeaveRequest,
    LeaveRequestStatus,
    ApprovalStep,
    ApprovalStepStatus,
    ApprovalWorkflow,
    ApprovalRole,
)
from app.models.user import User, UserRole
from app.domain.working_days import calculate_working_days, WorkingDaysBreakdown
from app.domain.conflict_detector import analyze_team_conflicts, ConflictAnalysis
from app.domain.workflow_engine import determine_approval_chain, WorkflowStepPlan
from app.domain.policy_rules import validate_leave_request_rules, LeaveValidationResult
from app.services.employee_service import EmployeeService
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService


class LeaveService:
    def __init__(self, db: Session):
        self.db = db
        self.employee_service = EmployeeService(db)
        self.notification_service = NotificationService(db)
        self.audit_service = AuditService(db)

    def _get_active_policy(self, leave_type_id: str, location_id: str, department_id: Optional[str] = None) -> LeavePolicy:
        # Check specific department policy first, then location policy
        if department_id:
            policy = (
                self.db.query(LeavePolicy)
                .filter(
                    LeavePolicy.leave_type_id == leave_type_id,
                    LeavePolicy.location_id == location_id,
                    LeavePolicy.department_id == department_id,
                    LeavePolicy.is_active == True,
                )
                .first()
            )
            if policy:
                return policy

        policy = (
            self.db.query(LeavePolicy)
            .filter(
                LeavePolicy.leave_type_id == leave_type_id,
                LeavePolicy.location_id == location_id,
                LeavePolicy.department_id == None,
                LeavePolicy.is_active == True,
            )
            .first()
        )
        if not policy:
            # Create a default fallback policy if not seeded
            policy = LeavePolicy(
                leave_type_id=leave_type_id,
                location_id=location_id,
                max_consecutive_days=10,
                advance_notice_days=0,
                carry_forward_limit=5.0,
                allow_negative_balance=False,
            )
        return policy

    def _get_approval_workflows_list(self) -> List[Dict[str, Any]]:
        workflows = self.db.query(ApprovalWorkflow).order_by(ApprovalWorkflow.step_order.asc()).all()
        if not workflows:
            return [
                {
                    "min_working_days": 1.0,
                    "max_working_days": None,
                    "step_order": 1,
                    "required_role": ApprovalRole.MANAGER,
                    "description": "Manager Approval",
                }
            ]
        return [
            {
                "min_working_days": w.min_working_days,
                "max_working_days": w.max_working_days,
                "step_order": w.step_order,
                "required_role": w.required_role,
                "description": w.description or f"{w.required_role.value} Approval",
            }
            for w in workflows
        ]

    def _resolve_approver_details(self, employee: Employee) -> Dict[str, Any]:
        manager_id, manager_name, manager_email = None, None, None
        dept_head_id, dept_head_name, dept_head_email = None, None, None
        hr_lead_id, hr_lead_name, hr_lead_email = None, None, None

        if employee.manager:
            manager_id = employee.manager.id
            manager_name = employee.manager.full_name
            manager_email = employee.manager.email

        # Find Department Head (senior manager in the same department, e.g. VP)
        dept_head = (
            self.db.query(Employee)
            .join(User)
            .filter(
                Employee.department_id == employee.department_id,
                User.role == UserRole.MANAGER,
                Employee.id != employee.id,
            )
            .order_by(Employee.created_at.asc())
            .first()
        )
        if dept_head:
            dept_head_id = dept_head.id
            dept_head_name = dept_head.full_name
            dept_head_email = dept_head.email
        elif employee.manager:
            dept_head_id = employee.manager.id
            dept_head_name = employee.manager.full_name
            dept_head_email = employee.manager.email

        # Find HR Lead
        hr_admin_user = (
            self.db.query(User)
            .join(Employee)
            .filter(User.role == UserRole.HR_ADMIN, User.is_active == True)
            .first()
        )
        if hr_admin_user and hr_admin_user.employee:
            hr_lead_id = hr_admin_user.employee.id
            hr_lead_name = hr_admin_user.employee.full_name
            hr_lead_email = hr_admin_user.employee.email

        return {
            "manager_id": manager_id,
            "manager_name": manager_name,
            "manager_email": manager_email,
            "dept_head_id": dept_head_id,
            "dept_head_name": dept_head_name,
            "dept_head_email": dept_head_email,
            "hr_lead_id": hr_lead_id,
            "hr_lead_name": hr_lead_name,
            "hr_lead_email": hr_lead_email,
        }

    def _get_team_absences(self, department_id: str, location_id: str) -> List[Dict[str, Any]]:
        active_requests = (
            self.db.query(LeaveRequest)
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
            .filter(
                Employee.department_id == department_id,
                Employee.location_id == location_id,
                LeaveRequest.status.in_([LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING]),
            )
            .all()
        )

        return [
            {
                "employee_id": r.employee_id,
                "employee_name": r.employee.full_name,
                "leave_type_name": r.leave_type.name,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "working_days": r.working_days,
                "status": r.status.value,
            }
            for r in active_requests
        ]

    def _get_team_size(self, department_id: str, location_id: str) -> int:
        return (
            self.db.query(Employee)
            .filter(
                Employee.department_id == department_id,
                Employee.location_id == location_id,
                Employee.is_active == True,
            )
            .count()
        )

    def pre_validate(
        self,
        employee_id: str,
        leave_type_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> LeaveValidationResult:
        employee = self.employee_service.get_employee_by_id(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # 1. Holidays map
        holidays_map = self.employee_service.get_location_holidays_map(employee.location_id, start_date.year)
        breakdown = calculate_working_days(start_date, end_date, holidays_map)

        # 2. Dynamic balance
        balance_summary = self.employee_service.get_single_balance(employee_id, leave_type_id, start_date.year)

        # 3. Policy
        policy = self._get_active_policy(leave_type_id, employee.location_id, employee.department_id)

        # 4. Approver hierarchy & workflow
        approvers = self._resolve_approver_details(employee)
        workflows = self._get_approval_workflows_list()
        approval_chain = determine_approval_chain(
            working_days=breakdown.working_days,
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

        # 5. Team conflicts
        team_absences = self._get_team_absences(employee.department_id, employee.location_id)
        team_size = self._get_team_size(employee.department_id, employee.location_id)
        conflict_analysis = analyze_team_conflicts(
            requester_id=employee_id,
            start_date=start_date,
            end_date=end_date,
            team_absences=team_absences,
            team_size=team_size,
        )

        # 6. Existing employee requests
        existing = (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_([LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING]),
            )
            .all()
        )
        existing_reqs = [{"start_date": r.start_date, "end_date": r.end_date, "status": r.status.value} for r in existing]

        # 7. Execute pure rule validator
        return validate_leave_request_rules(
            start_date=start_date,
            end_date=end_date,
            working_days_breakdown=breakdown,
            balance_summary=balance_summary,
            policy_max_consecutive_days=policy.max_consecutive_days,
            policy_advance_notice_days=policy.advance_notice_days,
            policy_allow_negative_balance=policy.allow_negative_balance,
            existing_employee_requests=existing_reqs,
            approval_chain=approval_chain,
            conflict_analysis=conflict_analysis,
        )

    def submit_leave_request(
        self,
        employee_id: str,
        leave_type_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
        reason: str,
        actor_user_id: Optional[str] = None,
        actor_email: Optional[str] = None,
    ) -> LeaveRequest:
        # Pre-validate first
        validation = self.pre_validate(employee_id, leave_type_id, start_date, end_date)
        if not validation.is_valid:
            error_msg = "; ".join(validation.policy_violations)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave validation failed: {error_msg}",
            )

        employee = self.employee_service.get_employee_by_id(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Create leave request
        leave_req = LeaveRequest(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            calendar_days=validation.calendar_days,
            weekend_days=validation.weekend_days,
            holiday_days=validation.holiday_days,
            working_days=validation.working_days,
            reason=reason,
            status=LeaveRequestStatus.PENDING,
        )
        self.db.add(leave_req)
        self.db.flush()  # Generate ID

        # Generate approval steps
        first_approver_user_id = None
        for step in validation.approval_plan:
            step_record = ApprovalStep(
                leave_request_id=leave_req.id,
                approver_id=step.approver_employee_id,
                required_role=step.required_role,
                step_order=step.step_order,
                status=ApprovalStepStatus.PENDING,
            )
            self.db.add(step_record)

            if step.step_order == 1:
                # Get approver user_id for notification
                approver_emp = self.db.query(Employee).filter(Employee.id == step.approver_employee_id).first()
                if approver_emp:
                    first_approver_user_id = approver_emp.user_id

        # Audit log
        self.audit_service.log_event(
            action="LEAVE_SUBMIT",
            entity_type="LEAVE_REQUEST",
            entity_id=leave_req.id,
            actor_id=actor_user_id or employee.user_id,
            actor_email=actor_email or employee.email,
            new_state={
                "status": "PENDING",
                "working_days": validation.working_days,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "reason": reason,
                "approval_route": validation.approval_route,
            },
        )

        # Notify first approver
        if first_approver_user_id:
            self.notification_service.create_notification(
                user_id=first_approver_user_id,
                title="New Leave Request Pending Approval",
                message=f"{employee.full_name} submitted a leave request for {validation.working_days} working days ({start_date} to {end_date}).",
                notification_type="APPROVAL_REQUIRED",
                link_url="/approvals",
            )

        # Notify employee of submission
        self.notification_service.create_notification(
            user_id=employee.user_id,
            title="Leave Request Submitted",
            message=f"Your request for {validation.working_days} working days from {start_date} to {end_date} has been submitted for approval.",
            notification_type="REQUEST_SUBMITTED",
            link_url="/requests",
        )

        self.db.commit()
        self.db.refresh(leave_req)
        return leave_req

    def get_employee_requests(
        self,
        employee_id: str,
        status_filter: Optional[str] = None,
    ) -> List[LeaveRequest]:
        query = (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee).joinedload(Employee.department),
                joinedload(LeaveRequest.employee).joinedload(Employee.location),
                joinedload(LeaveRequest.approval_steps).joinedload(ApprovalStep.approver),
            )
            .filter(LeaveRequest.employee_id == employee_id)
        )

        if status_filter and status_filter != "ALL":
            query = query.filter(LeaveRequest.status == LeaveRequestStatus(status_filter))

        return query.order_by(LeaveRequest.created_at.desc()).all()

    def cancel_leave_request(self, request_id: str, employee_id: str, actor_email: str) -> LeaveRequest:
        req = (
            self.db.query(LeaveRequest)
            .filter(LeaveRequest.id == request_id, LeaveRequest.employee_id == employee_id)
            .first()
        )
        if not req:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if req.status != LeaveRequestStatus.PENDING:
            raise HTTPException(status_code=400, detail="Only PENDING leave requests can be cancelled")

        prev_status = req.status.value
        req.status = LeaveRequestStatus.CANCELLED

        self.audit_service.log_event(
            action="LEAVE_CANCEL",
            entity_type="LEAVE_REQUEST",
            entity_id=req.id,
            actor_email=actor_email,
            previous_state={"status": prev_status},
            new_state={"status": "CANCELLED"},
        )

        self.db.commit()
        self.db.refresh(req)
        return req
