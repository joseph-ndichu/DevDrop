"""Sorts listings into levels, fields and types, mostly from the title.

A source's own label (e.g. Jobicy's jobLevel, Himalayas' seniority) is used when
the title doesn't say.
"""
from __future__ import annotations

import re

from .kenya import kenya_scope
from .models import Item

LEVELS = ["Internship", "Junior", "Mid", "Senior", "Lead / Staff", "Manager", "Unspecified"]

_LEVEL_RULES = [  # first match wins, so the order matters
    ("Internship", r"\b(intern(ship)?|attach(ment|ee|é)|industrial attachment|trainee|apprentice(ship)?|working student|werkstudent|praktikum|placement student|stagiaire|stage|co-?op)\b"),
    # "Product/Project/Program Manager" is a role, not a people-manager level.
    ("Manager", r"\b(?<!product )(?<!project )(?<!program )(?<!relations )(?<!media )(?<!account )manager\b"
                r"|\b(director|head of|vp|vice president|cto|cio|chief|avp)\b"),
    ("Lead / Staff", r"\b(lead|staff|principal|distinguished|architect|tech lead)\b"),
    ("Senior", r"\b(senior|sr\.?|snr|iii|iv|expert)\b"),
    ("Junior", r"\b(junior|jr\.?|entry[\s-]?level|graduate|new grad|grad|beginner|associate (software|developer|engineer|data)|(engineer|developer) i)\b"),
    ("Mid", r"\b(mid[\s-]?level|mid|intermediate|midweight|(engineer|developer) ii)\b"),
]


def years_to_level(text: str) -> str:
    """'3+ years' -> 'Mid', 'Any (new grads ok)' -> 'Junior' (for YC's minExperience)."""
    if re.search(r"new grad|any|student", text or "", re.I):
        return "Junior"
    m = re.search(r"(\d+)", text or "")
    if not m:
        return ""
    n = int(m[1])
    return "Junior" if n <= 1 else "Mid" if n <= 4 else "Senior"

_HINT_LEVELS = [  # source labels -> level
    ("Internship", r"intern"),
    ("Manager", r"director|executive|manager"),
    ("Lead / Staff", r"lead|staff|principal"),
    ("Senior", r"senior"),
    ("Junior", r"entry|junior"),
    ("Mid", r"mid"),
]

# Bump when the tech filter or field rules change: listings are then re-fetched,
# so jobs the old rules dropped come in.
RULES_VERSION = 2

JOB_FIELDS = ["Full-stack", "Frontend", "Backend", "Mobile", "Data & AI", "DevOps & Cloud",
              "IT & Support", "Security", "QA & Testing", "Design & Product", "Software Engineering", "Other tech"]

# First match on the title wins, so the order matters.
_FIELD_RULES = [
    ("Full-stack", r"full[\s-]?stack"),
    ("Mobile", r"\b(mobile|ios|android|flutter|dart|react native|xamarin|ionic|swift|kotlin)\b"),
    ("Security", r"\b(cyber ?security|cyber|infosec|information security|appsec|devsecops|security|pentest(er|ing)?|"
                 r"penetration|soc|siem|iam|pam|grc|threat|incident response|vulnerability|malware|forensics?|dfir|"
                 r"red team|blue team|purple team|ethical hack(er|ing)|bug bounty|cryptograph(y|er)|zero trust|ciso|"
                 r"identity (and|&) access|data protection|data privacy|"
                 r"(it|ict|technology|information) (audit|auditor|risk|governance|compliance)|information systems? audit)\b"),
    ("QA & Testing", r"\b(qa|quality assurance|quality engineer|test(er|ing)?|sdet|uat)\b"),
    ("Other tech", r"\b(technical writer|documentation engineer|developer (advocate|relations|experience)|devrel)\b"),
    ("IT & Support", r"\b(help ?desk|service desk|desktop support|technical support|tech support|it support|"
                     r"end[\s-]user|it (technician|officer|manager|administrator|admin|specialist|assistant|analyst|"
                     r"consultant|lead|director|coordinator|intern|attachment|operations|executive|trainer)|"
                     r"ict|mis|information technology|computer (technician|operator)|sysadmin|"
                     r"systems? (administrator|admin|support)|network|noc|telecom(munication)?s?|rf engineer|"
                     r"transmission engineer|fib(re|er)|head of (it|ict)|cio|dba|database administrator)\b"),
    ("DevOps & Cloud", r"\b(devops|sre|site reliability|platform|infrastructure|cloud|kubernetes|docker|openshift|"
                       r"ansible|terraform|aws|azure|gcp|ci/cd|observability|release engineer|build engineer|linux|"
                       r"unix|vmware|virtuali[sz]ation|storage|backup|middleware|data cent(er|re))\b"),
    ("Software Engineering", r"\b(embedded|firmware|fpga|asic|vlsi|chip design|pcb|hardware|electronics|robotics|iot)\b"),
    ("Design & Product", r"\b(design(er)?|ux|ui|user research(er)?|product (manager|management|owner|lead|analyst|"
                         r"operations|director|specialist)|scrum master|agile|(project|program|programme|delivery) "
                         r"(manager|lead|coordinator|officer)|business (systems )?analyst|systems analyst|"
                         r"digital (products?|transformation))\b"),
    ("Data & AI", r"\b(data|machine learning|ml|mlops|ai|llm|genai|generative ai|analytics|analyst|scientist|bi|"
                  r"power ?bi|tableau|looker|etl|big data|spark|snowflake|dbt|statistician|biostatistician|quant|"
                  r"nlp|computer vision|research|prompt engineer|chatbot|gis)\b"),
    ("Frontend", r"\b(front[\s-]?end|react|vue|angular|svelte|next\.?js|nuxt|ui engineer|web developer|webmaster|"
                 r"javascript|typescript|wordpress|shopify|magento|drupal|webflow)\b"),
    ("Backend", r"\b(back[\s-]?end|api|java|golang|go|node(\.?js)?|python|php|laravel|\.net|c#|ruby|rails|django|"
                r"flask|fastapi|spring|scala|rust|c\+\+|elixir|erlang|haskell|clojure|perl|graphql|microservices?|"
                r"integration|mainframe|cobol)\b"),
    ("Software Engineering", r"\b(software|developer|programmer|engineer(ing)?|swe|sde|softwareentwicklung|"
                             r"game|unity|unreal|blockchain|web3|smart contracts?|solidity|rpa|uipath|low[\s-]?code|"
                             r"cto|architect|tech lead)\b"),
    # Enterprise systems roles that aren't developer jobs: "SAP Consultant", "ERP Officer".
    ("IT & Support", r"\b(erp|sap|odoo|dynamics|navision|business central|netsuite|crm|salesforce|servicenow|"
                     r"sharepoint|power (apps|automate|platform)|oracle|technology|it)\b"),
]


def job_field(item: Item) -> str:
    """The job's field, from its title, else its tags."""
    return _first(_FIELD_RULES, item.title, "") or _first(_FIELD_RULES, " ".join(item.tags), "Other tech")


JOB_TYPES = ["Full-time", "Part-time", "Contract", "Unspecified"]

_TYPE_RULES = [
    ("Contract", r"\b(contract(or)?|freelance|freelancer|temporary|temp|fixed[\s-]?term|\d+[\s-]?month)\b"),
    ("Part-time", r"\b(part[\s-]?time|teilzeit)\b"),
    ("Full-time", r"\b(full[\s-]?time|vollzeit|permanent|cdi)\b"),
]

EVENT_TYPES = ["Hackathon", "Conference", "Workshop", "Meetup", "Webinar", "Other"]

_EVENT_RULES = [
    ("Hackathon", r"hack(athon|day|fest)|game jam|\bjam\b|challenge|competition"),
    ("Workshop", r"workshop|masterclass|bootcamp|training|course|hands-on"),
    ("Webinar", r"webinar|livestream|online session"),
    ("Meetup", r"meetup|meet-up|user group|community day|\bdevfest\b|\bgdg\b"),
    ("Conference", r"conference|summit|\bconf\b|symposium|forum|expo|congress|days?\b|week\b|festival|\d{4}"),
]


_REMOTE = re.compile(
    r"\bremote\b|\bremotely\b|work from home|\bwfh\b|home[\s-]?office|télétravail|teletrabajo|"
    r"fully distributed|anywhere in the world|\bworldwide\b|\bwork from anywhere\b", re.I)
_NOT_REMOTE = re.compile(r"\b(no|not|non)[\s-]remote\b|\bon[\s-]?site only\b|\bin[\s-]office only\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b|\bhybride?\b|\d\s*days?\s*(a week\s*)?(in|on)[\s-]?(the\s*)?(office|site)", re.I)
_ONSITE = re.compile(r"\bon[\s-]?site\b|\bin[\s-]office\b|\bin[\s-]person\b|\bvor ort\b|\bpräsenz\b", re.I)
# Remote is allowed outright, even if hybrid is mentioned too.
_FULLY_REMOTE = re.compile(r"\b(fully|100%|full)[\s-]remote\b|\bremote[\s-]first\b|"
                           r"\bremote\s*(or|/)\s*hybrid\b|\bhybrid\s*(or|/)\s*remote\b", re.I)


def work_mode(item: Item) -> str:
    """Remote / Hybrid / On-site for jobs, Online / In person for events, or "" if unknown.

    `item.remote` arrives as the source's own claim (True for remote-only job boards
    and online events); the title and location can override it.
    """
    text = f"{item.title} | {item.location}"
    if item.kind == "event":
        return "Online" if item.remote or re.search(r"\b(online|virtual|webinar)\b", text, re.I) else "In person"
    if item.mode_hint in ("Remote", "Hybrid", "On-site"):
        return item.mode_hint  # the employer's own setting (company job boards) beats guessing
    if _NOT_REMOTE.search(text):
        return "Hybrid" if _HYBRID.search(text) else "On-site"
    if _HYBRID.search(text) and not _FULLY_REMOTE.search(text):
        return "Hybrid"  # "Boston / Hybrid", "Remote or hybrid" -> not fully remote
    if item.remote or _REMOTE.search(text):
        return "Remote"
    if _ONSITE.search(text) or item.location.strip():
        return "On-site"  # a named place and no sign of remote work
    return ""


def remote_label(item: Item) -> str:
    """Where a remote job can be done from: 'United States', or 'Worldwide'."""
    loc = re.sub(r"\b(remote|job|only)\b|[()]", " ", item.location, flags=re.I)
    loc = re.sub(r"^[\s,/|·-]+|[\s,/|·-]+$", "", re.sub(r"\s+", " ", loc))
    if not loc or re.search(r"anywhere|worldwide|global|world", loc, re.I):
        return "Worldwide"
    return loc


def set_kenya(item: Item) -> None:
    """Fills in item.kenya (see app.kenya)."""
    remote_from = remote_label(item) if item.work_mode == "Remote" else ""
    item.kenya = kenya_scope(item.location, item.work_mode, remote_from)
    if item.kind == "event" and item.kenya == "remote":
        item.kenya = ""  # online events are open to everyone, not Kenyan events


def _first(rules, text: str, default: str) -> str:
    for label, pattern in rules:
        if re.search(pattern, text, re.I):
            return label
    return default


def classify(item: Item) -> None:
    """Fills in item.level, item.category, item.job_type, item.work_mode and item.remote."""
    title = item.title
    item.work_mode = work_mode(item)
    item.remote = item.work_mode in ("Remote", "Online")
    set_kenya(item)
    if item.kind == "event":
        item.category = _first(_EVENT_RULES, " ".join([title, *item.tags]), "Other")
        item.level = item.job_type = ""
        return

    level = _first(_LEVEL_RULES, title, "")
    if not level and item.level_hint:
        level = _first(_HINT_LEVELS, item.level_hint, "")
    item.level = level or "Unspecified"

    item.category = job_field(item)

    job_type = _first(_TYPE_RULES, title, "") or _first(_TYPE_RULES, item.type_hint, "")
    item.job_type = job_type or "Unspecified"
