"""Capa & Co monitoring dashboard — FastAPI application factory."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))


def create_app(scheduler=None, bot=None, safe_run_fn=None):
    """Build the FastAPI app. Receives scheduler/bot from daemon for live access."""
    app = FastAPI(title="Capa & Co Dashboard", docs_url=None, redoc_url=None)

    # Store shared objects so routes can access them
    app.state.scheduler = scheduler
    app.state.bot = bot
    app.state.safe_run = safe_run_fn

    # Static files
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

    # Auth middleware
    from web.auth import AuthMiddleware

    secret = os.environ.get("DASHBOARD_SECRET", "")
    if secret:
        app.add_middleware(AuthMiddleware, secret=secret)

    # Register routes
    from web.routes import dashboard, queue, logs, schedule, analytics, leads, engagement, system
    from web.auth import router as auth_router

    app.include_router(auth_router)
    app.include_router(dashboard.router)
    app.include_router(queue.router)
    app.include_router(logs.router)
    app.include_router(schedule.router)
    app.include_router(analytics.router)
    app.include_router(leads.router)
    app.include_router(engagement.router)
    app.include_router(system.router)

    return app
