from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classify import remote_label
from .models import MAX_AGE_HOURS, Item, cutoff_iso, iso, now_iso

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = _connect()
_conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL,
        title TEXT NOT NULL, url TEXT NOT NULL, posted_at TEXT NOT NULL,
        org TEXT, location TEXT, remote INTEGER, starts_at TEXT, salary TEXT, tags TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_listings_posted ON listings(posted_at);
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    """
)
# Columns added after the first version: add them to an existing database.
_cols = {r["name"] for r in _conn.execute("PRAGMA table_info(listings)")}
for _col in ("level", "category", "job_type", "work_mode", "africa_country", "africa_scope"):
    if _col not in _cols:
        _conn.execute(f"ALTER TABLE listings ADD COLUMN {_col} TEXT")
        _conn.execute("DELETE FROM meta WHERE key LIKE 'last_run:%'")  # re-scrape to fill it in
_conn.commit()


def upsert(items: list[Item]) -> None:
    with _lock:
        _conn.executemany(
            """
            INSERT INTO listings (id, kind, source, title, url, posted_at, org, location,
                                  remote, starts_at, salary, tags, level, category, job_type, work_mode,
                                  africa_country, africa_scope)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, url=excluded.url, posted_at=excluded.posted_at,
                org=excluded.org, location=excluded.location, remote=excluded.remote,
                starts_at=excluded.starts_at, salary=excluded.salary, tags=excluded.tags,
                level=excluded.level, category=excluded.category, job_type=excluded.job_type,
                work_mode=excluded.work_mode, africa_country=excluded.africa_country,
                africa_scope=excluded.africa_scope
            """,
            [
                (i.id, i.kind, i.source, i.title, i.url, i.posted_at, i.org, i.location,
                 int(i.remote), i.starts_at, i.salary, json.dumps(i.tags),
                 i.level, i.category, i.job_type, i.work_mode, i.africa_country, i.africa_scope)
                for i in items
            ],
        )
        _conn.commit()


def recent(hours: int) -> list[dict]:
    """Listings whose source-given posting date is within `hours`, newest first."""
    hours = min(hours, MAX_AGE_HOURS)
    stale_event = iso(datetime.now(timezone.utc) - timedelta(hours=12))
    with _lock:
        rows = _conn.execute(
            """
            SELECT * FROM listings
            WHERE posted_at >= ?
              AND (kind != 'event' OR starts_at IS NULL OR starts_at >= ?)
            ORDER BY posted_at DESC
            """,
            (cutoff_iso(hours), stale_event),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"] or "[]")
        d["remote"] = bool(d["remote"])
        if d.get("work_mode") == "Remote":
            d["remote_from"] = remote_label(Item(id="", kind=d["kind"], source="", title="", url="",
                                                 posted_at="", location=d["location"] or ""))
        out.append(d)
    return out


def stored(where: str = "1=1") -> list[Item]:
    """Stored listings as Items (`where` is a fixed SQL condition, never user input)."""
    with _lock:
        rows = _conn.execute(f"SELECT * FROM listings WHERE {where}").fetchall()
    return [
        Item(id=r["id"], kind=r["kind"], source=r["source"], title=r["title"], url=r["url"],
             posted_at=r["posted_at"], org=r["org"] or "", location=r["location"] or "",
             remote=bool(r["remote"]), starts_at=r["starts_at"], salary=r["salary"] or "",
             tags=json.loads(r["tags"] or "[]"), level=r["level"] or "", category=r["category"] or "",
             job_type=r["job_type"] or "", work_mode=r["work_mode"] or "",
             africa_country=r["africa_country"] or "", africa_scope=r["africa_scope"] or "")
        for r in rows
    ]


def delete(ids: list[str]) -> None:
    with _lock:
        _conn.executemany("DELETE FROM listings WHERE id = ?", [(i,) for i in ids])
        _conn.commit()


def prune() -> int:
    """Delete everything posted more than 48 h ago."""
    with _lock:
        n = _conn.execute("DELETE FROM listings WHERE posted_at < ?", (cutoff_iso(),)).rowcount
        _conn.commit()
    return n


def meta_get(key: str, default=None):
    with _lock:
        row = _conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return default if row is None else json.loads(row["value"])


def meta_delete_except(prefix: str, keep: set[str]) -> None:
    """Delete meta keys `prefix + name` whose name isn't in `keep`."""
    with _lock:
        keys = [r["key"] for r in _conn.execute("SELECT key FROM meta WHERE key LIKE ?", (prefix + "%",))]
        _conn.executemany("DELETE FROM meta WHERE key = ?",
                          [(k,) for k in keys if k[len(prefix):] not in keep])
        _conn.commit()


def meta_set(key: str, value) -> None:
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))
        _conn.commit()
