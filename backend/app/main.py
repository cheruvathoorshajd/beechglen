"""FastAPI application: routers, CORS, error mapping and the built frontend.

``create_app`` takes an optional context factory so tests can run the real
HTTP layer over a context built with fakes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import (
    routes_calls,
    routes_incidents,
    routes_leads,
    routes_links,
    routes_settings,
    routes_sim,
)
from app.config import get_settings
from app.context import AppContext
from app.flow.runner import LinkActionError
from app.graph.views import NotFoundError
from app.paths import FRONTEND_DIST_DIR
from app.realtime.bus import router as ws_router
from app.sim.replay import ScenarioNotFound

ROUTERS = (
    routes_calls.router,
    routes_incidents.router,
    routes_links.router,
    routes_leads.router,
    routes_settings.router,
    routes_sim.router,
)


def create_app(
    context_factory: Callable[[], AppContext] | None = None,
    frontend_dist: Path = FRONTEND_DIST_DIR,
) -> FastAPI:
    settings = get_settings()
    ctx = (context_factory or AppContext.create)()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ctx.bus.bind_loop(asyncio.get_running_loop())
        try:
            yield
        finally:
            ctx.replay.stop(publish=False)
            ctx.bus.bind_loop(None)

    app = FastAPI(
        title="Nexus911",
        version=__version__,
        description="Claim-weighted knowledge graph for 911: links duplicate calls, surfaces what's new, keeps humans in control.",
        lifespan=lifespan,
    )
    app.state.ctx = ctx
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Not found: {exc.args[0] if exc.args else ''}"})

    @app.exception_handler(ScenarioNotFound)
    async def scenario_not_found(_: Request, exc: ScenarioNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Unknown scenario: {exc.args[0] if exc.args else ''}"})

    @app.exception_handler(LinkActionError)
    async def conflict(_: Request, exc: LinkActionError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    for router in ROUTERS:
        app.include_router(router)
    app.include_router(ws_router)
    mount_frontend(app, frontend_dist)
    return app


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve ``frontend/dist`` at ``/`` with an SPA fallback, when it exists."""
    index = dist / "index.html"
    if not index.is_file():
        return
    root = dist.resolve()
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
