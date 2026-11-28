"""Tech job sources. Each function returns Items; the refresh step drops anything
without a posting date in the last 48 hours."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone

from ..kenya import in_kenya
from ..classify import years_to_level
from ..models import MAX_AGE_HOURS, Item, parse_date
from ..tech import is_tech
from .feeds import feed_items
from .fetch import get

_REL_UNITS = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720, "year": 8760}


def _relative_age(text: str) -> str | None:
    """'about 1 hour' / '5 days' / 'less than a minute' -> ISO timestamp, or None."""
    m = re.search(r"(\d+|an?|less than a)\s+(minute|hour|day|week|month|year)s?", text or "", re.I)
    if not m:
        return None
    n = 0 if m[1].lower().startswith("less") else (1 if not m[1].isdigit() else int(m[1]))
    hours = n * _REL_UNITS[m[2].lower()]
    return parse_date(int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()))


def _money(lo, hi, currency="$") -> str:
    try:
        lo, hi = int(float(lo or 0)), int(float(hi or 0))
    except ValueError:
        return ""
    if not lo and not hi:
        return ""
    if lo and hi and lo != hi:
        return f"{currency}{lo:,} – {currency}{hi:,}"
    return f"{currency}{max(lo, hi):,}"


def _text(s: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def _cutoff_epoch() -> int:
    return int((datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)).timestamp())


# ---------- JSON APIs ----------

def himalayas(max_pages: int = 30) -> list[Item]:
    """Newest first, 20 per page; stop once we're past 48 h."""
    items: list[Item] = []
    for page in range(max_pages):
        data = get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": page * 20}).json()
        jobs = data.get("jobs") or []
        for j in jobs:
            cats = (j.get("parentCategories") or []) + (j.get("categories") or [])
            # Himalayas' categories are broad (SAP consultants count as "Developer"),
            # so the title has to read as a tech role too.
            if not is_tech(j["title"]) or re.search(r"\btest job\b", j["title"], re.I):
                continue
            regions = j.get("locationRestrictions") or []
            # Only the first 3 are shown, so put Kenya first: a job open to
            # "Albania, …, Kenya, … (+49 more)" must still read as open to Kenya.
            regions = sorted(regions, key=lambda r: not in_kenya(r))
            items.append(Item(
                id=f"himalayas:{j.get('guid') or j['applicationLink']}", kind="job", source="Himalayas",
                title=j["title"], org=j.get("companyName") or "",
                url=j.get("applicationLink") or j.get("guid") or "",
                location=", ".join(regions[:3]) + (f" +{len(regions) - 3} more" if len(regions) > 3 else "") or "Worldwide",
                remote=True, posted_at=parse_date(j.get("pubDate")),
                salary=_money(j.get("minSalary"), j.get("maxSalary"), "$" if (j.get("currency") or "USD") == "USD" else f"{j.get('currency')} "),
                tags=[c.replace("-", " ") for c in cats[:3]],
                level_hint=" ".join(j.get("seniority") or []), type_hint=j.get("employmentType") or "",
            ))
        if not jobs or int(jobs[-1].get("pubDate") or 0) < _cutoff_epoch():
            break
    return items


def jobicy() -> list[Item]:
    items, seen = [], set()
    for industry in ("dev", "engineering", "data-science"):
        data = get("https://jobicy.com/api/v2/remote-jobs", params={"count": 100, "industry": industry}).json()
        for j in data.get("jobs", []):
            if j["id"] in seen or (industry == "engineering" and not is_tech(j["jobTitle"])):
                continue
            seen.add(j["id"])
            cur = {"USD": "$", "EUR": "€", "GBP": "£"}.get(j.get("salaryCurrency"), "")
            items.append(Item(
                id=f"jobicy:{j['id']}", kind="job", source="Jobicy",
                title=html.unescape(j["jobTitle"]), org=j.get("companyName") or "", url=j["url"],
                location=j.get("jobGeo") or "Worldwide", remote=True,
                posted_at=parse_date(j.get("pubDate")),
                salary=_money(j.get("salaryMin"), j.get("salaryMax"), cur),
                tags=[html.unescape(t) for t in (j.get("jobIndustry") or [])[:2]],
                level_hint=j.get("jobLevel") or "", type_hint=" ".join(j.get("jobType") or []),
            ))
    return items


def arbeitnow(pages: int = 3) -> list[Item]:
    items = []
    for page_no in range(1, pages + 1):
        data = get("https://www.arbeitnow.com/api/job-board-api", params={"page": page_no}).json()
        for j in data.get("data", []):
            tags = list(j.get("tags") or [])
            if not is_tech(j["title"], *tags):
                continue
            items.append(Item(
                id=f"arbeitnow:{j['slug']}", kind="job", source="Arbeitnow",
                title=j["title"], org=j.get("company_name") or "", url=j["url"],
                location=j.get("location") or "", remote=bool(j.get("remote")),
                posted_at=parse_date(j.get("created_at")), tags=tags[:3],
                type_hint=" ".join(j.get("job_types") or []),
            ))
        if not (data.get("links") or {}).get("next"):
            break
    return items


def hn_who_is_hiring() -> list[Item]:
    """Top-level comments in this month's 'Ask HN: Who is hiring?' thread.

    By convention each starts with 'Company | Role | Location | ...'.
    """
    stories = get("https://hn.algolia.com/api/v1/search_by_date", params={
        "tags": "story,author_whoishiring", "hitsPerPage": 5,
    }).json().get("hits", [])
    thread = next((s for s in stories if "who is hiring" in (s.get("title") or "").lower()), None)
    if not thread:
        return []
    tid = int(thread["objectID"])
    data = get("https://hn.algolia.com/api/v1/search_by_date", params={
        "tags": f"comment,story_{tid}", "hitsPerPage": 500,
        "numericFilters": f"created_at_i>{_cutoff_epoch()}",
    }).json()
    items = []
    for c in data.get("hits", []):
        if c.get("parent_id") != tid:
            continue  # replies, not postings
        text = c.get("comment_text") or ""
        first = _text(re.split(r"<p>|\n", text, maxsplit=1)[0])
        parts = [p.strip() for p in first.split("|") if p.strip()]
        if len(parts) < 2 or not is_tech(first, _text(text)[:400]):
            continue
        role = next((p for p in parts[1:] if is_tech(p)), parts[1])
        loc = next((p for p in parts[1:] if p is not role and re.search(
            r"remote|onsite|on-site|hybrid|,|\b[A-Z]{2}\b|london|berlin|york|francisco|nyc|sf\b", p, re.I)), "")
        items.append(Item(
            id=f"hnhiring:{c['objectID']}", kind="job", source="HN Who is hiring",
            title=role[:140], org=parts[0][:80],
            url=f"https://news.ycombinator.com/item?id={c['objectID']}",
            location=loc[:100], remote=bool(re.search(r"remote", first, re.I)),
            posted_at=parse_date(c.get("created_at_i")),
        ))
    return items


# ---------- HTML pages, scraped with Scrapling ----------

def yc_jobs() -> list[Item]:
    """Y Combinator startup jobs. The page embeds its data as JSON in a
    `data-page` attribute, which Scrapling's selector pulls out directly."""
    items, seen = [], set()
    for path in ("/jobs/role/software-engineer", "/jobs/role/software-engineer/remote",
                 "/jobs/role/science", "/jobs/role/designer", "/jobs"):
        page = get(f"https://www.ycombinator.com{path}")
        node = page.css("[data-page]")
        if not node:
            continue
        for j in json.loads(node[0].attrib["data-page"])["props"].get("jobPostings", []):
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            if j.get("role") not in ("eng", "science", "design") and not is_tech(j["title"]):
                continue
            loc = j.get("location") or ""
            items.append(Item(
                id=f"yc:{j['id']}", kind="job", source="YC Startups",
                title=j["title"],
                org=f"{j.get('companyName', '')} ({j['companyBatchName']})" if j.get("companyBatchName") else j.get("companyName", ""),
                url=f"https://www.ycombinator.com{j['url']}",
                location=" / ".join(dict.fromkeys(p.strip() for p in loc.split("/")))[:120],
                remote="remote" in loc.lower(),
                # YC only gives a relative age ("about 1 hour", "2 days"). "2 days" lands
                # exactly on the 48 h line and is dropped, so only clear matches survive.
                posted_at=_relative_age(j.get("createdAt")),
                salary=j.get("salaryRange") or "",
                tags=[t for t in [j.get("roleSpecificType"), j.get("minExperience")] if t],
                level_hint=years_to_level(j.get("minExperience") or ""), type_hint=j.get("type") or "",
            ))
    return items


WWR_FEEDS = [
    "remote-jobs",  # all categories; filtered to tech below
    "categories/remote-programming-jobs", "categories/remote-full-stack-programming-jobs",
    "categories/remote-back-end-programming-jobs", "categories/remote-front-end-programming-jobs",
    "categories/remote-devops-sysadmin-jobs",
]


def wwr() -> list[Item]:
    """We Work Remotely RSS feeds. Titles are 'Company: Role'."""
    items: dict[str, Item] = {}
    for feed in WWR_FEEDS:
        for d in feed_items(f"https://weworkremotely.com/{feed}.rss"):
            org, _, title = _text(d.get("title")).partition(": ")
            if not title:
                org, title = "", org
            cats = [_text(c) for c in d["category"]]
            # Even WWR's category feeds carry some non-tech posts, so check every title.
            link = d.get("link") if (d.get("link") or "").startswith("http") else d.get("guid", "")
            if not is_tech(title, *cats) or not link.startswith("http"):
                continue
            item_id = f"wwr:{link.rstrip('/').rsplit('/', 1)[-1]}"
            items.setdefault(item_id, Item(
                id=item_id, kind="job", source="We Work Remotely", title=title, org=org, url=link,
                location=_text(d.get("region")) or "Remote", remote=True,
                posted_at=parse_date(d.get("pubdate")), tags=cats[:3],
            ))
    return list(items.values())
