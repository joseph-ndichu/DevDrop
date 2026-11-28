"""Remote job boards. Whether a job is open to people in Kenya comes from its
stated location (worldwide, EMEA, Africa, ...); see app.kenya.

- Remote OK, Remotive, Working Nomads: public JSON APIs with posting times.
- NoDesk: RSS feed with posting times.
- DailyRemote: listing pages, with relative ages ("53 mins ago").
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone

from ..models import Item, iso, parse_date
from ..tech import is_tech
from .feeds import feed_items
from .fetch import get

log = logging.getLogger(__name__)


def _text(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _money(lo, hi) -> str:
    try:
        lo, hi = int(float(lo or 0)), int(float(hi or 0))
    except (TypeError, ValueError):
        return ""
    if lo and hi and lo != hi:
        return f"${lo:,} – ${hi:,}"
    return f"${max(lo, hi):,}" if lo or hi else ""


def remoteok() -> list[Item]:
    items = []
    for j in get("https://remoteok.com/api").json():
        if not isinstance(j, dict) or not j.get("id") or not j.get("position"):
            continue  # the first entry is the API's terms of use
        tags = j.get("tags") or []
        if not is_tech(j["position"], *tags):
            continue
        items.append(Item(
            id=f"remoteok:{j['id']}", kind="job", source="Remote OK",
            title=_text(j["position"]), org=_text(j.get("company")), url=j.get("url") or "",
            location=_text(j.get("location")) or "Worldwide", remote=True,
            posted_at=parse_date(j.get("epoch") or j.get("date")),
            salary=_money(j.get("salary_min"), j.get("salary_max")), tags=tags[:3],
        ))
    return items


def remotive() -> list[Item]:
    items = []
    for j in get("https://remotive.com/api/remote-jobs", timeout=60).json().get("jobs", []):
        tags = j.get("tags") or []
        if not is_tech(j["title"]) or j.get("category") in ("Sales / Business", "Marketing", "Customer Service", "Finance / Legal", "Human Resources"):
            continue
        # Times are UTC without a zone.
        posted = j.get("publication_date") or ""
        items.append(Item(
            id=f"remotive:{j['id']}", kind="job", source="Remotive",
            title=_text(j["title"]), org=_text(j.get("company_name")), url=j["url"],
            location=_text(j.get("candidate_required_location")) or "Worldwide", remote=True,
            posted_at=parse_date(posted + ("" if re.search(r"[Z+]|-\d\d:\d\d$", posted) else "+00:00")) if posted else None,
            salary=_text(j.get("salary")), tags=[j["category"]] if j.get("category") else [],
            type_hint=(j.get("job_type") or "").replace("_", " "),
        ))
    return items


def working_nomads() -> list[Item]:
    items = []
    for j in get("https://www.workingnomads.com/api/exposed_jobs/").json():
        tags = [t for t in (j.get("tags") or "").split(",") if t]
        if j.get("category_name") not in ("Development", "Design") and not is_tech(j["title"]):
            continue
        if not is_tech(j["title"], *tags):
            continue
        items.append(Item(
            id=f"workingnomads:{j['url'].rstrip('/').rsplit('/', 1)[-1]}", kind="job",
            source="Working Nomads", title=_text(j["title"]), org=_text(j.get("company_name")),
            url=j["url"], location=_text(j.get("location")) or "Worldwide", remote=True,
            posted_at=parse_date(j.get("pub_date")), tags=tags[:3],
        ))
    return items


def nodesk() -> list[Item]:
    """Titles are 'Role at Company'; a place, if any, is in the role: '... (United States)'."""
    items = []
    for d in feed_items("https://nodesk.co/remote-jobs/index.xml"):
        role, sep, org = _text(d.get("title")).rpartition(" at ")
        role, org = (role, org) if sep else (org, "")
        if not is_tech(role) or not d.get("link"):
            continue
        place = re.search(r"\(([^)]*)\)\s*$|\s-\s([A-Z][A-Za-z /]+)$", role)  # "... - Colombia/Remote"
        items.append(Item(
            id=f"nodesk:{d['link'].rstrip('/').rsplit('/', 1)[-1]}", kind="job", source="NoDesk",
            title=role, org=org, url=d["link"],
            location=(place[1] or place[2]).strip() if place else "Remote", remote=True,
            posted_at=parse_date(d.get("pubdate")),
        ))
    return items


DAILYREMOTE_SECTIONS = ["remote-software-development-jobs", "remote-data-science-jobs",
                        "remote-devops-sysadmin-jobs", "remote-design-jobs"]


def _age(text: str) -> str | None:
    """'53 mins ago' / '1 hour ago' / '2 days ago' -> ISO timestamp, or None."""
    m = re.search(r"(\d+|an?)\s*(min|minute|hr|hour|day|week)s?\s+ago", text or "", re.I)
    if not m:
        return None
    n = 1 if not m[1].isdigit() else int(m[1])
    hours = {"min": n / 60, "minute": n / 60, "hr": n, "hour": n, "day": 24 * n, "week": 168 * n}[m[2].lower()]
    return iso(datetime.now(timezone.utc) - timedelta(hours=hours))


def dailyremote() -> list[Item]:
    items: dict[str, Item] = {}
    for section in DAILYREMOTE_SECTIONS:
        try:
            doc = get(f"https://dailyremote.com/{section}")
        except Exception as e:
            log.warning("DailyRemote %s failed: %s", section, e)
            continue
        for card in doc.css("article.lst-card"):
            link = card.css("h2 a")
            if not link:
                continue
            title = link[0].get_all_text(strip=True)
            parts = [p.strip() for p in card.get_all_text(separator="|", strip=True).split("|") if p.strip() and p.strip() != "·"]
            age_at = next((n for n, p in enumerate(parts) if p.lower().endswith(" ago")), None)
            if age_at is None or not is_tech(title):
                continue
            org = parts[1] if len(parts) > 1 and parts[1] != "Company hidden" else ""
            place = parts[age_at + 1] if age_at + 1 < len(parts) else ""
            salary = next((p for p in parts[age_at + 1:] if re.search(r"\d+K|\$\d", p)), "")
            href = link[0].attrib.get("href", "")
            job_id = card.attrib.get("data-id") or href.rsplit("-", 1)[-1]
            items.setdefault(job_id, Item(
                id=f"dailyremote:{job_id}", kind="job", source="DailyRemote", title=title, org=org,
                url=href if href.startswith("http") else "https://dailyremote.com" + href,
                location=place if not re.search(r"\d+K|\$|yrs exp", place) else "Worldwide",
                remote=True, posted_at=_age(parts[age_at]), salary=salary,
                type_hint=next((p for p in parts[:age_at] if re.search(r"full|part|contract|freelance", p, re.I)), ""),
            ))
    return list(items.values())
