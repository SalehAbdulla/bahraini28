"""Single upload mechanism for the whole app.

Both the business-logo upload (admin) and the invoice-receipt upload (volunteer)
go through :func:`store_upload`, so there is exactly one place that decides
where files live, how big they may be, and which content types are allowed:

* files are written to ``settings.UPLOAD_DIR`` and served at ``/uploads/...``;
* ``settings.MAX_UPLOAD_SIZE_MB`` is enforced with the shared
  ``FileTooLargeError`` / ``UnsupportedFileTypeError`` domain errors;
* the SHA-256 of the bytes is returned so receipt images can be de-duplicated.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import FileTooLargeError, UnsupportedFileTypeError

#: Content types accepted for business logos.
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

#: Content types accepted for invoice receipts (images + PDF).
ALLOWED_RECEIPT_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def safe_upload_name(filename: str) -> str | None:
    """Return ``filename`` when it is a bare file name, else ``None``.

    Guards the upload-serving routes against path traversal: anything that is
    not a plain name (``../secrets``, an absolute path, an empty string) is
    reported as a miss so the caller can answer 404 without touching disk.
    """
    if not filename or filename in {".", ".."} or Path(filename).name != filename:
        return None
    return filename


async def store_upload(
    file: UploadFile,
    *,
    settings: Settings,
    allowed_types: dict[str, str],
    prefix: str,
    label: str = "File",
    unsupported_message: str | None = None,
) -> tuple[str, str]:
    """Persist ``file`` and return ``(public_url, sha256_hex)``.

    ``prefix`` seeds the filename (``b<id>`` for a logo, ``r<id>`` for a
    receipt) and a random suffix keeps repeated uploads distinct.
    """
    ext = allowed_types.get((file.content_type or "").lower())
    if ext is None:
        raise UnsupportedFileTypeError(message=unsupported_message)

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    payload = await file.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise FileTooLargeError(
            message=f"{label} exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit."
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}-{uuid.uuid4().hex[:12]}{ext}"
    (upload_dir / filename).write_bytes(payload)

    return f"/uploads/{filename}", hashlib.sha256(payload).hexdigest()