"""Big employers' engineering hubs in Africa (Nairobi, Cape Town, Cairo, Lagos …),
from their own career-site search APIs:

- Amazon (amazon.jobs search, by country)
- Microsoft (careers search, by country; rate-limited, so requests are spaced out)
- Companies whose careers sites run on Workday (Mastercard, Absa, Cisco, …),
  searched by country name

Which countries and Workday companies to check is configured under `hubs:` in
sources.yaml.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone

from scrapling.fetchers import Fetcher

from ..models import Item, iso, parse_date
from ..tech import is_tech
from .fetch import get

log = logging.getLogger(__name__)

# ISO 3166 alpha-3 codes, as Amazon's search uses them.
_ALPHA3 = {"Kenya": "KEN", "South Africa": "ZAF", "Nigeria": "NGA", "Egypt": "EGY", "Ghana": "GHA",
           "Rwanda": "RWA", "Morocco": "MAR", "Uganda": "UGA", "Tanzania": "TZA", "Ethiopia": "ETH",
           "Tunisia": "TUN", "Senegal": "SEN", "Côte d'Ivoire": "CIV"}

# Dates without a time ("November 13, 2026", "Posted Yesterday") are counted from
# the earliest moment that day could have started in Africa (UTC+3), so the 48-hour
# check can only err towards dropping a listing.
_EARLIEST_OFFSET = timedelta(hours=3)


def _day_start(day: datetime) -> str:
    return iso(day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc) - _EARLIEST_OFFSET)


# ---------- Amazon ----------

def amazon(countries: list[str]) -> list[Item]:
    items = []
    for country in countries:
        code = _ALPHA3.get(country)
        if not code:
            continue
        data = get("https://www.amazon.jobs/en/search.json",
                   params={"country": code, "result_limit": 100, "sort": "recent"}).json()
        for j in data.get("jobs", []):
            if not is_tech(j["title"], j.get("job_category") or ""):
                continue
            try:
                day = datetime.strptime(re.sub(r"\s+", " ", j["posted_date"]), "%B %d, %Y")
            except (KeyError, ValueError):
                continue
            items.append(Item(
                id=f"amazon:{j['id_icims']}", kind="job", source="Big tech hubs",
                title=j["title"].strip(), org="Amazon" if "aws" not in (j.get("business_category") or "") else "Amazon Web Services",
                url="https://www.amazon.jobs" + j["job_path"],
                location=", ".join(p for p in [j.get("city"), country] if p),
                posted_at=_day_start(day),
                tags=[t for t in [j.get("job_category")] if t],
                level_hint="Internship" if j.get("is_intern") else "",
                type_hint=j.get("job_schedule_type") or "",
            ))
    return items


# ---------- Microsoft ----------

def _microsoft_search(location: str) -> list[dict]:
    """Microsoft's careers search answers 429 to quick bursts, so back off and retry."""
    for attempt in range(4):
        page = Fetcher.get("https://apply.careers.microsoft.com/api/pcsx/search", timeout=30, retries=1,
                           params={"domain": "microsoft.com", "location": location, "start": 0,
                                   "sort_by": "timestamp"})
        if page.status == 200:
            return page.json().get("data", {}).get("positions", [])
        if page.status != 429:
            raise RuntimeError(f"Microsoft careers search returned HTTP {page.status}")
        time.sleep(15 * (attempt + 1))
    raise RuntimeError("Microsoft careers search kept rate-limiting (HTTP 429)")


def microsoft(countries: list[str]) -> list[Item]:
    items, seen = [], set()
    for i, country in enumerate(countries):
        if i:
            time.sleep(5)  # stay under the rate limit
        for p in _microsoft_search(country):
            if p["id"] in seen or not is_tech(p["name"], p.get("department") or ""):
                continue
            seen.add(p["id"])
            mode = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}.get((p.get("workLocationOption") or "").lower(), "")
            # Locations read "Egypt, Cairo, Cairo": show them city-first.
            locs = [", ".join(dict.fromkeys(reversed([x.strip() for x in l.split(",")]))) for l in p.get("locations") or []]
            items.append(Item(
                id=f"microsoft:{p['id']}", kind="job", source="Big tech hubs",
                title=p["name"].strip(), org="Microsoft",
                url="https://apply.careers.microsoft.com" + (p.get("positionUrl") or f"/careers/job/{p['id']}"),
                location=" / ".join(locs[:3]), posted_at=parse_date(p.get("postedTs")),
                tags=[t for t in [p.get("department")] if t], mode_hint=mode,
            ))
    return items


# ---------- Workday-hosted career sites ----------

def _workday_posted(text: str) -> str | None:
    """'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' / 'Posted 30+ Days Ago'."""
    t = (text or "").lower()
    now = datetime.now(timezone.utc)
    if "today" in t:
        return _day_start(now)
    if "yesterday" in t:
        return _day_start(now - timedelta(days=1))
    m = re.search(r"(\d+)\+?\s+days?\s+ago", t)
    return _day_start(now - timedelta(days=int(m[1]))) if m else None


def workday(name: str, host: str, tenant: str, site: str, countries: list[str]) -> list[Item]:
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    items, seen = [], set()
    for country in countries:
        page = Fetcher.post(f"{base}/jobs", timeout=30,
                            json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": country})
        if page.status != 200:
            raise RuntimeError(f"{name} Workday search returned HTTP {page.status}")
        for j in page.json().get("jobPostings", []):
            path = j.get("externalPath") or ""
            if path in seen or not is_tech(j.get("title") or ""):
                continue
            seen.add(path)
            posted = _workday_posted(j.get("postedOn"))
            location = j.get("locationsText") or ""
            if re.match(r"\d+ Locations", location) and posted:
                # "2 Locations": the job's own page lists them.
                try:
                    info = get(base + path).json().get("jobPostingInfo", {})
                    location = " / ".join([info.get("location", "")] + (info.get("additionalLocations") or []))
                except Exception:
                    pass
            items.append(Item(
                id=f"workday:{tenant}:{path.rsplit('_', 1)[-1]}", kind="job", source="Big tech hubs",
                title=j["title"].strip(), org=name, url=f"https://{host}/en-US/{site}{path}",
                location=location, posted_at=posted,
            ))
    return items


def big_tech_hubs(config: dict) -> list[Item]:
    """`config` is the `hubs:` section of sources.yaml."""
    countries = (config or {}).get("countries") or ["Kenya"]
    items: list[Item] = []
    for label, fn in [("Amazon", lambda: amazon(countries)), ("Microsoft", lambda: microsoft(countries))]:
        try:
            items += fn()
        except Exception as e:  # one employer failing shouldn't sink the rest
            log.warning("%s careers failed: %s", label, e)
    for name, w in ((config or {}).get("workday") or {}).items():
        try:
            items += workday(name, w["host"], w["tenant"], w["site"], countries)
        except Exception as e:
            log.warning("%s careers failed: %s", name, e)
    return items
