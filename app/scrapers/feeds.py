"""RSS parsing. Feeds are fetched with Scrapling, but parsed as XML with lxml:
Scrapling's parser is HTML-only, which mangles CDATA and <link> elements."""
from __future__ import annotations

from lxml import etree

from .fetch import get


def feed_items(url: str) -> list[dict]:
    """Returns each <item> as {tag: text}, with repeated tags (category) as lists.
    Namespaced tags (dc:creator, ...) are keyed by their local name."""
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)
    root = etree.fromstring(get(url).body, parser)
    if root is None:
        return []
    out = []
    for item in root.iter("item"):
        d: dict = {"category": []}
        for child in item:
            if not isinstance(child.tag, str):
                continue
            tag = etree.QName(child).localname.lower()
            text = (child.text or "").strip()
            if tag == "category":
                d["category"].append(text)
            elif tag not in d:
                d[tag] = text
        out.append(d)
    return out
