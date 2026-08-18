import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.models.employee import Employee
from app.models.request import (
    LeaveRequest,
    LeaveRequestStatus,
    ApprovalStep,
    ApprovalStepStatus,
)
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService


class ApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)
        self.audit_service = AuditService(db)

    def get_pending_approvals(self, approver_employee_id: str) -> List[ApprovalStep]:
        return (
            self.db.query(ApprovalStep)
            .join(LeaveRequest, ApprovalStep.leave_request_id == LeaveRequest.id)
            .options(
                joinedload(ApprovalStep.leave_request).joinedload(LeaveRequest.employee).joinedload(Employee.department),
                joinedload(ApprovalStep.leave_request).joinedload(LeaveRequest.employee).joinedload(Employee.location),
                joinedload(ApprovalStep.leave_request).joinedload(LeaveRequest.leave_type),
                joinedload(ApprovalStep.leave_request).joinedload(LeaveRequest.approval_steps).joinedload(ApprovalStep.approver),
            )
            .filter(
                ApprovalStep.approver_id == approver_employee_id,
                ApprovalStep.status == ApprovalStepStatus.PENDING,
                LeaveRequest.status == LeaveRequestStatus.PENDING,
            )
            .order_by(ApprovalStep.created_at.desc())
            .all()
        )

    def get_all_requests_for_manager(self, manager_employee_id: str) -> List[LeaveRequest]:
        return (
            self.db.query(LeaveRequest)
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .options(
                joinedload(LeaveRequest.employee).joinedload(Employee.department),
                joinedload(LeaveRequest.employee).joinedload(Employee.location),
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.approval_steps).joinedload(ApprovalStep.approver),
            )
            .filter(Employee.manager_id == manager_employee_id)
            .order_by(LeaveRequest.created_at.desc())
            .all()
        )

    def action_approval_step(
        self,
        step_id: str,
        approver_employee_id: str,
        action: str,  # "APPROVE" or "REJECT"
        comments: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_email: Optional[str] = None,
    ) -> LeaveRequest:
        step = (
            self.db.query(ApprovalStep)
            .options(
                joinedload(ApprovalStep.leave_request).joinedload(LeaveRequest.employee),
                joinedload(ApprovalStep.leave_request).joinedload(LeaveRequest.approval_steps),
            )
            .filter(ApprovalStep.id == step_id)
            .first()
        )
        if not step:
            raise HTTPException(status_code=404, detail="Approval step not found")

        if step.approver_id != approver_employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to action this approval step.",
            )

        if step.status != ApprovalStepStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This approval step is already in {step.status.value} status.",
            )

        leave_req = step.leave_request
        if leave_req.status != LeaveRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave request is already {leave_req.status.value}.",
            )

        now = datetime.datetime.now(datetime.timezone.utc)

        if action == "APPROVE":
            step.status = ApprovalStepStatus.APPROVED
            step.comments = comments
            step.actioned_at = now

            # Check if there is a next pending step
            all_steps = sorted(leave_req.approval_steps, key=lambda s: s.step_order)
            current_order = step.step_order
            next_steps = [s for s in all_steps if s.step_order > current_order and s.status == ApprovalStepStatus.PENDING]

            if next_steps:
                # Still requires next tier approval
                next_step = next_steps[0]
                next_approver = self.db.query(Employee).filter(Employee.id == next_step.approver_id).first()
                if next_approver:
                    self.notification_service.create_notification(
                        user_id=next_approver.user_id,
                        title="Leave Request Requires Your Next-Tier Approval",
                        message=f"{leave_req.employee.full_name}'s request for {leave_req.working_days} working days was approved by previous tier and now requires your review.",
                        notification_type="APPROVAL_REQUIRED",
                        link_url="/approvals",
                    )
            else:
                # All steps approved -> mark LeaveRequest as APPROVED
                leave_req.status = LeaveRequestStatus.APPROVED

                # Notify employee
                self.notification_service.create_notification(
                    user_id=leave_req.employee.user_id,
                    title="Leave Request Approved!",
                    message=f"Your leave request from {leave_req.start_date} to {leave_req.end_date} ({leave_req.working_days} working days) has been fully approved.",
                    notification_type="REQUEST_APPROVED",
                    link_url="/requests",
                )

            # Audit log
            self.audit_service.log_event(
                action="LEAVE_APPROVE",
                entity_type="LEAVE_REQUEST",
                entity_id=leave_req.id,
                actor_id=actor_user_id,
                actor_email=actor_email,
                previous_state={"status": "PENDING", "step_order": step.step_order},
                new_state={"status": leave_req.status.value, "step_status": "APPROVED", "comments": comments},
            )

        elif action == "REJECT":
            step.status = ApprovalStepStatus.REJECTED
            step.comments = comments
            step.actioned_at = now

            # Skip any subsequent steps
            all_steps = sorted(leave_req.approval_steps, key=lambda s: s.step_order)
            for s in all_steps:
                if s.step_order > step.step_order and s.status == ApprovalStepStatus.PENDING:
                    s.status = ApprovalStepStatus.SKIPPED

            leave_req.status = LeaveRequestStatus.REJECTED
            leave_req.rejection_reason = comments or "Rejected by approver."

            # Notify employee
            self.notification_service.create_notification(
                user_id=leave_req.employee.user_id,
                title="Leave Request Rejected",
                message=f"Your leave request for {leave_req.working_days} days was rejected. Reason: {comments or 'No reason provided'}",
                notification_type="REQUEST_REJECTED",
                link_url="/requests",
            )

            # Audit log
            self.audit_service.log_event(
                action="LEAVE_REJECT",
                entity_type="LEAVE_REQUEST",
                entity_id=leave_req.id,
                actor_id=actor_user_id,
                actor_email=actor_email,
                previous_state={"status": "PENDING", "step_order": step.step_order},
                new_state={"status": "REJECTED", "comments": comments},
            )

        self.db.commit()
        self.db.refresh(leave_req)
        return leave_req
