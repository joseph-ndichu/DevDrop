"""Kenyan job boards. Every listing here is a job in Kenya.

- MyJobMag Kenya: the IT section, with a posting date on every listing ("14 November").
- BrighterMonday Kenya: the Software & Data section ("Posted 5 days ago").
- Jobweb Kenya, Summit Recruitment & Search, NGO Jobs in Africa and
  Opportunities For Africans: WordPress RSS feeds, with exact posting times.
- Corporate Staffing Services: its jobs page, with exact posting times.
- PigiaMe: the jobs section, whose listings carry a posting time.
- Jobrapido Kenya: search results for tech roles, dated by day ("17 Nov").

Boards that cover every field are filtered to tech titles. Only listing pages
and feeds are fetched; job links open on the sites themselves.
"""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from ..kenya import in_kenya
from ..models import Item, cutoff_iso, iso, parse_date
from ..tech import is_tech
from .feeds import feed_items
from .fetch import get

log = logging.getLogger(__name__)

# Listing dates are Kenyan calendar days. A day starts at midnight in Nairobi
# (UTC+3), the earliest moment the date can mean, so the 48-hour check can only
# err towards dropping a listing, never keeping an old one.
_EARLIEST_OFFSET = timedelta(hours=3)

MYJOBMAG = "https://www.myjobmag.co.ke"
BRIGHTERMONDAY = "https://www.brightermonday.co.ke"


def _day_start(day: datetime) -> str:
    return iso(day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc) - _EARLIEST_OFFSET)


def _myjobmag_date(text: str) -> str | None:
    """'14 November' or '17 Nov' (no year) -> ISO timestamp of that day's start."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)", text or "")
    if not m:
        return None
    now = datetime.now(timezone.utc)
    for fmt in ("%d %B %Y", "%d %b %Y"):  # "14 November" or "17 Nov"
        try:
            day = datetime.strptime(f"{m[1]} {m[2]} {now.year}", fmt)
            break
        except ValueError:
            continue
    else:
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
    for page in range(1, pages + 1):
        path = "/jobs-by-field/information-technology" + (f"/{page}" if page > 1 else "")
        try:
            doc = get(MYJOBMAG + path)
        except Exception as e:
            log.warning("MyJobMag page %d failed: %s", page, e)
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
                id=f"myjobmag:Kenya:{href.rstrip('/').rsplit('/', 1)[-1]}", kind="job",
                source="MyJobMag", title=title, org=org, url=MYJOBMAG + href,
                location=", ".join(p for p in [city, "Kenya"] if p),
                posted_at=_myjobmag_date(date_node[0].get_all_text(strip=True) if date_node else ""),
            ))
        if not rows:
            break
    return items


def brightermonday(pages: int = 2) -> list[Item]:
    items = []
    for page in range(1, pages + 1):
        try:
            doc = get(BRIGHTERMONDAY + "/jobs/software-data", params={"page": page} if page > 1 else None)
        except Exception as e:
            log.warning("BrighterMonday page %d failed: %s", page, e)
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
            place = next((p for p in parts if re.search(r"\b(remote|nairobi|mombasa|kisumu|nakuru|eldoret|thika)\b", p, re.I)), "")
            if not is_tech(title):
                continue
            href = link.attrib.get("href", "")
            items.append(Item(
                id=f"brightermonday:{href.rstrip('/').rsplit('/', 1)[-1]}", kind="job",
                source="BrighterMonday", title=title, org=org,
                url=href if href.startswith("http") else BRIGHTERMONDAY + href,
                location=place if "kenya" in place.lower() else ", ".join(p for p in [place, "Kenya"] if p),
                posted_at=_relative_date(posted),
            ))
        if not cards:
            break
    return items


def _text(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _with_kenya(place: str) -> str:
    """'Nairobi' -> 'Nairobi, Kenya'; '' -> 'Kenya'."""
    place = place.strip(" ,|-–")
    return place if "kenya" in place.lower() else ", ".join(p for p in [place, "Kenya"] if p)


def _wordpress_feed(url: str, max_pages: int) -> list[dict]:
    """A WordPress RSS feed, newest first, 10 posts a page, until posts are older than 48 h."""
    out = []
    for page in range(1, max_pages + 1):
        try:
            posts = feed_items(url + (f"{'&' if '?' in url else '?'}paged={page}" if page > 1 else ""))
        except Exception as e:
            if page == 1:
                raise
            log.info("%s page %d: %s", url, page, e)  # past the last page
            break
        out += posts
        oldest = parse_date(posts[-1].get("pubdate")) if posts else None
        if not posts or not oldest or oldest < cutoff_iso():
            break
    return out


def _split_at(title: str) -> tuple[str, str]:
    """'Backend Developer at Acme Ltd' -> ('Backend Developer', 'Acme Ltd')."""
    role, sep, org = title.rpartition(" at ")
    return (role.strip(), org.strip()) if sep and role else (title.strip(), "")


def jobwebkenya(max_pages: int = 30) -> list[Item]:
    """Every field; about 100 posts a day. Titles: 'Role | Town at Company'."""
    items = []
    for d in _wordpress_feed("https://jobwebkenya.com/feed/", max_pages):
        role, org = _split_at(_text(d.get("title")))
        role, _, town = role.partition(" | ")
        if not is_tech(role) or not d.get("link"):
            continue
        items.append(Item(
            id=f"jobwebkenya:{d['link'].rstrip('/').rsplit('/', 1)[-1]}", kind="job",
            source="Jobweb Kenya", title=role, org=org, url=d["link"],
            location=_with_kenya(town), posted_at=parse_date(d.get("pubdate")),
        ))
    return items


def summit_recruitment(max_pages: int = 5) -> list[Item]:
    """Summit's own vacancies. Titles: 'Role (Sector) – Town, Kenya'."""
    items = []
    for d in _wordpress_feed("https://summitrecruitment-search.com/jobs/feed/", max_pages):
        title = role = _text(d.get("title"))
        place = ""
        m = re.search(r"\s+[–-]\s*([^–-]+)$", title)
        if m:
            role, place = title[:m.start()].strip(), m[1].strip()
        if not is_tech(role) or not d.get("link"):
            continue
        items.append(Item(
            id=f"summit:{d['link'].rstrip('/').rsplit('/', 1)[-1]}", kind="job",
            source="Summit Recruitment", title=role, org="Summit Recruitment & Search (for a client)",
            url=d["link"], location=place if in_kenya(place) else _with_kenya(place),
            posted_at=parse_date(d.get("pubdate")),
        ))
    return items


def ngo_jobs_africa(max_pages: int = 5) -> list[Item]:
    """NGO jobs mentioning Kenya; kept only when the post itself is in Kenya."""
    items = []
    for d in _wordpress_feed("https://ngojobsinafrica.com/?s=kenya&feed=rss2", max_pages):
        title, text = _text(d.get("title")), _text(d.get("description"))[:400]
        if not is_tech(title) or not d.get("link") or not in_kenya(f"{title} {text}"):
            continue
        town = next((t for t in ("Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret") if t.lower() in f"{title} {text}".lower()), "")
        items.append(Item(
            id=f"ngojobsafrica:{d['link'].rstrip('/').rsplit('/', 1)[-1]}", kind="job",
            source="NGO Jobs in Africa", title=title, url=d["link"],
            location=_with_kenya(town), posted_at=parse_date(d.get("pubdate")),
        ))
    return items


def opportunities_for_africans(max_pages: int = 5) -> list[Item]:
    """Internships, graduate programmes and jobs tagged Kenya."""
    items = []
    for d in _wordpress_feed("https://www.opportunitiesforafricans.com/feed/", max_pages):
        cats = [_text(c) for c in d["category"]]
        title = _text(d.get("title"))
        if "Kenya" not in cats or not {"Internships", "Jobs", "Graduate Programs"} & set(cats):
            continue
        if not is_tech(title) or not d.get("link"):
            continue
        items.append(Item(
            id=f"ofa:{d['link'].rstrip('/').rsplit('/', 1)[-1]}", kind="job",
            source="Opportunities For Africans", title=title, url=d["link"], location="Kenya",
            posted_at=parse_date(d.get("pubdate")), type_hint="internship" if "Internships" in cats else "",
        ))
    return items


def corporate_staffing(max_pages: int = 6) -> list[Item]:
    """Corporate Staffing Services' jobs page; titles end in 'Job (salary)'."""
    items = []
    for page in range(1, max_pages + 1):
        try:
            doc = get("https://www.corporatestaffing.co.ke/jobs/" + (f"page/{page}/" if page > 1 else ""))
        except Exception as e:
            if page == 1:
                raise
            log.info("Corporate Staffing page %d: %s", page, e)
            break
        posts = [a for a in doc.css("article") if a.css("h2.entry-title a") and a.css("time.published")]
        for art in posts:
            link = art.css("h2.entry-title a")[0]
            # "ICT Officer I Job County Assembly of Machakos", "Senior HR Officer Job (130-150K)"
            raw = link.get_all_text(strip=True)
            title, sep, org = raw.rpartition(" Job")
            title, org = (title, org) if sep else (raw, "")
            salary = (re.search(r"\(([^)]*\d[^)]*)\)", org) or [None, ""])[1]
            org = re.sub(r"\([^)]*\)", "", org).strip(" s-–")
            title = title.strip()
            if not is_tech(title):
                continue
            href = link.attrib.get("href", "")
            tags = " ".join(art.attrib.get("class", "").split())
            town = (re.search(r"tag-jobs-in-([a-z]+)", tags) or [None, ""])[1].title()
            items.append(Item(
                id=f"corporatestaffing:{href.rstrip('/').rsplit('/', 1)[-1]}", kind="job",
                source="Corporate Staffing", title=title, org=org or "Corporate Staffing Services (for a client)",
                url=href, location=_with_kenya(town), salary=f"KES {salary}" if salary else "",
                posted_at=parse_date(art.css("time.published")[0].attrib.get("datetime")),
            ))
        if not posts or min(parse_date(a.css("time.published")[0].attrib.get("datetime")) or "" for a in posts) < cutoff_iso():
            break
    return items


def pigiame(max_pages: int = 10) -> list[Item]:
    """PigiaMe jobs. Each page's JSON-LD lists its jobs with a posting time in
    Nairobi time; the cards give the real titles."""
    items = []
    for page in range(1, max_pages + 1):
        try:
            doc = get("https://www.pigiame.co.ke/jobs", params={"page": page} if page > 1 else None)
        except Exception as e:
            if page == 1:
                raise
            log.info("PigiaMe page %d: %s", page, e)
            break
        titles = {}
        for a in doc.css("a[href*='/listings/']"):
            t = a.get_all_text(strip=True)
            if t:
                titles.setdefault(a.attrib.get("href", "").split("?")[0], t)
        posts = []
        for node in doc.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(node.get_all_text() or node.text or "")
            except (ValueError, TypeError):
                continue
            stack = [data]
            while stack:  # find every JobPosting, however deep it sits
                x = stack.pop()
                if isinstance(x, list):
                    stack += x
                elif isinstance(x, dict):
                    if x.get("@type") == "JobPosting" and x.get("url"):
                        posts.append(x)
                    stack += list(x.values())
        for j in posts:
            url = j["url"].split("?")[0]
            title = titles.get(url) or ""
            title = title.title() if title.isupper() else title
            if not title or not is_tech(title, j.get("industry") or ""):
                continue
            # "2026-11-28 01:52:22" is Nairobi time (UTC+3).
            when = parse_date((j.get("datePosted") or "").replace(" ", "T") + "+03:00") if j.get("datePosted") else None
            items.append(Item(
                id=f"pigiame:{url.rstrip('/').rsplit('-', 1)[-1]}", kind="job", source="PigiaMe",
                title=title, org=((j.get("hiringOrganization") or {}).get("name") or "").strip(),
                url=url, location="Kenya", posted_at=when, type_hint=j.get("employmentType") or "",
            ))
        dates = [parse_date((j.get("datePosted") or "").replace(" ", "T") + "+03:00") or "" for j in posts]
        if not posts or min(dates) < cutoff_iso():
            break
    return items


JOBRAPIDO_SEARCHES = ["software developer", "software engineer", "data analyst", "data engineer",
                      "devops", "web developer", "IT support", "network engineer", "cyber security"]


def jobrapido() -> list[Item]:
    """Jobrapido Kenya search results; each result's data sits in a JSON attribute."""
    items: dict[str, Item] = {}
    for q in JOBRAPIDO_SEARCHES:
        try:
            doc = get("https://ke.jobrapido.com/", params={"w": q, "l": "kenya"})
        except Exception as e:
            log.warning("Jobrapido '%s' failed: %s", q, e)
            continue
        for node in doc.css("[data-advert]"):
            try:
                a = json.loads(node.attrib["data-advert"])
            except (ValueError, KeyError):
                continue
            if a.get("isSponsored") or not a.get("advertId") or not is_tech(a.get("title") or ""):
                continue
            items.setdefault(a["advertId"], Item(
                id=f"jobrapido:{a['advertId']}", kind="job", source="Jobrapido",
                title=_text(a["title"]), org=_text(a.get("company")),
                url=a.get("openAdvertUrl") or "", location=_with_kenya(a.get("location") or ""),
                posted_at=_myjobmag_date(a.get("date") or ""),
            ))
    return [i for i in items.values() if i.url]
