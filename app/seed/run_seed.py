import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.organization import Location, Department, HolidayCalendar, Holiday
from app.models.leave import LeaveType, LeavePolicy, EmployeeAccrual, AccrualPolicy, AccrualFrequency
from app.models.employee import Employee
from app.models.request import (
    LeaveRequest,
    LeaveRequestStatus,
    ApprovalWorkflow,
    ApprovalStep,
    ApprovalStepStatus,
    ApprovalRole,
)
from app.models.audit import Notification, AuditLog


def seed_database():
    db: Session = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).count() > 0:
            print("Database already contains data, skipping seed.")
            return

        print("Seeding database with enterprise HR dataset...")

        # 1. Locations
        loc_chennai = Location(
            name="Chennai",
            country="India",
            timezone="Asia/Kolkata",
            description="Chennai Development Centre, Taramani",
        )
        loc_bangalore = Location(
            name="Bangalore",
            country="India",
            timezone="Asia/Kolkata",
            description="Bangalore Corporate & R&D Hub, Indiranagar",
        )
        db.add_all([loc_chennai, loc_bangalore])
        db.flush()

        # 2. Holiday Calendars & Holidays (2026)
        cal_chennai_2026 = HolidayCalendar(location_id=loc_chennai.id, year=2026, name="Chennai 2026 Holiday Calendar")
        cal_bangalore_2026 = HolidayCalendar(location_id=loc_bangalore.id, year=2026, name="Bangalore 2026 Holiday Calendar")
        db.add_all([cal_chennai_2026, cal_bangalore_2026])
        db.flush()

        chennai_holidays = [
            Holiday(calendar_id=cal_chennai_2026.id, name="Pongal", date=datetime.date(2026, 1, 14), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Thiruvalluvar Day", date=datetime.date(2026, 1, 15), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Republic Day", date=datetime.date(2026, 1, 26), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Tamil New Year", date=datetime.date(2026, 4, 14), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="May Day", date=datetime.date(2026, 5, 1), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Independence Day", date=datetime.date(2026, 8, 15), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Location Regional Holiday", date=datetime.date(2026, 8, 21), is_mandatory=True, description="Chennai Regional Observance"),
            Holiday(calendar_id=cal_chennai_2026.id, name="Gandhi Jayanti", date=datetime.date(2026, 10, 2), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Deepavali", date=datetime.date(2026, 11, 8), is_mandatory=True),
            Holiday(calendar_id=cal_chennai_2026.id, name="Christmas", date=datetime.date(2026, 12, 25), is_mandatory=True),
        ]

        bangalore_holidays = [
            Holiday(calendar_id=cal_bangalore_2026.id, name="Makara Sankranti", date=datetime.date(2026, 1, 15), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Republic Day", date=datetime.date(2026, 1, 26), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Ugadi Festival", date=datetime.date(2026, 3, 20), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="May Day", date=datetime.date(2026, 5, 1), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Independence Day", date=datetime.date(2026, 8, 15), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Gandhi Jayanti", date=datetime.date(2026, 10, 2), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Kannada Rajyotsava", date=datetime.date(2026, 11, 1), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Deepavali", date=datetime.date(2026, 11, 8), is_mandatory=True),
            Holiday(calendar_id=cal_bangalore_2026.id, name="Christmas", date=datetime.date(2026, 12, 25), is_mandatory=True),
        ]
        db.add_all(chennai_holidays + bangalore_holidays)

        # 3. Departments
        dept_eng = Department(name="Engineering", code="ENG", description="Product, Infrastructure & Platform Engineering")
        dept_hr = Department(name="People & Culture", code="HR", description="Human Resources & Talent Management")
        dept_fin = Department(name="Finance", code="FIN", description="Finance, Payroll & Accounts")
        db.add_all([dept_eng, dept_hr, dept_fin])
        db.flush()

        # 4. Leave Types
        lt_annual = LeaveType(name="Annual Leave (PTO)", code="ANNUAL", is_paid=True, color_code="#4f46e5", description="Earned annual vacation quota")
        lt_casual = LeaveType(name="Casual Leave", code="CASUAL", is_paid=True, color_code="#059669", description="Short personal leaves and contingencies")
        lt_sick = LeaveType(name="Sick Leave", code="SICK", is_paid=True, color_code="#d97706", description="Medical ailments and health recovery")
        lt_parental = LeaveType(name="Parental Leave", code="PARENTAL", is_paid=True, color_code="#db2777", description="Maternity and paternity benefits")
        db.add_all([lt_annual, lt_casual, lt_sick, lt_parental])
        db.flush()

        # 5. Policies (Distinct per location)
        policies = [
            # Chennai policies
            LeavePolicy(leave_type_id=lt_annual.id, location_id=loc_chennai.id, max_consecutive_days=10, advance_notice_days=3, carry_forward_limit=5.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_casual.id, location_id=loc_chennai.id, max_consecutive_days=3, advance_notice_days=1, carry_forward_limit=0.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_sick.id, location_id=loc_chennai.id, max_consecutive_days=10, requires_document_after_days=2, advance_notice_days=0, carry_forward_limit=5.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_parental.id, location_id=loc_chennai.id, max_consecutive_days=90, advance_notice_days=30, carry_forward_limit=0.0, allow_negative_balance=False),
            # Bangalore policies (Subtle location differences: higher max consecutive & carry forward)
            LeavePolicy(leave_type_id=lt_annual.id, location_id=loc_bangalore.id, max_consecutive_days=12, advance_notice_days=2, carry_forward_limit=8.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_casual.id, location_id=loc_bangalore.id, max_consecutive_days=3, advance_notice_days=1, carry_forward_limit=0.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_sick.id, location_id=loc_bangalore.id, max_consecutive_days=12, requires_document_after_days=2, advance_notice_days=0, carry_forward_limit=8.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_parental.id, location_id=loc_bangalore.id, max_consecutive_days=90, advance_notice_days=30, carry_forward_limit=0.0, allow_negative_balance=False),
        ]
        db.add_all(policies)

        # 6. Approval Workflows (Configurable multi-level rules)
        workflows = [
            ApprovalWorkflow(name="Short Absence (1-2 days)", min_working_days=1.0, max_working_days=2.0, step_order=1, required_role=ApprovalRole.MANAGER, description="Direct Manager Approval"),
            ApprovalWorkflow(name="Medium Absence (3-5 days) - Step 1", min_working_days=3.0, max_working_days=5.0, step_order=1, required_role=ApprovalRole.MANAGER, description="Direct Manager Approval"),
            ApprovalWorkflow(name="Medium Absence (3-5 days) - Step 2", min_working_days=3.0, max_working_days=5.0, step_order=2, required_role=ApprovalRole.DEPT_HEAD, description="Department Head Approval"),
            ApprovalWorkflow(name="Extended Absence (>5 days) - Step 1", min_working_days=6.0, max_working_days=None, step_order=1, required_role=ApprovalRole.MANAGER, description="Direct Manager Approval"),
            ApprovalWorkflow(name="Extended Absence (>5 days) - Step 2", min_working_days=6.0, max_working_days=None, step_order=2, required_role=ApprovalRole.DEPT_HEAD, description="Department Head Approval"),
            ApprovalWorkflow(name="Extended Absence (>5 days) - Step 3", min_working_days=6.0, max_working_days=None, step_order=3, required_role=ApprovalRole.HR_ADMIN, description="HR Leadership Approval"),
        ]
        db.add_all(workflows)
        db.flush()

        # 7. Users & Employees
        default_pwd_hash = get_password_hash("password123")

        # Sarah Jenkins (HR Lead / Admin)
        u_sarah = User(email="sarah.jenkins@company.com", password_hash=default_pwd_hash, role=UserRole.HR_ADMIN)
        db.add(u_sarah)
        db.flush()
        emp_sarah = Employee(
            user_id=u_sarah.id,
            employee_code="EMP-1001",
            first_name="Sarah",
            last_name="Jenkins",
            email=u_sarah.email,
            department_id=dept_hr.id,
            location_id=loc_bangalore.id,
            designation="Head of People & Culture",
            hire_date=datetime.date(2022, 3, 1),
            avatar_url="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_sarah)
        db.flush()

        # Ananya Deshmukh (VP of Engineering)
        u_ananya = User(email="ananya.deshmukh@company.com", password_hash=default_pwd_hash, role=UserRole.MANAGER)
        db.add(u_ananya)
        db.flush()
        emp_ananya = Employee(
            user_id=u_ananya.id,
            employee_code="EMP-1002",
            first_name="Ananya",
            last_name="Deshmukh",
            email=u_ananya.email,
            department_id=dept_eng.id,
            location_id=loc_bangalore.id,
            designation="VP of Engineering",
            hire_date=datetime.date(2021, 6, 15),
            avatar_url="https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_ananya)
        db.flush()

        # Rajesh Nair (Engineering Manager - Chennai)
        u_rajesh = User(email="rajesh.nair@company.com", password_hash=default_pwd_hash, role=UserRole.MANAGER)
        db.add(u_rajesh)
        db.flush()
        emp_rajesh = Employee(
            user_id=u_rajesh.id,
            employee_code="EMP-1003",
            first_name="Rajesh",
            last_name="Nair",
            email=u_rajesh.email,
            department_id=dept_eng.id,
            location_id=loc_chennai.id,
            manager_id=emp_ananya.id,
            designation="Engineering Manager",
            hire_date=datetime.date(2022, 8, 1),
            avatar_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_rajesh)
        db.flush()

        # Arun Kumar (Software Engineer II - Chennai)
        u_arun = User(email="arun.kumar@company.com", password_hash=default_pwd_hash, role=UserRole.EMPLOYEE)
        db.add(u_arun)
        db.flush()
        emp_arun = Employee(
            user_id=u_arun.id,
            employee_code="EMP-1004",
            first_name="Arun",
            last_name="Kumar",
            email=u_arun.email,
            department_id=dept_eng.id,
            location_id=loc_chennai.id,
            manager_id=emp_rajesh.id,
            designation="Software Engineer II",
            hire_date=datetime.date(2023, 4, 10),
            avatar_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_arun)
        db.flush()

        # Priya Sharma (Senior Engineer - Bangalore)
        u_priya = User(email="priya.sharma@company.com", password_hash=default_pwd_hash, role=UserRole.EMPLOYEE)
        db.add(u_priya)
        db.flush()
        emp_priya = Employee(
            user_id=u_priya.id,
            employee_code="EMP-1005",
            first_name="Priya",
            last_name="Sharma",
            email=u_priya.email,
            department_id=dept_eng.id,
            location_id=loc_bangalore.id,
            manager_id=emp_ananya.id,
            designation="Senior Software Engineer",
            hire_date=datetime.date(2023, 1, 15),
            avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_priya)
        db.flush()

        # Karthik Venkat (Peer Engineer in Chennai for conflict testing)
        u_karthik = User(email="karthik.v@company.com", password_hash=default_pwd_hash, role=UserRole.EMPLOYEE)
        db.add(u_karthik)
        db.flush()
        emp_karthik = Employee(
            user_id=u_karthik.id,
            employee_code="EMP-1006",
            first_name="Karthik",
            last_name="Venkat",
            email=u_karthik.email,
            department_id=dept_eng.id,
            location_id=loc_chennai.id,
            manager_id=emp_rajesh.id,
            designation="DevOps Engineer",
            hire_date=datetime.date(2023, 9, 1),
            avatar_url="https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_karthik)
        db.flush()

        # 8. Employee Accruals (2026)
        all_emps = [emp_sarah, emp_ananya, emp_rajesh, emp_arun, emp_priya, emp_karthik]
        accruals = []
        for emp in all_emps:
            accruals.extend([
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_annual.id, year=2026, annual_entitlement=18.0, carried_over=3.0, manual_adjustments=0.0),
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_casual.id, year=2026, annual_entitlement=12.0, carried_over=0.0, manual_adjustments=0.0),
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_sick.id, year=2026, annual_entitlement=10.0, carried_over=2.0, manual_adjustments=0.0),
            ])
        db.add_all(accruals)
        db.flush()

        # 9. Pre-populate Sample Requests & Demonstrable Scenarios
        # Scenario A: Approved historical leave for Priya (Used days)
        req_priya_past = LeaveRequest(
            employee_id=emp_priya.id,
            leave_type_id=lt_annual.id,
            start_date=datetime.date(2026, 2, 9),
            end_date=datetime.date(2026, 2, 13),
            calendar_days=5,
            weekend_days=0,
            holiday_days=0,
            working_days=5.0,
            reason="Family gathering in hometown",
            status=LeaveRequestStatus.APPROVED,
        )
        db.add(req_priya_past)
        db.flush()

        step_priya_1 = ApprovalStep(
            leave_request_id=req_priya_past.id,
            approver_id=emp_ananya.id,
            required_role=ApprovalRole.MANAGER,
            step_order=1,
            status=ApprovalStepStatus.APPROVED,
            comments="Approved. Coverage coordinated.",
            actioned_at=datetime.datetime(2026, 2, 2, 10, 30, tzinfo=datetime.timezone.utc),
        )
        db.add(step_priya_1)

        # Scenario B: Pre-existing overlapping leave for Karthik in Chennai (triggers conflict detector during Arun's inquiry)
        req_karthik_overlap = LeaveRequest(
            employee_id=emp_karthik.id,
            leave_type_id=lt_annual.id,
            start_date=datetime.date(2026, 8, 20),
            end_date=datetime.date(2026, 8, 24),
            calendar_days=5,
            weekend_days=2,
            holiday_days=1,
            working_days=2.0,
            reason="Scheduled infrastructure maintenance downtime personal leave",
            status=LeaveRequestStatus.APPROVED,
        )
        db.add(req_karthik_overlap)
        db.flush()

        step_karthik_1 = ApprovalStep(
            leave_request_id=req_karthik_overlap.id,
            approver_id=emp_rajesh.id,
            required_role=ApprovalRole.MANAGER,
            step_order=1,
            status=ApprovalStepStatus.APPROVED,
            comments="Approved.",
            actioned_at=datetime.datetime(2026, 8, 1, 14, 0, tzinfo=datetime.timezone.utc),
        )
        db.add(step_karthik_1)

        # Scenario C: Pre-populated Pending Request for Priya requiring Ananya's approval
        req_priya_pending = LeaveRequest(
            employee_id=emp_priya.id,
            leave_type_id=lt_annual.id,
            start_date=datetime.date(2026, 9, 14),
            end_date=datetime.date(2026, 9, 18),
            calendar_days=5,
            weekend_days=0,
            holiday_days=0,
            working_days=5.0,
            reason="Attending distributed systems conference and personal vacation",
            status=LeaveRequestStatus.PENDING,
        )
        db.add(req_priya_pending)
        db.flush()

        step_priya_pending_1 = ApprovalStep(
            leave_request_id=req_priya_pending.id,
            approver_id=emp_ananya.id,
            required_role=ApprovalRole.MANAGER,
            step_order=1,
            status=ApprovalStepStatus.PENDING,
        )
        db.add(step_priya_pending_1)

        # 10. Audit Logs
        db.add_all([
            AuditLog(actor_email=u_sarah.email, action="SYSTEM_INIT", entity_type="SYSTEM", entity_id="GLOBAL", new_state={"initialized": True}),
            AuditLog(actor_email=u_priya.email, action="LEAVE_SUBMIT", entity_type="LEAVE_REQUEST", entity_id=req_priya_past.id, new_state={"status": "PENDING"}),
            AuditLog(actor_email=u_ananya.email, action="LEAVE_APPROVE", entity_type="LEAVE_REQUEST", entity_id=req_priya_past.id, previous_state={"status": "PENDING"}, new_state={"status": "APPROVED"}),
        ])

        # 11. Initial Notifications
        db.add_all([
            Notification(user_id=u_ananya.id, title="Leave Request Requires Approval", message="Priya Sharma submitted a leave request for 5 days.", type="APPROVAL_REQUIRED", link_url="/approvals"),
            Notification(user_id=u_arun.id, title="Welcome to PTO Orchestration", message="Your leave accounts for 2026 are active and ready.", type="INFO", link_url="/dashboard"),
        ])

        db.commit()
        print("Database successfully seeded with 6 employees, locations, holiday calendars, policies, and sample requests!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


def check_and_seed():
    init_db()
    seed_database()


if __name__ == "__main__":
    check_and_seed()
