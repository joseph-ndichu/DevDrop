"""Runs the scrapers and stores only tech listings posted in the last 48 hours."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import yaml

from . import db
from .classify import classify, set_africa, work_mode
from .models import is_fresh, now_iso
from .scrapers import BUILTIN, CONFIG_SECTIONS, SOURCE_NAMES
from .tech import is_tech

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "sources.yaml"

_run_lock = threading.Lock()
_pending = False
status: dict = {"running": False, "started": None, "finished": None, "sources": {}}


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def _due(name: str, hours: float, force: bool) -> bool:
    if force:
        return True
    last = db.meta_get(f"last_run:{name}")
    return last is None or time.time() - last > hours * 3600


def run(force: bool = False) -> dict:
    """Scrape every enabled source that is due."""
    global _pending
    if not _run_lock.acquire(blocking=False):
        _pending = _pending or force  # run again right after the current one
        return status
    try:
        cfg = load_config()
        hours = float(cfg.get("refresh_hours", 2))
        status.update(running=True, started=now_iso(), finished=None, sources={})

        builtin_cfg = cfg.get("builtin") or {}
        jobs = [(name, (lambda fn=fn: fn(cfg.get(CONFIG_SECTIONS[fn]))) if fn in CONFIG_SECTIONS else fn)
                for name, fn in BUILTIN.items()
                if (builtin_cfg.get(name) or {}).get("enabled", True)]

        for name, fn in jobs:
            if not _due(name, hours, force):
                status["sources"][name] = {"skipped": "fetched recently"}
                continue
            try:
                items = fn()
                fresh = [i for i in items if is_fresh(i)]  # strict: no date or older than 48 h -> dropped
                for i in fresh:
                    classify(i)
                db.upsert(fresh)
                db.meta_set(f"last_run:{name}", time.time())
                status["sources"][name] = {"ok": len(fresh), "dropped": len(items) - len(fresh)}
                log.info("%s: kept %d, dropped %d", name, len(fresh), len(items) - len(fresh))
            except Exception as e:
                status["sources"][name] = {"error": str(e)[:300]}
                log.exception("%s failed", name)

        db.prune()
        return status
    finally:
        status.update(running=False, finished=now_iso())
        _run_lock.release()
        if _pending:
            _pending = False
            run_in_background(force=True)


def classify_stored() -> None:
    """On startup, bring stored listings up to the current rules: remove jobs that
    no longer pass the tech filter or come from removed sources, and classify
    listings saved before categories or work modes existed."""
    items = db.stored()
    drop = [i.id for i in items
            if i.source not in SOURCE_NAMES or (i.kind == "job" and not is_tech(i.title))]
    keep = [i for i in items if i.id not in set(drop)]
    for item in keep:
        if not item.level and not item.category:
            classify(item)  # saved before categories existed
        elif not item.work_mode:
            item.work_mode = work_mode(item)  # saved before work modes existed
            item.remote = item.work_mode in ("Remote", "Online")
        set_africa(item)  # cheap and depends only on location and work mode, so always redo it
    db.delete(drop)
    db.upsert(keep)
    log.info("startup check: %d listings kept, %d removed (non-tech or removed source)", len(keep), len(drop))
    # Forget when removed sources last ran.
    db.meta_delete_except("last_run:", set(BUILTIN))


def run_in_background(force: bool = False) -> None:
    threading.Thread(target=run, args=(force,), daemon=True).start()
