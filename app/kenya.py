"""Works out whether a listing is in Kenya, or remote and open to people in Kenya."""
from __future__ import annotations

import re

# "Kenya", its main towns, and the KE code as job boards write it ("Nairobi, KE").
_IN_KENYA = re.compile(
    r"\b(kenya|nairobi|mombasa|kisumu|nakuru|eldoret|thika|machakos|kiambu|westlands|"
    r"upper hill|karen|kilimani|gigiri)\b", re.I)
# The code only counts in capitals right next to a separator, never as part of a word.
_KE_CODE = re.compile(r"(?:^|[,/|(]\s*)KE(?=\s*(?:$|[,/|)]))")

# Remote jobs open to Kenya: worldwide, or a region that includes Kenya. "Africa"
# counts on its own or as East Africa, but not South/North/West Africa.
_OPEN_TO_KENYA = re.compile(
    r"\b(worldwide|anywhere|global(ly)?|emea|all countries|international)\b|"
    r"(?<!south )(?<!north )(?<!west )(?<!southern )(?<!northern )(?<!western )\bafrica\b", re.I)


def in_kenya(text: str) -> bool:
    return bool(_IN_KENYA.search(text or "") or _KE_CODE.search(text or ""))


def kenya_scope(location: str, work_mode: str, remote_from: str = "") -> str:
    """'in'      the job or event is in Kenya (on-site, hybrid, or remote from Kenya)
    'remote'  remote and open to people in Kenya (worldwide, EMEA, Africa)
    ''        neither"""
    if in_kenya(location):
        return "in"
    if work_mode in ("Remote", "Online") and (not remote_from or remote_from == "Worldwide"
                                              or _OPEN_TO_KENYA.search(location or "")):
        return "remote"
    return ""
