# 🌟 ZenithHR — Enterprise Workforce Leave & PTO Orchestration Platform

> **Policy-aware, deterministic workforce leave orchestration with dynamic multi-tier approval routing, organization-controlled provisioning, and a grounded AI Leave Copilot.**

---

## 🌐 Live Production Deployments & Repositories

| Component | Live Deployment URL | Infrastructure / Host |
| :--- | :--- | :--- |
| **Frontend Web App** | [https://zenithhr-platform.netlify.app](https://zenithhr-platform.netlify.app) | **Netlify Production** |
| **Backend API Service** | [https://zenithhr-backend.onrender.com](https://zenithhr-backend.onrender.com) | **Render Web Service** (Docker / Python 3.13) |
| **API Health & Metadata** | [https://zenithhr-backend.onrender.com/health](https://zenithhr-backend.onrender.com/health) | **FastAPI Uvicorn** |
| **Managed Database** | Supabase Session Pooler (IPv4) | **Supabase PostgreSQL** |
| **Email Delivery** | `ZenithHR <onboarding@resend.dev>` | **Resend API** |
| **Frontend Repository** | [https://github.com/wd-prj/frontend](https://github.com/wd-prj/frontend) | GitHub (`main`) |
| **Backend Repository** | [https://github.com/wd-prj/backend](https://github.com/wd-prj/backend) | GitHub (`main`) |

---

## 🏛️ Architectural Architecture

```text
                  ┌────────────────────────────────────────────────────────┐
                  │          Next.js 16 Client (App Router)                │
                  │   Tailwind CSS • Untitled UI Tokens • Lucide Icons     │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                                              │ HTTPS REST + Bearer Token / Cookie Auth
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │              FastAPI REST & Auth Gateway               │
                  │             (Python 3.13 / Pydantic v2 / RBAC)         │
                  └──────────────┬──────────────────────────┬──────────────┘
                                 │                          │
                 ┌───────────────┴──────────────┐           │
                 ▼                              ▼           │
     ┌───────────────────────┐      ┌───────────────────────┐
     │ Deterministic Engine  │      │  LangGraph LeaveAgent │
     │  - Working Days Math  │      │  - Grounded Execution │
     │  - Regional Calendars │◀─────┤  - Zero Hallucination │
     │  - Dynamic Accruals   │Tools │  - Multi-Model BYOK   │
     │  - Multi-Tier Routing │      └───────────────────────┘
     │  - Coverage Overlap   │
     └───────────┬───────────┘
                 │
                 ▼
     ┌───────────────────────┐      ┌───────────────────────┐
     │  SQLAlchemy 2.0 ORM   │      │  Resend Email Engine  │
     └───────────┬───────────┘      └───────────┬───────────┘
                 │                              │
                 ▼                              ▼
     ┌───────────────────────┐      ┌───────────────────────┐
     │  Supabase PostgreSQL  │      │ 48h Invitation Tokens │
     └───────────────────────┘      └───────────────────────┘
```

---

## ⚡ Core Capabilities & Differentiators

### 1. Deterministic Calculation Engine (Zero Hallucinations)
- Automatically computes **exact working days** across multi-day ranges.
- Accurately excludes weekends and location-specific public holidays (e.g. Bangalore vs. Chennai calendars).
- Eliminates AI mathematical errors—all quotas and balances are backed by database transactions.

### 2. Multi-Tier Dynamic Approval Routing
- **1–2 Working Days:** Single Tier → Direct Manager (`MANAGER`).
- **3–5 Working Days:** Two Tiers → Direct Manager (`MANAGER`) → Department Head / VP (`DEPT_HEAD`).
- **>5 Working Days (Extended):** Three Tiers → Direct Manager → Department Head → HR Leadership (`HR_ADMIN`).
- **Self-Healing Step Deduplication:** If an employee reports directly to a Department Head, redundant duplicate steps are automatically merged.

### 3. Organization-Controlled Provisioning
- **No Public Sign-Up:** Open registration is strictly disabled.
- **Bootstrap HR Admin:** The initial organizational admin is created during database initialization (`admin@zenithhr.com`).
- **HR Admin → Manager:** HR Admins provision Department Heads & Managers.
- **Manager → Employee:** Managers provision team members within their reporting lines.
- **Secure Activation:** 48-hour single-use token invitations dispatched via **Resend** or copied with 1-click.

### 4. Grounded AI Leave Copilot
- Context-aware virtual assistant powered by LangGraph function calling.
- Directly invokes domain tools (`get_leave_balance`, `get_holidays`, `validate_leave_request`, `get_approval_workflow`).
- Capable of providing **strategic long weekend recommendations** by pairing holidays with minimal PTO days.

### 5. Compliance Audit Trail & Workforce Intelligence
- Immutable event log capturing all state transitions (`PROVISION_MANAGER_INVITED`, `USER_ACTIVATED`, `LEAVE_SUBMITTED`, `LEAVE_APPROVED`).
- Department-wide absence heatmaps and team coverage risk assessment.

---

## 🔑 Default Credentials & Personas

| Persona / Role | Email | Password | Scope & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Bootstrap HR Admin** | `admin@zenithhr.com` | `ZenithAdmin2026!` | Full enterprise administration, manager provisioning, audit log |
| **Engineering Manager** | `rajesh.nair@company.com` | `ZenithAdmin2026!` | Core Backend Services team manager, Tier-1 leave approvals |
| **VP of Engineering** | `ananya.deshmukh@company.com` | `ZenithAdmin2026!` | Platform & Engineering Lead, Tier-2 Department Head approvals |
| **Software Engineer II** | `arun.kumar@company.com` | `ZenithAdmin2026!` | Employee, leave submissions, AI Copilot, calendar |
| **Senior Platform Eng** | `priya.sharma@company.com` | `ZenithAdmin2026!` | Employee (Bangalore location) |
| **DevOps Engineer** | `karthik.v@company.com` | `ZenithAdmin2026!` | Employee (Chennai location) |

---

## 🚀 1-Click Automated Setup (Windows)

A PowerShell automation script is included in the root directory to clone both repositories, configure `.env` files, install dependencies, and start both servers concurrently.

### Run in PowerShell:

```powershell
# Run the automated setup script
.\setup_and_run.ps1
```

*What the script does automatically:*
1. Verifies Git, Python (3.11+), and Node.js (v18+) prerequisites.
2. Clones `wd-prj/backend` and `wd-prj/frontend` if not already present.
3. Generates `.env` and `.env.local` configuration templates.
4. Creates a Python virtual environment (`.venv`) and installs `requirements.txt`.
5. Installs frontend packages (`pnpm install` or `npm install`).
6. Starts the backend (port 8000) and frontend (port 3000) in concurrent terminal windows.
7. Automatically opens `http://localhost:3000` in your default browser.

---

## 🛠️ Manual Local Setup (macOS / Linux / Windows)

### Prerequisites
- **Git**
- **Python 3.11+** (or [`uv`](https://github.com/astral-sh/uv))
- **Node.js 18+** and [`pnpm`](https://pnpm.io/) (or `npm`)

---

### Step 1: Clone Repositories

```bash
# Clone Backend
git clone https://github.com/wd-prj/backend.git
cd backend

# Clone Frontend
git clone https://github.com/wd-prj/frontend.git
cd frontend
```

---

### Step 2: Backend Setup

```bash
cd backend

# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
# Or if using uv:
# uv sync

# 3. Create .env file
cp .env.example .env   # Or create .env with variables below

# 4. (Optional) Run domain tests
pytest -v

# 5. Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be running at: **`http://localhost:8000`** (Interactive Docs: `http://localhost:8000/docs`).

---

### Step 3: Frontend Setup

```bash
cd frontend

# 1. Install dependencies
pnpm install   # Or: npm install

# 2. Configure environment
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

# 3. Start Next.js development server
pnpm dev --port 3000   # Or: npm run dev
```

Frontend will be running at: **`http://localhost:3000`**.

---

## ⚙️ Environment Variables Reference

### Backend (`backend/.env`)

```ini
# =================================================================
# Database Configuration (Supabase PostgreSQL / Local Postgres)
# =================================================================
DATABASE_URL=postgresql+psycopg://postgres:your_password@your_db_host:5432/postgres

# =================================================================
# Security & JWT Authentication
# =================================================================
SECRET_KEY=zenith-enterprise-secure-jwt-production-token-2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# =================================================================
# Bootstrap HR Administrator (Created during initial DB seed)
# =================================================================
BOOTSTRAP_ADMIN_EMAIL=admin@zenithhr.com
BOOTSTRAP_ADMIN_PASSWORD=ZenithAdmin2026!

# =================================================================
# Email Delivery Service (Resend)
# =================================================================
EMAIL_PROVIDER=resend
RESEND_API_KEY=your_resend_api_key_here
EMAIL_FROM=ZenithHR <onboarding@resend.dev>
APP_URL=http://localhost:3000
INVITATION_EXPIRE_HOURS=48

# =================================================================
# AI & LLM Provider Configuration
# Set to 'mock' for local deterministic execution, or 'openai'
# =================================================================
LLM_PROVIDER=mock
LLM_MODEL=mimo-v2.5-free
LLM_BASE_URL=https://opencode.ai/zen/v1
LLM_API_KEY=
LLM_TEMPERATURE=0.0
```

### Frontend (`frontend/.env.local`)

```ini
# Local Backend API Gateway URL
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Production Backend API Gateway URL (when deployed)
# NEXT_PUBLIC_API_URL=https://zenithhr-backend.onrender.com/api/v1
```

---

## 📡 Core API Endpoints

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/v1/auth/login` | Authenticates user & issues session token |
| **Auth** | `POST` | `/api/v1/auth/logout` | Clears authentication session |
| **Auth** | `GET` | `/api/v1/auth/me` | Returns current authenticated user |
| **Auth** | `POST` | `/api/v1/auth/accept-invitation` | Validates single-use token & sets password |
| **Provisioning** | `POST` | `/api/v1/provisioning/invite-manager` | HR Admin creates manager & sends invite |
| **Provisioning** | `POST` | `/api/v1/provisioning/invite-employee` | Manager creates employee in their team |
| **Provisioning** | `POST` | `/api/v1/provisioning/resend-invite` | Generates fresh token & resends invitation |
| **Provisioning** | `GET` | `/api/v1/provisioning/members` | Returns team hierarchy and directory |
| **Leave** | `POST` | `/api/v1/leave/validate` | Deterministic pre-validation & working days calculation |
| **Leave** | `POST` | `/api/v1/leave/submit` | Submits request & initiates multi-tier approval steps |
| **Leave** | `GET` | `/api/v1/leave/my-requests` | Returns leave history and live statuses |
| **Approvals** | `GET` | `/api/v1/manager/pending-requests` | Returns requests pending caller's approval step |
| **Approvals** | `POST` | `/api/v1/manager/approvals/{step_id}/action`| Approves or rejects step with comments |
| **AI Copilot** | `POST` | `/api/v1/ai/chat` | Grounded AI assistant with domain tool verification |
| **Audit** | `GET` | `/api/v1/admin/audit-trail` | Returns chronological immutable compliance events |

---

## 🛡️ License & Compliance

© 2026 ZenithHR Technologies, Inc. All rights reserved.  
Built for enterprise workforce management, SOC 2 compliance readiness, and policy-governed leave orchestration.
