"""Works out whether a listing is in Africa, or remote and open to people in Africa."""
from __future__ import annotations

import re

# Country -> extra names: main tech cities, demonyms, ISO codes as job boards write them.
COUNTRIES: dict[str, list[str]] = {
    "Kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret", "Thika", "KE"],
    "Nigeria": ["Lagos", "Abuja", "Ibadan", "Port Harcourt", "Kano", "Enugu", "Niger Delta", "NG"],
    "South Africa": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Sandton", "Centurion", "Stellenbosch", "ZA"],
    "Egypt": ["Cairo", "Alexandria", "Giza", "EG"],
    "Ghana": ["Accra", "Kumasi", "GH"],
    "Uganda": ["Kampala", "Entebbe", "UG"],
    "Tanzania": ["Dar es Salaam", "Dodoma", "Arusha", "Zanzibar", "TZ"],
    "Rwanda": ["Kigali", "RW"],
    "Ethiopia": ["Addis Ababa", "ET"],
    "Morocco": ["Casablanca", "Rabat", "Marrakech", "Tangier", "MA"],
    "Tunisia": ["Tunis", "Sfax", "TN"],
    "Algeria": ["Algiers", "Oran", "DZ"],
    "Senegal": ["Dakar", "SN"],
    "Côte d'Ivoire": ["Ivory Coast", "Cote d'Ivoire", "Abidjan", "CI"],
    "Cameroon": ["Cameroun", "Douala", "Yaoundé", "Yaounde", "CM"],
    "Zambia": ["Lusaka", "ZM"],
    "Zimbabwe": ["Harare", "Bulawayo", "ZW"],
    "Botswana": ["Gaborone", "BW"],
    "Namibia": ["Windhoek", "NA"],
    "Mozambique": ["Maputo", "MZ"],
    "Malawi": ["Lilongwe", "Blantyre", "MW"],
    "Togo": ["Lomé", "Lome", "TG"],
    "Benin": ["Cotonou", "BJ"],
    "Gabon": ["Libreville"],
    "DR Congo": ["Democratic Republic of the Congo", "Congo, République démocratique du", "Kinshasa", "DRC"],
    "Mauritius": ["Port Louis", "MU"],
    "Somalia": ["Mogadishu"],
    "Sudan": ["Khartoum"],
    "South Sudan": ["Juba"],
    "Sierra Leone": ["Freetown"],
    "Liberia": ["Monrovia"],
    "Mali": ["Bamako"],
    "Burkina Faso": ["Ouagadougou"],
    "Niger": ["Niamey"],
    "Madagascar": ["Antananarivo"],
    "Angola": ["Luanda"],
    "Libya": ["Tripoli"],
}


def _is_code(name: str) -> bool:
    return len(name) == 2 and name.isupper()


# Per country: names and cities match case-insensitively as whole words. Two-letter
# codes must be capitals right next to a separator ("Nairobi, KE"), so ordinary
# words like "in" or "na" never count.
_PATTERNS: list[tuple[str, re.Pattern, re.Pattern | None]] = []
for _country, _names in COUNTRIES.items():
    _words = [w for w in [_country, *_names] if not _is_code(w)]
    _codes = [w for w in _names if _is_code(w)]
    _PATTERNS.append((
        _country,
        re.compile("|".join(r"\b" + re.escape(w) + r"\b" for w in _words), re.I),
        re.compile("|".join(r"(?:^|[,/|(]\s*)" + c + r"(?=\s*(?:$|[,/|)]))" for c in _codes)) if _codes else None,
    ))

# Remote jobs open to Africa: worldwide, or a region that includes Africa.
_OPEN_TO_AFRICA = re.compile(r"\b(worldwide|anywhere|global(ly)?|emea|africa|all countries|international)\b", re.I)


def countries_in(text: str) -> list[str]:
    """African countries mentioned in a location string, in order of appearance."""
    found = []
    for country, names, codes in _PATTERNS:
        m = names.search(text or "") or (codes.search(text or "") if codes else None)
        if m:
            found.append((m.start(), -len(m.group()), country))  # same spot: longer name wins
    return [c for *_, c in sorted(found)]


def africa_scope(location: str, work_mode: str, remote_from: str = "") -> tuple[str, str]:
    """Returns (country, scope):
    ("Kenya", "in")       the job or event is in Kenya (on-site, hybrid, or remote from Kenya)
    ("", "remote")        remote and open to people in Africa (worldwide, EMEA, Africa)
    ("", "")              neither
    """
    found = countries_in(location)
    if found:
        return found[0], "in"
    if work_mode in ("Remote", "Online") and (not remote_from or remote_from == "Worldwide"
                                              or _OPEN_TO_AFRICA.search(location or "")):
        return "", "remote"
    return "", ""
