import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_auth_login_and_cookie():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "arun.kumar@company.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "arun.kumar@company.com"
    assert data["role"] == "EMPLOYEE"
    assert "wtf_session" in response.cookies


def test_auth_me_endpoint():
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "arun.kumar@company.com", "password": "password123"},
    )
    cookie_val = login_res.cookies.get("wtf_session")

    me_res = client.get(
        "/api/v1/auth/me",
        cookies={"wtf_session": cookie_val},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "arun.kumar@company.com"


def test_leave_types_and_balances():
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "arun.kumar@company.com", "password": "password123"},
    )
    cookie_val = login_res.cookies.get("wtf_session")

    # Get types
    types_res = client.get("/api/v1/leave/types", cookies={"wtf_session": cookie_val})
    assert types_res.status_code == 200
    types = types_res.json()
    assert len(types) >= 3

    # Get balances
    bal_res = client.get("/api/v1/employee/balances", cookies={"wtf_session": cookie_val})
    assert bal_res.status_code == 200
    balances = bal_res.json()
    assert len(balances) >= 3
    annual_bal = next(b for b in balances if b["leave_type_code"] == "ANNUAL")
    assert annual_bal["available_balance"] > 0


def test_rbac_manager_route_protection():
    # Login as Employee Arun
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "arun.kumar@company.com", "password": "password123"},
    )
    cookie_val = login_res.cookies.get("wtf_session")

    # Try accessing manager endpoint
    mgr_res = client.get(
        "/api/v1/manager/approvals",
        cookies={"wtf_session": cookie_val},
    )
    assert mgr_res.status_code == 403
