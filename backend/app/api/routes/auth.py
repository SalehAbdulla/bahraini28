"""Authentication routes: user login, admin login, profile activation,
password change and logout.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AdminLoginRequest,
    PasswordChangeRequest,
    ProfileSetupRequest,
    TokenResponse,
    UserLoginRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def user_login(payload: UserLoginRequest, db: DbSession):
    """Login for volunteers.

    ``identifier`` accepts either the email address or the CPR number.
    Successful login bumps ``token_version`` (single-session enforcement) and
    returns a fresh token. ``must_change_password`` is ``True`` for accounts
    that still need to complete the first-login profile activation.
    """
    user = auth_service.authenticate_and_login_user(
        db, identifier=payload.identifier, password=payload.password
    )
    return TokenResponse(
        access_token=auth_service.issue_user_token(user),
        role="user",
        must_change_password=user.must_change_password,
    )


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(payload: AdminLoginRequest, db: DbSession):
    """Login for administrators (username + password). Admins are exempt from
    single-session enforcement."""
    admin = auth_service.login_admin(db, username=payload.username, password=payload.password)
    return TokenResponse(
        access_token=auth_service.issue_admin_token(admin),
        role="admin",
        must_change_password=False,
    )


@router.post("/activate-profile", response_model=TokenResponse)
def activate_profile(payload: ProfileSetupRequest, user: CurrentUser, db: DbSession):
    """First-login profile activation.

    Forces the volunteer to set their real name, email and a new password
    before using the portal. Clears the ``must_change_password`` flag.
    """
    auth_service.activate_profile(
        db,
        user=user,
        name=payload.name,
        email=str(payload.email),
        new_password=payload.password,
    )
    return TokenResponse(
        access_token=auth_service.issue_user_token(user),
        role="user",
        must_change_password=False,
    )


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Change the current user's password (requires the current one)."""
    auth_service.change_password(
        db,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


@router.post("/logout", status_code=204)
def logout(user: CurrentUser, db: DbSession):
    """Invalidate all of the user's sessions (single-session)."""
    auth_service.force_logout(db, user)