"""Web server: serves the UI and a small JSON API.

Run with:  .venv/bin/uvicorn app.main:app --port 8765
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, refresh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("scrapling").setLevel(logging.WARNING)

STATIC = Path(__file__).resolve().parent.parent / "static"


def _scheduler() -> None:
    """Re-scrape in the background; refresh_hours in sources.yaml decides what's due.
    Every 15 minutes it also drops anything that has aged past 48 hours (3 days for Kenya)."""
    while True:
        refresh.run()
        time.sleep(15 * 60)


@asynccontextmanager
async def lifespan(_app):
    refresh.classify_stored()
    threading.Thread(target=_scheduler, daemon=True).start()
    yield


app = FastAPI(title="DevDrop", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def always_revalidate(request, call_next):
    """Make browsers check for a newer page and scripts on every visit.
    Without this they reuse cached copies after an update, and an old script
    paired with a new page can leave the page blank."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/items")
def items(hours: int = Query(72, ge=1, le=72)):
    return {"items": db.recent(hours), "status": refresh.status}


class RefreshBody(BaseModel):
    force: bool = True


@app.post("/api/refresh")
def do_refresh(body: RefreshBody):
    refresh.run_in_background(body.force)
    return {"started": True}


@app.get("/api/status")
def status():
    return refresh.status
