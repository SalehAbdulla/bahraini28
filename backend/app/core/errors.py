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


class AdminNotFoundError(AppError):
    status_code = 404
    code = "admin_not_found"
    message = "Admin account not found."


class PasswordTooShortError(AppError):
    status_code = 400
    code = "password_too_short"
    message = "Password must be at least 8 characters long."


class InvalidCurrentPasswordError(AppError):
    """The caller *is* authenticated but supplied the wrong current password.

    Deliberately a 400 rather than a 401: the request was authorised, so the
    frontend must not treat it as an expired session and drop the token.
    """

    status_code = 400
    code = "invalid_current_password"
    message = "The current password is incorrect."


# --- Businesses --------------------------------------------------------------
class BusinessNotFoundError(AppError):
    status_code = 404
    code = "business_not_found"
    message = "Business not found."


class BusinessExistsError(AppError):
    status_code = 409
    code = "duplicate_business"
    message = "A business with this commercial registration already exists."


class CategoryNotFoundError(AppError):
    status_code = 404
    code = "category_not_found"
    message = "The selected category does not exist."


class AreaNotFoundError(AppError):
    status_code = 404
    code = "area_not_found"
    message = "One or more selected areas do not exist."


class CategoryExistsError(AppError):
    status_code = 409
    code = "duplicate_category"
    message = "A category with this name already exists."


class CategoryInUseError(AppError):
    status_code = 409
    code = "category_in_use"
    message = "This category is assigned to one or more businesses."


class AreaExistsError(AppError):
    status_code = 409
    code = "duplicate_area"
    message = "An area with this name already exists."


class AreaInUseError(AppError):
    status_code = 409
    code = "area_in_use"
    message = "This area is linked to one or more business branches."


class UnsupportedFileTypeError(AppError):
    status_code = 400
    code = "unsupported_file_type"
    message = "Unsupported file type. Use PNG, JPEG, GIF or WebP."


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"
    message = "The uploaded file is too large."


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


class TotalDailyLimitExceededError(AppError):
    status_code = 429
    code = "total_daily_limit_exceeded"
    message = "You have reached the total daily reward limit across all partners."

    remaining = 0


class InvoiceFormatError(AppError):
    status_code = 400
    code = "invalid_invoice_format"
    message = "The invoice number does not match the expected format for this partner."


class ReceiptRequiredError(AppError):
    status_code = 400
    code = "receipt_required"
    message = "Attach a photo or PDF of your receipt to submit this invoice."


class TransactionNotPendingError(AppError):
    """Raised when a review decision targets a row that is not awaiting review."""

    status_code = 409
    code = "transaction_not_pending"
    message = "This submission has already been reviewed."


class TransactionNotFoundError(AppError):
    status_code = 404
    code = "transaction_not_found"
    message = "Transaction not found."


# --- Invoice codes (anti-fraud Tier 3) -----------------------------------------
class InvoiceCodeRequiredError(AppError):
    """A partner that prints single-use codes received a submission without one."""

    status_code = 400
    code = "invoice_code_required"
    message = "This partner requires the single-use code printed on your receipt."


class InvalidInvoiceCodeError(AppError):
    """The quoted code does not exist, or belongs to a different partner."""

    status_code = 400
    code = "invalid_invoice_code"
    message = "This receipt code is not valid for this partner."


class InvoiceCodeUsedError(AppError):
    """The code is already claimed by a submission or has been redeemed."""

    status_code = 409
    code = "invoice_code_used"
    message = "This receipt code has already been used."


class InvoiceCodeNotFoundError(AppError):
    status_code = 404
    code = "invoice_code_not_found"
    message = "Receipt code not found."