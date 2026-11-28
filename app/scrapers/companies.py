"""Jobs straight from tech companies' own career boards.

Most tech companies post jobs through an applicant-tracking system, and these
publish free, official JSON job-board APIs: Greenhouse, Lever, Ashby, Workable
and Breezy. This is where listings originate (LinkedIn and others
re-list them later), and each says exactly when the job was published.

Which companies to check is configured under `companies:` in sources.yaml.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor

from ..models import Item, cutoff_iso, parse_date
from ..tech import is_tech
from .fetch import get

log = logging.getLogger(__name__)

# Big companies' boards can be several MB; fetched 12 at a time, 30 s isn't always enough.
BOARD_TIMEOUT = 60

_MODES = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site", "inoffice": "On-site", "office": "On-site"}


def _mode(value) -> str:
    """'OnSite' / 'on-site' / 'In office' / 'Remote' / 'hybrid' -> Remote, Hybrid or On-site."""
    return _MODES.get(re.sub(r"[\s_-]", "", str(value or "")).lower(), "")


def _fresh(item: Item) -> bool:
    return bool(item.posted_at) and item.posted_at >= cutoff_iso()


# ---------- one function per platform: (slug, company name) -> Items ----------

def greenhouse(slug: str, name: str) -> list[Item]:
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=BOARD_TIMEOUT).json()
    items = []
    for j in data.get("jobs", []):
        # first_published = when the job went live; updated_at changes on every edit.
        meta = {m.get("name", "").lower(): m.get("value") for m in j.get("metadata") or []}
        mode = _mode(meta.get("workplace type") or meta.get("location type") or meta.get("remote"))
        items.append(Item(
            id=f"greenhouse:{slug}:{j['id']}", kind="job", source="Company boards",
            title=j["title"].strip(), org=j.get("company_name") or name, url=j["absolute_url"],
            location=(j.get("location") or {}).get("name", ""),
            posted_at=parse_date(j.get("first_published")), mode_hint=mode,
        ))
    return items


def lever(slug: str, name: str) -> list[Item]:
    data = get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=BOARD_TIMEOUT).json()
    items = []
    for j in data if isinstance(data, list) else []:
        cats = j.get("categories") or {}
        items.append(Item(
            id=f"lever:{slug}:{j['id']}", kind="job", source="Company boards",
            title=j["text"].strip(), org=name, url=j["hostedUrl"],
            location=cats.get("location") or ", ".join(cats.get("allLocations") or []),
            posted_at=parse_date(j.get("createdAt")),
            tags=[t for t in [cats.get("team"), cats.get("department")] if t][:2],
            type_hint=cats.get("commitment") or "", mode_hint=_mode(j.get("workplaceType")),
        ))
    return items


def ashby(slug: str, name: str) -> list[Item]:
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=BOARD_TIMEOUT).json()
    items = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        mode = _mode(j.get("workplaceType")) or ("Remote" if j.get("isRemote") else "")
        items.append(Item(
            id=f"ashby:{slug}:{j['id']}", kind="job", source="Company boards",
            title=j["title"].strip(), org=name, url=j.get("jobUrl") or j.get("applyUrl") or "",
            location=j.get("location") or "", posted_at=parse_date(j.get("publishedAt")),
            tags=[t for t in [j.get("department")] if t],
            type_hint=re.sub(r"(?<=[a-z])(?=[A-Z])", " ", j.get("employmentType") or ""),  # FullTime -> Full Time
            mode_hint=mode,
        ))
    return items


def workable(slug: str, name: str) -> list[Item]:
    data = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}").json()
    items = []
    for j in data.get("jobs", []):
        # Workable only gives a date. Midnight UTC is the earliest it could have been
        # posted, so the 48-hour check can only err on the side of dropping it.
        loc = ", ".join(p for p in [j.get("city"), j.get("country")] if p)
        items.append(Item(
            id=f"workable:{slug}:{j['shortcode']}", kind="job", source="Company boards",
            title=j["title"].strip(), org=name, url=j.get("url") or j.get("shortlink") or "",
            location=loc, posted_at=parse_date(j.get("published_on") or j.get("created_at")),
            tags=[t for t in [j.get("department")] if t],
            type_hint=j.get("employment_type") or "", level_hint=j.get("experience") or "",
            mode_hint="Remote" if j.get("telecommuting") else "",
        ))
    return items


def breezy(slug: str, name: str) -> list[Item]:
    data = get(f"https://{slug}.breezy.hr/json").json()
    items = []
    for j in data if isinstance(data, list) else []:
        loc = j.get("location") or {}
        items.append(Item(
            id=f"breezy:{slug}:{j['id']}", kind="job", source="Company boards",
            title=j["name"].strip(), org=name, url=j["url"],
            location=", ".join(p for p in [loc.get("city"), (loc.get("country") or {}).get("name")] if p) or loc.get("name", ""),
            posted_at=parse_date(j.get("published_date")),
            tags=[t for t in [j.get("department")] if t],
            type_hint=(j.get("type") or {}).get("name", ""),
            mode_hint="Remote" if loc.get("is_remote") else "",
        ))
    return items


PLATFORMS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable,
             "breezy": breezy}


def company_boards(companies: dict) -> list[Item]:
    """`companies` is {platform: {slug: display name}} from sources.yaml."""
    tasks = [(PLATFORMS[p], slug, name or slug)
             for p, boards in (companies or {}).items() if p in PLATFORMS
             for slug, name in (boards or {}).items()]

    def run(task):
        fn, slug, name = task
        try:
            return [i for i in fn(slug, name) if _fresh(i) and is_tech(i.title, *i.tags)]
        except Exception as e:  # one company's board failing shouldn't sink the rest
            log.warning("%s board %r failed: %s", fn.__name__, slug, e)
            return []

    with ThreadPoolExecutor(max_workers=12) as pool:
        return [item for batch in pool.map(run, tasks) for item in batch]
