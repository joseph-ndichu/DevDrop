"""Tech event sources.

Only sources that say *when an event was posted* qualify, because the app keeps
just what was posted in the last 48 hours. Luma, Meetup-style calendars,
Devpost and Devfolio publish when an event happens but not when it was listed,
so they're not used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import Item, iso, parse_date
from .feeds import feed_items

_HAPPENING = re.compile(
    r"is happening on (?P<date>[A-Z][a-z]+ \d{1,2}, \d{4})(?:,? (?P<online>Online)| in (?P<place>.+?))\.\s*More",
    re.S,
)


def dev_events() -> list[Item]:
    """dev.events: developer conferences, meetups and hackathons worldwide.
    Each RSS item's pubDate is when the event was added to the site."""
    items = []
    for d in feed_items("https://dev.events/rss.xml"):
        title = d.get("title", "")
        link = d.get("link", "")
        desc = d.get("description", "")
        if not title or not link.startswith("http"):
            continue
        starts_at, location, online = None, "", False
        m = _HAPPENING.search(desc)
        if m:
            try:
                starts_at = iso(datetime.strptime(m["date"], "%B %d, %Y").replace(tzinfo=timezone.utc))
            except ValueError:
                pass
            online = bool(m["online"])
            location = "Online" if online else m["place"].strip()
            # "Islamabad, Pakistan, Asia" -> drop the trailing continent
            location = re.sub(r",\s*(Asia|Europe|Africa|North America|South America|Oceania)$", "", location)
        items.append(Item(
            id=f"devevents:{link.rstrip('/').rsplit('/', 1)[-1]}", kind="event", source="dev.events",
            title=title, url=link, location=location, remote=online,
            posted_at=parse_date(d.get("pubdate")),
            starts_at=starts_at,
            tags=[c for c in d["category"] if c][:3],
        ))
    return items
