"""Authentication & session schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserLoginRequest(BaseModel):
    """Login payload — ``identifier`` is either the email or the CPR number."""

    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # "user" | "admin"
    must_change_password: bool = False


class ProfileSetupRequest(BaseModel):
    """First-login profile activation: name, email and new password."""

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)