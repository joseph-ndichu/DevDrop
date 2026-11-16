"""All page fetching goes through Scrapling's fast HTTP fetcher, which sends a
browser-like TLS fingerprint and headers."""
from __future__ import annotations

from scrapling.fetchers import Fetcher


class FetchError(RuntimeError):
    pass


def get(url: str, params: dict | None = None, timeout: int = 30):
    page = Fetcher.get(url, params=params, timeout=timeout, stealthy_headers=True)
    if page.status != 200:
        raise FetchError(f"{url} returned HTTP {page.status}")
    return page
