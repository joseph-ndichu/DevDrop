"""Internships and new-grad roles from the community-run GitHub lists that
students and early-career engineers rely on (SimplifyJobs and others).

Each list keeps its data in .github/scripts/listings.json, with a `date_posted`
timestamp per role, refreshed as new roles are found on company career pages.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import MAX_AGE_HOURS, Item, parse_date
from ..tech import is_tech
from .fetch import get

LISTS = [
    # (GitHub repo, branch, which level these roles are)
    ("SimplifyJobs/Summer2027-Internships", "dev", "Internship"),
    ("SimplifyJobs/New-Grad-Positions", "dev", "Junior"),
    ("vanshb03/New-Grad-2027", "dev", "Junior"),
]


def early_career() -> list[Item]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)).timestamp()
    items: dict[str, Item] = {}
    for repo, branch, level in LISTS:
        data = get(f"https://raw.githubusercontent.com/{repo}/{branch}/.github/scripts/listings.json",
                   timeout=60).json()
        for j in data:
            if not j.get("active", True) or not j.get("is_visible", True):
                continue
            if (j.get("date_posted") or 0) < cutoff:
                continue
            title, cat = (j.get("title") or "").strip(), j.get("category") or ""
            # The lists' categories are broad ("AI/ML/Data" includes business analysts),
            # so the title itself has to read as a tech role.
            if not is_tech(title):
                continue
            locations = j.get("locations") or []
            sponsorship = j.get("sponsorship") or ""
            item = Item(
                id=f"early:{j.get('id') or j.get('url')}", kind="job", source="Intern & new-grad lists",
                title=title, org=j.get("company_name") or "", url=j.get("url") or "",
                location=" / ".join(locations[:3]) + (f" +{len(locations) - 3} more" if len(locations) > 3 else ""),
                posted_at=parse_date(j.get("date_posted")),
                tags=[t for t in [cat, sponsorship if sponsorship not in ("", "Other") else ""] if t],
                level_hint=level, type_hint="Internship" if level == "Internship" else "Full-time",
            )
            # The same role often appears in more than one list.
            items.setdefault(f"{item.org}|{item.title}|{item.url}".lower(), item)
    return list(items.values())
