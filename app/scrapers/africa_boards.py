"""African job boards, scraped from their listing pages with Scrapling.

- MyJobMag (Kenya, Nigeria, South Africa): the IT section, newest first, with a
  posting date on every listing ("14 November").
- BrighterMonday (Kenya, Uganda) and Jobberman (Nigeria, Ghana), sister sites:
  the Software & Data section, with relative dates ("Posted 5 days ago").

Only listing pages are fetched (both sites' robots.txt allow them); job links
open on the sites themselves.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from ..models import Item, iso
from ..tech import is_tech
from .fetch import get

log = logging.getLogger(__name__)

# Listing dates are local calendar days. Treat a day as starting at midnight in the
# easternmost of these time zones (UTC+3), the earliest moment it could mean, so
# the 48-hour check can only err towards dropping a listing, never keeping an old one.
_EARLIEST_OFFSET = timedelta(hours=3)

MYJOBMAG = [  # (site, country)
    ("https://www.myjobmag.co.ke", "Kenya"),
    ("https://www.myjobmag.com", "Nigeria"),
    ("https://www.myjobmag.co.za", "South Africa"),
]
RINGIER = [  # (site, source name, country)
    ("https://www.brightermonday.co.ke", "BrighterMonday", "Kenya"),
    ("https://www.brightermonday.co.ug", "BrighterMonday", "Uganda"),
    ("https://www.jobberman.com", "Jobberman", "Nigeria"),
    ("https://www.jobberman.com.gh", "Jobberman", "Ghana"),
]


def _day_start(day: datetime) -> str:
    return iso(day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc) - _EARLIEST_OFFSET)


def _myjobmag_date(text: str) -> str | None:
    """'14 November' (no year) -> ISO timestamp of that day's start."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)", text or "")
    if not m:
        return None
    now = datetime.now(timezone.utc)
    try:
        day = datetime.strptime(f"{m[1]} {m[2]} {now.year}", "%d %B %Y")
    except ValueError:
        return None
    if day.replace(tzinfo=timezone.utc) > now + timedelta(days=1):
        day = day.replace(year=now.year - 1)  # "30 December" seen in early January
    return _day_start(day)


def _relative_date(text: str) -> str | None:
    """'Posted today' / 'Posted 3 hours ago' / 'Posted 1 day ago' -> ISO timestamp."""
    t = (text or "").lower()
    now = datetime.now(timezone.utc)
    if "today" in t or "just now" in t:
        return _day_start(now)
    if "yesterday" in t:
        return _day_start(now - timedelta(days=1))
    m = re.search(r"(\d+|an?)\s+(minute|hour|day|week|month|year)s?\s+ago", t)
    if not m:
        return None
    n = 1 if not m[1].isdigit() else int(m[1])
    hours = {"minute": n / 60, "hour": n, "day": 24 * n, "week": 168 * n, "month": 720 * n, "year": 8760 * n}[m[2]]
    # "1 day ago" can mean up to 47 h; count it from the start of that day.
    when = now - timedelta(hours=hours)
    return _day_start(when) if m[2] == "day" else iso(when)


def myjobmag(pages: int = 3) -> list[Item]:
    items = []
    for site, country in MYJOBMAG:
        for page in range(1, pages + 1):
            path = "/jobs-by-field/information-technology" + (f"/{page}" if page > 1 else "")
            try:
                doc = get(site + path)
            except Exception as e:
                log.warning("MyJobMag %s page %d failed: %s", country, page, e)
                break
            rows = doc.css("li.job-list-li")
            for row in rows:
                link = row.css("li.mag-b h2 a")
                if not link:
                    continue  # ad slot
                raw = link[0].get_all_text(strip=True)
                title, _, org = raw.rpartition(" at ")
                title, org = (title or raw).strip(), org.strip()
                if not is_tech(title):
                    continue
                href = link[0].attrib.get("href", "")
                date_node = row.css("#job-date")
                city = " ".join(row.css("#job-date a::text").getall()).strip()
                items.append(Item(
                    id=f"myjobmag:{country}:{href.rstrip('/').rsplit('/', 1)[-1]}", kind="job",
                    source="MyJobMag", title=title, org=org, url=site + href,
                    location=", ".join(p for p in [city, country] if p),
                    posted_at=_myjobmag_date(date_node[0].get_all_text(strip=True) if date_node else ""),
                ))
            if not rows:
                break
    return items


def ringier_boards(pages: int = 2) -> list[Item]:
    """BrighterMonday and Jobberman share one platform and page layout."""
    items = []
    for site, source, country in RINGIER:
        for page in range(1, pages + 1):
            try:
                doc = get(site + "/jobs/software-data", params={"page": page} if page > 1 else None)
            except Exception as e:
                log.warning("%s %s page %d failed: %s", source, country, page, e)
                break
            cards = doc.css('[data-cy="listing-cards-components"]')
            for card in cards:
                link = next((a for a in card.css("a[href*='/listings/']")), None)
                if link is None:
                    continue
                parts = [p for p in card.get_all_text(separator="|", strip=True).split("|") if p.strip()]
                title = link.get_all_text(strip=True) or (parts[1] if len(parts) > 1 else "")
                posted = next((p for p in parts if p.lower().startswith("posted")), "")
                org = next((a.get_all_text(strip=True) for a in card.css("a[href*='/company/']")), "")
                place = next((p for p in parts if re.search(r"\b(remote|nairobi|mombasa|kampala|lagos|abuja|accra|kumasi|"
                                                               r"kisumu|nakuru|port harcourt|ibadan)\b", p, re.I)), "")
                if not is_tech(title):
                    continue
                href = link.attrib.get("href", "")
                items.append(Item(
                    id=f"{source.lower()}:{href.rstrip('/').rsplit('/', 1)[-1]}", kind="job",
                    source=source, title=title, org=org,
                    url=href if href.startswith("http") else site + href,
                    location=place if country.lower() in place.lower() else ", ".join(p for p in [place, country] if p),
                    posted_at=_relative_date(posted),
                ))
            if not cards:
                break
    return items
