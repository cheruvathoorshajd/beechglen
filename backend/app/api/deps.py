"""FastAPI dependency that resolves the application context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.context import AppContext


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]
