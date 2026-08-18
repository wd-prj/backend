from typing import Optional, Generator
from fastapi import Depends, HTTPException, status, Request, Cookie
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.models.employee import Employee


def get_token_from_request(
    request: Request,
    wtf_session: Optional[str] = Cookie(None),
) -> Optional[str]:
    # Check HTTP-only cookie first
    if wtf_session:
        return wtf_session

    # Check Authorization header fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_token_from_request),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = (
        db.query(User)
        .options(
            joinedload(User.employee).joinedload(Employee.department),
            joinedload(User.employee).joinedload(Employee.location),
            joinedload(User.employee).joinedload(Employee.manager),
        )
        .filter(User.id == user_id, User.is_active == True)
        .first()
    )
    if not user:
        raise credentials_exception

    return user


def get_current_employee(
    current_user: User = Depends(get_current_user),
) -> Employee:
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for this user account.",
        )
    return current_user.employee


def require_role(*allowed_roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles {[r.value for r in allowed_roles]}.",
            )
        return current_user

    return role_checker
