from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

WINDOW_HOURS = 48   # jobs and events older than this are dropped...
MAX_AGE_HOURS = 72  # ...except Kenya listings, kept for 3 days. Nothing older is kept.


@dataclass
class Item:
    """One job or event, normalised across all sources."""

    id: str                      # "<source>:<native id>"
    kind: str                    # "job" | "event"
    source: str
    title: str
    url: str
    posted_at: str | None        # ISO UTC, when the source says it was posted
    org: str = ""
    location: str = ""
    remote: bool = False  # from the source: "this source says it's remote/online";
                          # app.classify then settles it from the title and location too
    starts_at: str | None = None  # ISO UTC, events only
    salary: str = ""
    tags: list[str] = field(default_factory=list)
    # Set by app.classify from the title and the hints below.
    level: str = ""       # jobs: Internship, Junior, Mid, Senior, Lead / Staff, Manager, Unspecified
    category: str = ""    # jobs: Frontend, Backend, Data & AI, ...; events: Conference, Hackathon, ...
    job_type: str = ""    # jobs: Full-time, Part-time, Contract, Unspecified
    work_mode: str = ""   # jobs: Remote, Hybrid, On-site (or "" if unknown); events: Online, In person
    kenya: str = ""       # "in" (located in Kenya), "remote" (remote, open to Kenya) or ""
    level_hint: str = ""  # the source's own seniority label, if it has one
    type_hint: str = ""   # the source's own employment-type label
    mode_hint: str = ""   # the source's own work mode (Remote / Hybrid / On-site), if it states one


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def now_iso() -> str:
    return iso(datetime.now(timezone.utc))


def cutoff_iso(hours: float = MAX_AGE_HOURS) -> str:
    return iso(datetime.now(timezone.utc) - timedelta(hours=hours))


def parse_date(value) -> str | None:
    """Accepts ISO strings, unix epochs and RFC 822 dates; returns ISO UTC or None."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            v = int(value)
            if v > 10**11:  # milliseconds
                v //= 1000
            return iso(datetime.fromtimestamp(v, tz=timezone.utc))
        s = str(value).strip()
        try:
            return iso(datetime.fromisoformat(s.replace("Z", "+00:00")))
        except ValueError:
            return iso(parsedate_to_datetime(s))
    except (ValueError, TypeError, OverflowError):
        return None


def is_fresh(item: Item, hours: float = MAX_AGE_HOURS) -> bool:
    """True only if the source gives a posting date and it's within `hours`.

    The posting date must also not be in the future (a sign of a bad date).
    """
    if not item.posted_at:
        return False
    return cutoff_iso(hours) <= item.posted_at <= iso(datetime.now(timezone.utc) + timedelta(hours=1))
