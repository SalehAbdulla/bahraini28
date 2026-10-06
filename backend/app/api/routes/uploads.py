"""Public upload serving — business logos only.

Logos are meant to be public: the directory and partner pages load them
straight from ``/uploads/<file>``. Invoice receipts share the same directory but
are **not** public — ``GET /uploads/<file>`` answers 404 for anything no partner
uses as a logo, so a leaked receipt URL is inert. Receipts are served to admins
only, from ``/api/v1/admin/receipts/<file>`` (see ``routes/admin.py``).

This replaces a blanket ``StaticFiles`` mount of ``UPLOAD_DIR``: a mount cannot
tell a logo from a receipt, so it would have made every receipt world-readable.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession
from app.models import Business
from app.services.uploads import safe_upload_name

router = APIRouter(tags=["Uploads"])


def _not_found() -> HTTPException:
    """A fresh 404 — reusing one instance would accumulate tracebacks."""
    return HTTPException(status_code=404, detail="Not found")


@router.get("/uploads/{filename}", include_in_schema=False)
def serve_logo(filename: str, db: DbSession, settings: AppSettings):
    """Serve a business logo, and *only* a business logo."""
    name = safe_upload_name(filename)
    if name is None:
        raise _not_found()

    # A file is public only while some partner references it as their logo;
    # a receipt (same directory) has no such row, so it stays private.
    logo_path = f"/uploads/{name}"
    if db.scalar(select(Business.id).where(Business.logo_path == logo_path)) is None:
        raise _not_found()

    path = Path(settings.UPLOAD_DIR) / name
    if not path.is_file():
        raise _not_found()
    # The URL carries a random suffix, so it is safe to cache at the edge.
    return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})
