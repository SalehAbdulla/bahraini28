"""Domain errors mapped to HTTP responses.

Raise ``AppError`` subclasses from services/routes; a single exception
handler registered in ``app.main`` converts them into consistent JSON
responses with a machine-readable ``code``.
"""
from __future__ import annotations


class AppError(Exception):
    """Base domain error."""

    status_code: int = 400
    code: str = "app_error"
    message: str = "Request failed."

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {"detail": self.message, "code": self.code}


# --- Authentication ---------------------------------------------------------
class InvalidCredentialsError(AppError):
    status_code = 401
    code = "invalid_credentials"
    message = "Invalid login credentials."


class InvalidTokenError(AppError):
    status_code = 401
    code = "invalid_token"
    message = "Invalid or expired token."


class SessionInvalidatedError(AppError):
    status_code = 401
    code = "session_invalidated"
    message = "Session invalidated — please log in again."


class MembershipExpiredError(AppError):
    status_code = 403
    code = "membership_expired"
    message = "Your membership has expired. Please contact the organization."


class UserInactiveError(AppError):
    status_code = 403
    code = "user_inactive"
    message = "This account has been deactivated."


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "Authentication required."


# --- Users ------------------------------------------------------------------
class UserNotFoundError(AppError):
    status_code = 404
    code = "user_not_found"
    message = "User not found."


class CprConflictError(AppError):
    status_code = 409
    code = "cpr_conflict"
    message = "A user with this CPR already exists."


class EmailConflictError(AppError):
    status_code = 409
    code = "email_conflict"
    message = "A user with this email already exists."


class UsernameConflictError(AppError):
    status_code = 409
    code = "username_conflict"
    message = "An admin with this username already exists."


class PasswordTooShortError(AppError):
    status_code = 400
    code = "password_too_short"
    message = "Password must be at least 8 characters long."


# --- Businesses --------------------------------------------------------------
class BusinessNotFoundError(AppError):
    status_code = 404
    code = "business_not_found"
    message = "Business not found."


class BusinessInactiveError(AppError):
    status_code = 403
    code = "business_inactive"
    message = "This business partnership is currently inactive."


class BusinessExpiredError(AppError):
    status_code = 403
    code = "business_expired"
    message = "This business partnership has expired."


# --- Transactions --------------------------------------------------------------
class DuplicateInvoiceError(AppError):
    status_code = 409
    code = "duplicate_invoice"
    message = "This invoice number has already been submitted for this business."


class DailyLimitExceededError(AppError):
    status_code = 429
    code = "daily_limit_exceeded"
    message = "The daily usage limit for this business has been exhausted."

    remaining = 0