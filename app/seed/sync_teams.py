import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.models.organization import Department, Team, Location
from app.models.employee import Employee


def sync_teams_and_bootstrap():
    db: Session = SessionLocal()
    try:
        # 1. Ensure Bootstrap HR Admin
        admin_user = db.query(User).filter(User.email == settings.BOOTSTRAP_ADMIN_EMAIL).first()
        dept_hr = db.query(Department).filter(Department.code == "HR").first()
        dept_eng = db.query(Department).filter(Department.code == "ENG").first()
        dept_fin = db.query(Department).filter(Department.code == "FIN").first()
        loc_bangalore = db.query(Location).filter(Location.name == "Bangalore").first() or db.query(Location).first()

        if not admin_user:
            admin_pwd_hash = get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD)
            admin_user = User(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                password_hash=admin_pwd_hash,
                role=UserRole.HR_ADMIN,
                status=UserStatus.ACTIVE,
                is_active=True,
            )
            db.add(admin_user)
            db.flush()
            emp_admin = Employee(
                user_id=admin_user.id,
                employee_code="EMP-BOOT-001",
                first_name="Bootstrap",
                last_name="HR Admin",
                email=admin_user.email,
                department_id=dept_hr.id if dept_hr else None,
                location_id=loc_bangalore.id if loc_bangalore else None,
                designation="Principal HR Administrator",
                hire_date=datetime.date(2020, 1, 1),
            )
            db.add(emp_admin)
            db.flush()
            print(f"Created bootstrap HR Admin: {settings.BOOTSTRAP_ADMIN_EMAIL}")

        # 2. Teams
        if dept_eng:
            team_platform = db.query(Team).filter(Team.code == "ENG-PLAT").first()
            if not team_platform:
                team_platform = Team(
                    name="Platform & Cloud Architecture",
                    code="ENG-PLAT",
                    department_id=dept_eng.id,
                    description="Cloud infrastructure, DevOps and reliability",
                )
                db.add(team_platform)

            team_core = db.query(Team).filter(Team.code == "ENG-CORE").first()
            if not team_core:
                team_core = Team(
                    name="Core Backend Services",
                    code="ENG-CORE",
                    department_id=dept_eng.id,
                    description="Core business logic and API services",
                )
                db.add(team_core)

            team_web = db.query(Team).filter(Team.code == "ENG-WEB").first()
            if not team_web:
                team_web = Team(
                    name="Web Applications",
                    code="ENG-WEB",
                    department_id=dept_eng.id,
                    description="Frontend interfaces and design systems",
                )
                db.add(team_web)

        if dept_hr:
            team_people = db.query(Team).filter(Team.code == "HR-OPS").first()
            if not team_people:
                team_people = Team(
                    name="People Operations",
                    code="HR-OPS",
                    department_id=dept_hr.id,
                    description="Employee experience and policy governance",
                )
                db.add(team_people)

        if dept_fin:
            team_fin = db.query(Team).filter(Team.code == "FIN-OPS").first()
            if not team_fin:
                team_fin = Team(
                    name="Financial Strategy",
                    code="FIN-OPS",
                    department_id=dept_fin.id,
                    description="Financial planning and accounting",
                )
                db.add(team_fin)

        db.flush()

        # Link Managers to Teams
        emp_ananya = db.query(Employee).filter(Employee.email == "ananya.deshmukh@company.com").first()
        emp_rajesh = db.query(Employee).filter(Employee.email == "rajesh.nair@company.com").first()
        emp_sarah = db.query(Employee).filter(Employee.email == "sarah.jenkins@company.com").first()
        emp_arun = db.query(Employee).filter(Employee.email == "arun.kumar@company.com").first()
        emp_priya = db.query(Employee).filter(Employee.email == "priya.sharma@company.com").first()
        emp_karthik = db.query(Employee).filter(Employee.email == "karthik.v@company.com").first()

        t_platform = db.query(Team).filter(Team.code == "ENG-PLAT").first()
        t_core = db.query(Team).filter(Team.code == "ENG-CORE").first()
        t_people = db.query(Team).filter(Team.code == "HR-OPS").first()

        if t_platform and emp_ananya:
            t_platform.manager_id = emp_ananya.id
            emp_ananya.team_id = t_platform.id
            if emp_priya:
                emp_priya.team_id = t_platform.id
                emp_priya.primary_manager_id = emp_ananya.id

        if t_core and emp_rajesh:
            t_core.manager_id = emp_rajesh.id
            emp_rajesh.team_id = t_core.id
            emp_rajesh.primary_manager_id = emp_ananya.id if emp_ananya else None
            if emp_arun:
                emp_arun.team_id = t_core.id
                emp_arun.primary_manager_id = emp_rajesh.id
            if emp_karthik:
                emp_karthik.team_id = t_core.id
                emp_karthik.primary_manager_id = emp_rajesh.id

        if t_people and emp_sarah:
            t_people.manager_id = emp_sarah.id
            emp_sarah.team_id = t_people.id

        # Update all users to ACTIVE status
        users = db.query(User).all()
        for u in users:
            if not u.status:
                u.status = UserStatus.ACTIVE

        db.commit()
        print("Teams and hierarchy synchronized successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error syncing: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    sync_teams_and_bootstrap()
