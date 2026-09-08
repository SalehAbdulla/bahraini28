"""Real-time admin notification feed via Server-Sent Events (SSE).

Browser ``EventSource`` cannot attach an ``Authorization`` header, so the
admin JWT is passed as a ``_token`` query parameter (short-lived session
tokens; use HTTPS in production). If a standard ``Authorization: Bearer``
header is present it takes precedence.
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_admin
from app.core.errors import NotAuthenticatedError
from app.db.session import get_db
from app.models import Admin
from app.services.notifications import bus

router = APIRouter(prefix="/admin/notifications", tags=["Admin", "Notifications"])


def get_sse_admin(
    _token: str | None = Query(default=None, description="Admin JWT"),
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> Admin:
    """Resolve the admin from either the Authorization header or ``_token``."""
    token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif _token:
        token = _token
    if not token:
        raise NotAuthenticatedError
    return get_current_admin(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        db=db,
    )


@router.get("/stream", response_class=StreamingResponse)
async def notification_stream(
    admin: Annotated[Admin, Depends(get_sse_admin)],
):
    """SSE stream that pushes purchase alerts to connected admin dashboards.

    Emits ``event: purchase`` payloads in real time. The server sends a
    keep-alive comment every 15s of silence so proxies don't drop the
    connection.
    """

    async def event_generator():
        queue = await bus.subscribe()
        await bus.on_connect_greeting(queue)
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )