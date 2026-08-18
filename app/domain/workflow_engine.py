from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.models.request import ApprovalRole


class WorkflowStepPlan(BaseModel):
    step_order: int
    required_role: ApprovalRole
    approver_employee_id: str
    approver_name: str
    approver_email: str
    description: str


def determine_approval_chain(
    working_days: float,
    workflows: List[Dict[str, Any]],
    employee_manager_id: Optional[str],
    employee_manager_name: Optional[str],
    employee_manager_email: Optional[str],
    dept_head_id: Optional[str],
    dept_head_name: Optional[str],
    dept_head_email: Optional[str],
    hr_lead_id: Optional[str],
    hr_lead_name: Optional[str],
    hr_lead_email: Optional[str],
) -> List[WorkflowStepPlan]:
    """
    Evaluates configurable approval workflows matching the requested working days
    and maps them to specific approvers according to organizational hierarchy.
    """
    # Sort workflows by step_order
    sorted_rules = sorted(workflows, key=lambda w: w.get("step_order", 1))

    # Filter applicable workflows for the given duration
    applicable_steps = []
    for rule in sorted_rules:
        min_days = rule.get("min_working_days", 0.0)
        max_days = rule.get("max_working_days")

        if working_days >= min_days and (max_days is None or working_days <= max_days):
            applicable_steps.append(rule)

    # Fallback to standard 1-step manager if no matching rule
    if not applicable_steps:
        applicable_steps = [
            {
                "step_order": 1,
                "required_role": ApprovalRole.MANAGER,
                "description": "Standard Direct Manager Approval",
            }
        ]

    chain: List[WorkflowStepPlan] = []
    order = 1

    for step in applicable_steps:
        role = step["required_role"]
        desc = step.get("description", f"{role} Approval")

        if role == ApprovalRole.MANAGER:
            if employee_manager_id:
                chain.append(
                    WorkflowStepPlan(
                        step_order=order,
                        required_role=ApprovalRole.MANAGER,
                        approver_employee_id=employee_manager_id,
                        approver_name=employee_manager_name or "Direct Manager",
                        approver_email=employee_manager_email or "",
                        description=desc,
                    )
                )
                order += 1
            elif dept_head_id:  # If no direct manager, escalate to dept head
                chain.append(
                    WorkflowStepPlan(
                        step_order=order,
                        required_role=ApprovalRole.DEPT_HEAD,
                        approver_employee_id=dept_head_id,
                        approver_name=dept_head_name or "Department Head",
                        approver_email=dept_head_email or "",
                        description=desc,
                    )
                )
                order += 1
        elif role == ApprovalRole.DEPT_HEAD:
            if dept_head_id and dept_head_id != employee_manager_id:
                chain.append(
                    WorkflowStepPlan(
                        step_order=order,
                        required_role=ApprovalRole.DEPT_HEAD,
                        approver_employee_id=dept_head_id,
                        approver_name=dept_head_name or "Department Head",
                        approver_email=dept_head_email or "",
                        description=desc,
                    )
                )
                order += 1
        elif role == ApprovalRole.HR_ADMIN:
            if hr_lead_id:
                chain.append(
                    WorkflowStepPlan(
                        step_order=order,
                        required_role=ApprovalRole.HR_ADMIN,
                        approver_employee_id=hr_lead_id,
                        approver_name=hr_lead_name or "HR Administrator",
                        approver_email=hr_lead_email or "",
                        description=desc,
                    )
                )
                order += 1

    return chain
