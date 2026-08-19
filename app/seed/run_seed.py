import datetime
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.models.organization import Location, Department, Team, HolidayCalendar, Holiday
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
    init_db()
    db: Session = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).count() > 0:
            print("Database already contains data, checking bootstrap HR Admin...")
            ensure_bootstrap_admin(db)
            return

        print("Seeding database with enterprise HR dataset & organizational hierarchy...")

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

        # 4. Teams (Multi-team per department)
        team_platform = Team(name="Platform & Cloud Architecture", code="ENG-PLAT", department_id=dept_eng.id, description="Cloud infrastructure, DevOps and reliability")
        team_core = Team(name="Core Backend Services", code="ENG-CORE", department_id=dept_eng.id, description="Core business logic and API services")
        team_web = Team(name="Web Applications", code="ENG-WEB", department_id=dept_eng.id, description="Frontend interfaces and design systems")
        team_people = Team(name="People Operations", code="HR-OPS", department_id=dept_hr.id, description="Employee experience and policy governance")
        team_finance = Team(name="Financial Strategy", code="FIN-OPS", department_id=dept_fin.id, description="Financial planning and accounting")
        db.add_all([team_platform, team_core, team_web, team_people, team_finance])
        db.flush()

        # 5. Leave Types
        lt_annual = LeaveType(name="Annual Leave (PTO)", code="ANNUAL", is_paid=True, color_code="#4f46e5", description="Earned annual vacation quota")
        lt_casual = LeaveType(name="Casual Leave", code="CASUAL", is_paid=True, color_code="#059669", description="Short personal leaves and contingencies")
        lt_sick = LeaveType(name="Sick Leave", code="SICK", is_paid=True, color_code="#d97706", description="Medical ailments and health recovery")
        lt_parental = LeaveType(name="Parental Leave", code="PARENTAL", is_paid=True, color_code="#db2777", description="Maternity and paternity benefits")
        db.add_all([lt_annual, lt_casual, lt_sick, lt_parental])
        db.flush()

        # 6. Policies (Distinct per location)
        policies = [
            # Chennai policies
            LeavePolicy(leave_type_id=lt_annual.id, location_id=loc_chennai.id, max_consecutive_days=10, advance_notice_days=3, carry_forward_limit=5.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_casual.id, location_id=loc_chennai.id, max_consecutive_days=3, advance_notice_days=1, carry_forward_limit=0.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_sick.id, location_id=loc_chennai.id, max_consecutive_days=10, requires_document_after_days=2, advance_notice_days=0, carry_forward_limit=5.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_parental.id, location_id=loc_chennai.id, max_consecutive_days=90, advance_notice_days=30, carry_forward_limit=0.0, allow_negative_balance=False),
            # Bangalore policies
            LeavePolicy(leave_type_id=lt_annual.id, location_id=loc_bangalore.id, max_consecutive_days=12, advance_notice_days=2, carry_forward_limit=8.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_casual.id, location_id=loc_bangalore.id, max_consecutive_days=3, advance_notice_days=1, carry_forward_limit=0.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_sick.id, location_id=loc_bangalore.id, max_consecutive_days=12, requires_document_after_days=2, advance_notice_days=0, carry_forward_limit=8.0, allow_negative_balance=False),
            LeavePolicy(leave_type_id=lt_parental.id, location_id=loc_bangalore.id, max_consecutive_days=90, advance_notice_days=30, carry_forward_limit=0.0, allow_negative_balance=False),
        ]
        db.add_all(policies)

        # 6b. Accrual Policies (Annual baseline entitlements per location)
        accrual_policies = [
            # Chennai
            AccrualPolicy(leave_type_id=lt_annual.id, location_id=loc_chennai.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=18.0, max_carry_forward=5.0),
            AccrualPolicy(leave_type_id=lt_casual.id, location_id=loc_chennai.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=12.0, max_carry_forward=0.0),
            AccrualPolicy(leave_type_id=lt_sick.id, location_id=loc_chennai.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=12.0, max_carry_forward=2.0),
            AccrualPolicy(leave_type_id=lt_parental.id, location_id=loc_chennai.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=90.0, max_carry_forward=0.0),
            # Bangalore
            AccrualPolicy(leave_type_id=lt_annual.id, location_id=loc_bangalore.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=18.0, max_carry_forward=5.0),
            AccrualPolicy(leave_type_id=lt_casual.id, location_id=loc_bangalore.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=12.0, max_carry_forward=0.0),
            AccrualPolicy(leave_type_id=lt_sick.id, location_id=loc_bangalore.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=12.0, max_carry_forward=2.0),
            AccrualPolicy(leave_type_id=lt_parental.id, location_id=loc_bangalore.id, frequency=AccrualFrequency.YEARLY, annual_entitlement=90.0, max_carry_forward=0.0),
        ]
        db.add_all(accrual_policies)

        # 7. Approval Workflows
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

        # 8. Bootstrap HR Admin
        admin_pwd_hash = get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD)
        u_admin = User(
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            password_hash=admin_pwd_hash,
            role=UserRole.HR_ADMIN,
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(u_admin)
        db.flush()
        emp_admin = Employee(
            user_id=u_admin.id,
            employee_code="EMP-BOOT-001",
            first_name="Bootstrap",
            last_name="HR Admin",
            email=u_admin.email,
            department_id=dept_hr.id,
            team_id=team_people.id,
            location_id=loc_bangalore.id,
            designation="Principal HR Administrator",
            hire_date=datetime.date(2020, 1, 1),
        )
        db.add(emp_admin)
        db.flush()
        team_people.manager_id = emp_admin.id

        # 9. Enterprise Users & Employees
        default_pwd_hash = get_password_hash("password123")

        # Sarah Jenkins (HR Lead)
        u_sarah = User(
            email="sarah.jenkins@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.HR_ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(u_sarah)
        db.flush()
        emp_sarah = Employee(
            user_id=u_sarah.id,
            employee_code="EMP-1001",
            first_name="Sarah",
            last_name="Jenkins",
            email=u_sarah.email,
            department_id=dept_hr.id,
            team_id=team_people.id,
            location_id=loc_bangalore.id,
            primary_manager_id=emp_admin.id,
            designation="Head of People & Culture",
            hire_date=datetime.date(2022, 3, 1),
            avatar_url="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_sarah)
        db.flush()

        # Ananya Deshmukh (VP of Engineering / Platform Manager)
        u_ananya = User(
            email="ananya.deshmukh@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.MANAGER,
            status=UserStatus.ACTIVE,
        )
        db.add(u_ananya)
        db.flush()
        emp_ananya = Employee(
            user_id=u_ananya.id,
            employee_code="EMP-1002",
            first_name="Ananya",
            last_name="Deshmukh",
            email=u_ananya.email,
            department_id=dept_eng.id,
            team_id=team_platform.id,
            location_id=loc_bangalore.id,
            designation="VP of Engineering & Platform Lead",
            hire_date=datetime.date(2021, 6, 15),
            avatar_url="https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_ananya)
        db.flush()
        team_platform.manager_id = emp_ananya.id

        # Suresh Ramanathan (VP of Engineering & Chennai Head / Dept Head)
        u_suresh = User(
            email="chennai.depthead@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.MANAGER,
            status=UserStatus.ACTIVE,
        )
        db.add(u_suresh)
        db.flush()
        emp_suresh = Employee(
            user_id=u_suresh.id,
            employee_code="EMP-CHN-DH01",
            first_name="Suresh",
            last_name="Ramanathan",
            email=u_suresh.email,
            department_id=dept_eng.id,
            team_id=team_core.id,
            location_id=loc_chennai.id,
            designation="VP of Engineering & Chennai Centre Head",
            hire_date=datetime.date(2019, 6, 1),
            avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_suresh)
        db.flush()

        # Kavitha Raman (Chennai HR Operations Lead / HR Admin)
        u_kavitha = User(
            email="chennai.hr@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.HR_ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(u_kavitha)
        db.flush()
        emp_kavitha = Employee(
            user_id=u_kavitha.id,
            employee_code="EMP-CHN-HR01",
            first_name="Kavitha",
            last_name="Raman",
            email=u_kavitha.email,
            department_id=dept_hr.id,
            team_id=team_people.id,
            location_id=loc_chennai.id,
            designation="Chennai HR Operations Lead",
            hire_date=datetime.date(2022, 3, 1),
            avatar_url="https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_kavitha)
        db.flush()

        # Rajesh Nair (Core Services Engineering Manager - Chennai)
        u_rajesh = User(
            email="rajesh.nair@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.MANAGER,
            status=UserStatus.ACTIVE,
        )
        db.add(u_rajesh)
        db.flush()
        emp_rajesh = Employee(
            user_id=u_rajesh.id,
            employee_code="EMP-1003",
            first_name="Rajesh",
            last_name="Nair",
            email=u_rajesh.email,
            department_id=dept_eng.id,
            team_id=team_core.id,
            location_id=loc_chennai.id,
            primary_manager_id=emp_suresh.id,
            manager_id=emp_suresh.id,
            designation="Core Services Engineering Manager",
            hire_date=datetime.date(2022, 8, 1),
            avatar_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_rajesh)
        db.flush()
        team_core.manager_id = emp_rajesh.id

        # Arun Kumar (Software Engineer II - Core Team Chennai)
        u_arun = User(
            email="arun.kumar@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.EMPLOYEE,
            status=UserStatus.ACTIVE,
        )
        db.add(u_arun)
        db.flush()
        emp_arun = Employee(
            user_id=u_arun.id,
            employee_code="EMP-1004",
            first_name="Arun",
            last_name="Kumar",
            email=u_arun.email,
            department_id=dept_eng.id,
            team_id=team_core.id,
            location_id=loc_chennai.id,
            primary_manager_id=emp_rajesh.id,
            manager_id=emp_rajesh.id,
            designation="Software Engineer II",
            hire_date=datetime.date(2023, 4, 10),
            avatar_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_arun)
        db.flush()

        # Priya Sharma (Senior Engineer - Platform Team Bangalore)
        u_priya = User(
            email="priya.sharma@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.EMPLOYEE,
            status=UserStatus.ACTIVE,
        )
        db.add(u_priya)
        db.flush()
        emp_priya = Employee(
            user_id=u_priya.id,
            employee_code="EMP-1005",
            first_name="Priya",
            last_name="Sharma",
            email=u_priya.email,
            department_id=dept_eng.id,
            team_id=team_platform.id,
            location_id=loc_bangalore.id,
            primary_manager_id=emp_ananya.id,
            manager_id=emp_ananya.id,
            designation="Senior Platform Engineer",
            hire_date=datetime.date(2023, 1, 15),
            avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_priya)
        db.flush()

        # Karthik Venkat (DevOps Engineer - Core Team Chennai)
        u_karthik = User(
            email="karthik.v@company.com",
            password_hash=default_pwd_hash,
            role=UserRole.EMPLOYEE,
            status=UserStatus.ACTIVE,
        )
        db.add(u_karthik)
        db.flush()
        emp_karthik = Employee(
            user_id=u_karthik.id,
            employee_code="EMP-1006",
            first_name="Karthik",
            last_name="Venkat",
            email=u_karthik.email,
            department_id=dept_eng.id,
            team_id=team_core.id,
            location_id=loc_chennai.id,
            primary_manager_id=emp_rajesh.id,
            manager_id=emp_rajesh.id,
            designation="DevOps Engineer",
            hire_date=datetime.date(2023, 9, 1),
            avatar_url="https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&auto=format&fit=crop&q=80",
        )
        db.add(emp_karthik)
        db.flush()

        # 10. Employee Accruals (2026)
        all_emps = [emp_admin, emp_sarah, emp_ananya, emp_suresh, emp_kavitha, emp_rajesh, emp_arun, emp_priya, emp_karthik]
        accruals = []
        for emp in all_emps:
            accruals.extend([
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_annual.id, year=2026, annual_entitlement=18.0, carried_over=3.0, manual_adjustments=0.0),
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_casual.id, year=2026, annual_entitlement=12.0, carried_over=0.0, manual_adjustments=0.0),
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_sick.id, year=2026, annual_entitlement=10.0, carried_over=2.0, manual_adjustments=0.0),
                EmployeeAccrual(employee_id=emp.id, leave_type_id=lt_parental.id, year=2026, annual_entitlement=0.0, carried_over=0.0, manual_adjustments=0.0),
            ])
        db.add_all(accruals)
        db.flush()

        # 11. Historical & Pending Requests
        # Request 1: Arun Kumar - Pending Annual Leave (Sep 7 to Sep 11, 2026 = 5 working days)
        req_arun = LeaveRequest(
            employee_id=emp_arun.id,
            leave_type_id=lt_annual.id,
            start_date=datetime.date(2026, 9, 7),
            end_date=datetime.date(2026, 9, 11),
            calendar_days=5.0,
            working_days=5.0,
            weekend_days=0.0,
            holiday_days=0.0,
            status=LeaveRequestStatus.PENDING,
            reason="Annual family vacation and rest",
        )
        db.add(req_arun)
        db.flush()

        step1 = ApprovalStep(
            leave_request_id=req_arun.id,
            step_order=1,
            required_role="MANAGER",
            approver_id=emp_rajesh.id,
            status=ApprovalStepStatus.PENDING,
        )
        step2 = ApprovalStep(
            leave_request_id=req_arun.id,
            step_order=2,
            required_role="DEPT_HEAD",
            approver_id=emp_ananya.id,
            status=ApprovalStepStatus.PENDING,
        )
        db.add_all([step1, step2])

        # Request 2: Karthik Venkat - Approved Sick Leave (Feb 2 to Feb 3, 2026 = 2 days)
        req_karthik = LeaveRequest(
            employee_id=emp_karthik.id,
            leave_type_id=lt_sick.id,
            start_date=datetime.date(2026, 2, 2),
            end_date=datetime.date(2026, 2, 3),
            calendar_days=2.0,
            working_days=2.0,
            weekend_days=0.0,
            holiday_days=0.0,
            status=LeaveRequestStatus.APPROVED,
            reason="Severe viral fever and rest under physician advice",
        )
        db.add(req_karthik)
        db.flush()

        step_karthik = ApprovalStep(
            leave_request_id=req_karthik.id,
            step_order=1,
            required_role="MANAGER",
            approver_id=emp_rajesh.id,
            status=ApprovalStepStatus.APPROVED,
            comments="Approved. Get well soon.",
            actioned_at=datetime.datetime(2026, 2, 2, 9, 30, tzinfo=datetime.timezone.utc),
        )
        db.add(step_karthik)

        # 12. Notifications
        notif_arun = Notification(
            user_id=u_arun.id,
            title="Leave Request Submitted",
            message="Your leave request for 5 working days (Sep 7 – Sep 11) is routed to Rajesh Nair for Step 1 approval.",
        )
        notif_rajesh = Notification(
            user_id=u_rajesh.id,
            title="New Approval Pending",
            message="Arun Kumar submitted a request for 5 working days (Sep 7 – Sep 11) requiring your review.",
        )
        db.add_all([notif_arun, notif_rajesh])

        db.commit()
        print("Database seeded successfully!")
        print(f"Bootstrap HR Admin: {settings.BOOTSTRAP_ADMIN_EMAIL} / {settings.BOOTSTRAP_ADMIN_PASSWORD}")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


def ensure_bootstrap_admin(db: Session):
    admin_exists = db.query(User).filter(User.role == UserRole.HR_ADMIN).first()
    if not admin_exists:
        print(f"Creating bootstrap HR Admin ({settings.BOOTSTRAP_ADMIN_EMAIL})...")
        dept_hr = db.query(Department).filter(Department.code == "HR").first()
        loc = db.query(Location).first()
        admin_pwd_hash = get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD)
        u_admin = User(
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            password_hash=admin_pwd_hash,
            role=UserRole.HR_ADMIN,
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(u_admin)
        db.flush()
        emp_admin = Employee(
            user_id=u_admin.id,
            employee_code="EMP-BOOT-001",
            first_name="Bootstrap",
            last_name="HR Admin",
            email=u_admin.email,
            department_id=dept_hr.id if dept_hr else None,
            location_id=loc.id if loc else None,
            designation="Principal HR Administrator",
            hire_date=datetime.date.today(),
        )
        db.add(emp_admin)
        db.commit()
        print(f"Bootstrap HR Admin created: {settings.BOOTSTRAP_ADMIN_EMAIL}")


check_and_seed = seed_database

if __name__ == "__main__":
    seed_database()
