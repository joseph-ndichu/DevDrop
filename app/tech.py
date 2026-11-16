"""Decides whether a listing is a tech job, for sources that mix all kinds of roles."""
from __future__ import annotations

import re

_TECH = re.compile(
    r"\b("
    # A bare "engineer" isn't enough (Value Engineer, Process Engineer): it needs a tech word.
    r"engineering manager|developer|dev|programmer|coding|software|swe|sde|softwareentwicklung|"
    r"front[\s-]?end|back[\s-]?end|full[\s-]?stack|mobile|ios|android|"
    r"devops|devsecops|sre|site reliability|platform engineer|infrastructure|cloud|"
    r"data (scientist|engineer|analyst|architect)|data science|analytics engineer|"
    # A bare "AI" isn't enough either ("Social Media & AI Manager", "AI-Native Strategist").
    r"machine learning|ml|ai/ml|ai (engineer|engineering|developer|researcher|scientist|architect|research|infrastructure|platform)|"
    r"llm|deep learning|nlp|computer vision|mlops|research scientist|"
    r"security|cyber ?security|pentest(er|ing)?|soc analyst|appsec|"
    r"qa|test automation|sdet|tester|"
    r"sysadmin|system administrator|network (engineer|administrator)|it support|"
    r"database|dba|blockchain|smart contract|solidity|embedded|firmware|"
    r"architect|tech lead|cto|ux|ui|product designer|"
    r"python|java|javascript|typescript|golang|go (developer|engineer)|rust|ruby|rails|php|laravel|"
    r"node(\.?js)?|react|vue|angular|django|\.net|c#|c\+\+|kotlin|swift|scala|"
    r"kubernetes|aws|azure|gcp|terraform|salesforce developer"
    r")\b",
    re.I,
)

# Roles that mention a tech word but aren't tech jobs.
_NOT_TECH = re.compile(
    r"\b(sales|account (executive|manager)|business development|bdr|sdr|marketing|gtm|go[\s-]to[\s-]market|customer engagement|"
    r"social media|creative|strategist|risk analyst|session director|"
    r"(business|market|partnership|community) developer|"
    r"recruit(er|ing)|talent|customer (success|support|service)|copywriter|"
    r"accountant|bookkeeper|legal|paralegal|nurse|teacher|tutor|"
    r"mechanical|civil|electrical engineer|chemical|hvac|construction)\b",
    re.I,
)


def is_tech(title: str, *extra: str) -> bool:
    text = " ".join([title, *extra])
    if _NOT_TECH.search(title):
        # "Sales Engineer", "Customer Success Engineer": only keep clearly technical titles
        # ("Salesforce Developer" yes, "Business Developer" no).
        return bool(re.search(r"\b(software|programmer|devops|sre)\b|"
                              r"(?<!business )(?<!market )(?<!partnership )(?<!community )\bdeveloper\b",
                              title, re.I))
    return bool(_TECH.search(text))
