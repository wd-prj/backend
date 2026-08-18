import pytest
from app.domain.workflow_engine import determine_approval_chain
from app.models.request import ApprovalRole


def test_approval_workflow_short_absence():
    workflows = [
        {"min_working_days": 1.0, "max_working_days": 2.0, "step_order": 1, "required_role": ApprovalRole.MANAGER},
        {"min_working_days": 3.0, "max_working_days": 5.0, "step_order": 1, "required_role": ApprovalRole.MANAGER},
        {"min_working_days": 3.0, "max_working_days": 5.0, "step_order": 2, "required_role": ApprovalRole.DEPT_HEAD},
        {"min_working_days": 6.0, "max_working_days": None, "step_order": 1, "required_role": ApprovalRole.MANAGER},
        {"min_working_days": 6.0, "max_working_days": None, "step_order": 2, "required_role": ApprovalRole.DEPT_HEAD},
        {"min_working_days": 6.0, "max_working_days": None, "step_order": 3, "required_role": ApprovalRole.HR_ADMIN},
    ]

    # 2 working days -> Manager only
    chain = determine_approval_chain(
        working_days=2.0,
        workflows=workflows,
        employee_manager_id="mgr_1",
        employee_manager_name="Rajesh Nair",
        employee_manager_email="rajesh@company.com",
        dept_head_id="vp_1",
        dept_head_name="Ananya Deshmukh",
        dept_head_email="ananya@company.com",
        hr_lead_id="hr_1",
        hr_lead_name="Sarah Jenkins",
        hr_lead_email="sarah@company.com",
    )
    assert len(chain) == 1
    assert chain[0].required_role == ApprovalRole.MANAGER
    assert chain[0].approver_name == "Rajesh Nair"


def test_approval_workflow_medium_absence():
    workflows = [
        {"min_working_days": 1.0, "max_working_days": 2.0, "step_order": 1, "required_role": ApprovalRole.MANAGER},
        {"min_working_days": 3.0, "max_working_days": 5.0, "step_order": 1, "required_role": ApprovalRole.MANAGER},
        {"min_working_days": 3.0, "max_working_days": 5.0, "step_order": 2, "required_role": ApprovalRole.DEPT_HEAD},
    ]

    # 4 working days -> Manager -> Dept Head
    chain = determine_approval_chain(
        working_days=4.0,
        workflows=workflows,
        employee_manager_id="mgr_1",
        employee_manager_name="Rajesh Nair",
        employee_manager_email="rajesh@company.com",
        dept_head_id="vp_1",
        dept_head_name="Ananya Deshmukh",
        dept_head_email="ananya@company.com",
        hr_lead_id="hr_1",
        hr_lead_name="Sarah Jenkins",
        hr_lead_email="sarah@company.com",
    )
    assert len(chain) == 2
    assert chain[0].required_role == ApprovalRole.MANAGER
    assert chain[1].required_role == ApprovalRole.DEPT_HEAD


def test_approval_workflow_extended_absence():
    workflows = [
        {"min_working_days": 6.0, "max_working_days": None, "step_order": 1, "required_role": ApprovalRole.MANAGER},
        {"min_working_days": 6.0, "max_working_days": None, "step_order": 2, "required_role": ApprovalRole.DEPT_HEAD},
        {"min_working_days": 6.0, "max_working_days": None, "step_order": 3, "required_role": ApprovalRole.HR_ADMIN},
    ]

    # 10 working days -> Manager -> Dept Head -> HR
    chain = determine_approval_chain(
        working_days=10.0,
        workflows=workflows,
        employee_manager_id="mgr_1",
        employee_manager_name="Rajesh Nair",
        employee_manager_email="rajesh@company.com",
        dept_head_id="vp_1",
        dept_head_name="Ananya Deshmukh",
        dept_head_email="ananya@company.com",
        hr_lead_id="hr_1",
        hr_lead_name="Sarah Jenkins",
        hr_lead_email="sarah@company.com",
    )
    assert len(chain) == 3
    assert chain[0].required_role == ApprovalRole.MANAGER
    assert chain[1].required_role == ApprovalRole.DEPT_HEAD
    assert chain[2].required_role == ApprovalRole.HR_ADMIN
