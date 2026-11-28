"""Decides whether a listing is a tech job, for sources that mix all kinds of roles.

Words that also mean non-tech jobs only count with a tech word next to them:
a bare "Architect" designs buildings, a bare "Security Officer" is a guard, a
bare "Infrastructure" can be roads, a bare "QA Officer" works in a factory.
"""
from __future__ import annotations

import re

_TECH = re.compile(
    r"\b("
    # --- software engineering ---
    r"engineering (manager|director|lead)|developer|dev|programmer|software|swe|sde|softwareentwicklung|"
    r"front[\s-]?end|back[\s-]?end|full[\s-]?stack|web (developer|designer|master|engineer)|webmaster|"
    r"mobile|ios|android|flutter|dart|react native|xamarin|ionic|"
    r"python|java|javascript|typescript|golang|go (developer|engineer)|rust|ruby|rails|php|laravel|"
    r"node(\.?js)?|react|vue|angular|svelte|next\.?js|nuxt|django|flask|fastapi|spring( boot)?|\.net|c#|c\+\+|"
    r"kotlin|swift|scala|elixir|erlang|haskell|clojure|perl|graphql|microservices?|api|"
    r"wordpress|shopify|magento|drupal|webflow|"
    r"game (developer|designer|programmer|engineer)|unity|unreal|"
    r"embedded|firmware|fpga|asic|vlsi|chip design|pcb design|hardware engineer|electronics engineer|robotics|iot|"
    r"blockchain|web3|smart contracts?|solidity|defi|"
    r"rpa|uipath|blue prism|low[\s-]?code|power (apps|automate|platform)|mainframe|cobol|abap|"
    r"integration (engineer|developer|specialist|architect)|implementation (engineer|consultant|specialist)|"
    # --- enterprise systems ---
    r"erp|sap|odoo|dynamics( 365)?|navision|business central|netsuite|servicenow|sharepoint|"
    r"oracle (dba|developer|consultant|database|apex|ebs|fusion|cloud)|"
    r"salesforce (developer|admin|administrator|architect|engineer|consultant)|"
    r"crm (developer|administrator|admin|specialist|consultant|analyst)|"
    # --- data & AI ---
    r"data (scientist|science|engineer|engineering|analyst|analytics|architect|steward|governance|management|"
    r"quality|manager|lead|specialist|officer|modell?er|warehouse|platform|operations|annotator|label(l)?er|"
    r"protection|privacy|centre|center)|"
    r"analytics|business intelligence|bi (developer|analyst|engineer|specialist|consultant)|power ?bi|tableau|looker|"
    r"etl|big data|hadoop|spark|snowflake|dbt|statistician|biostatistician|"
    r"quant(itative)? (analyst|developer|researcher|engineer)|"
    r"machine learning|ml|ai/ml|mlops|llmops|llm|deep learning|nlp|computer vision|generative ai|gen ?ai|"
    r"ai (engineer|engineering|developer|researcher|scientist|architect|research|infrastructure|platform|"
    r"trainer|tutor|specialist|lead|product|ops|safety|consultant|analyst|annotator)|"
    r"prompt engineer|applied scientist|research (scientist|engineer)|conversational ai|chatbot|"
    # --- security ---
    r"cyber ?security|cyber|infosec|information security|it security|ict security|network security|cloud security|"
    r"application security|appsec|product security|data security|devsecops|"
    r"security (engineer|engineering|analyst|architect|researcher|operations|software|consultant|specialist|"
    r"auditor|administrator|testing|tester|compliance|risk|governance|champion)|"
    r"soc( analyst)?|siem|pentest(er|ing)?|penetration test(er|ing)?|ethical hack(er|ing)|bug bounty|"
    r"red team|blue team|purple team|threat (intelligence|hunter|hunting|analyst|detection)|"
    r"incident response|vulnerability|malware|(digital )?forensics?|dfir|cryptograph(y|er)|zero trust|"
    r"identity (and|&) access|iam|pam|grc|governance,? risk|"
    r"(it|ict|technology|information) (audit|auditor|risk|governance|compliance)|"
    r"information systems? (audit|auditor|security)|ciso|cissp|cism|"
    # --- DevOps & cloud ---
    r"devops|sre|site reliability|platform (engineer|engineering|developer|architect|operations)|"
    r"cloud|kubernetes|docker|openshift|ansible|terraform|aws|azure|gcp|ci/cd|observability|"
    r"release (engineer|manager)|build engineer|linux|unix|vmware|virtuali[sz]ation|"
    r"storage (engineer|administrator)|backup (engineer|administrator)|middleware|windows (server|administrator)|"
    r"(it|ict|cloud|network|technology|digital|systems?) infrastructure|infrastructure (engineer|architect|as code|operations|automation)|"
    # --- IT & support ---
    r"it (support|technician|officer|manager|administrator|admin|specialist|assistant|analyst|consultant|lead|"
    r"director|coordinator|intern|attachment|engineer|operations|helpdesk|help desk|executive|trainer|"
    r"project manager|service|services|systems)|"
    r"ict|information technology|mis|help ?desk|service desk|desktop support|technical support|tech support|"
    r"end[\s-]user (support|computing)|computer (technician|operator|engineer|science)|"
    r"sysadmin|systems? (administrator|admin|analyst|engineer|support|developer|architect)|"
    r"network (engineer|administrator|admin|technician|specialist|analyst|architect|officer|support|operations)|"
    r"network technolog(y|ies)|noc|dba|database|"
    r"telecom(munication)?s? (engineer|technician|specialist)|rf engineer|transmission engineer|"
    r"fib(re|er) (optic )?(engineer|technician)|gis|"
    # --- leadership ---
    r"cto|cio|chief (technology|information|data|digital|information security|product) officer|"
    r"head of (it|ict|technology|engineering|data|product|information security|infrastructure|platform)|"
    r"(vp|vice president|director) (of )?(engineering|technology|it|data|product)|"
    r"technology (manager|officer|lead|director|consultant|analyst|specialist)|tech lead|"
    r"(software|solutions?|cloud|enterprise|data|security|systems?|technical|it|ict|network|infrastructure|"
    r"platform|integration|application|ai|ml) architect|"
    r"technical (consultant|lead|manager|program manager|project manager|specialist|analyst|writer|support)|"
    # --- design & product ---
    r"ux|ui|user research(er)?|interaction designer|product designer|visual designer|design systems?|"
    r"product (manager|management|owner|lead|analyst|operations|director|specialist)|scrum master|"
    r"agile (coach|delivery|project manager)|"
    r"(technical|it|ict|software|digital|tech) (project|program|programme|delivery) (manager|lead|coordinator|officer)|"
    r"business (systems )?analyst|digital (product|transformation|platforms?|solutions?)|"
    # --- QA & testing ---
    r"qa (engineer|analyst|tester|automation|lead|manager|specialist)|"
    r"software (quality|testing|test)|test (engineer|analyst|lead|manager|automation|architect)|"
    r"automation (tester|test|testing)|tester|sdet|uat|performance (test|tester|testing)|manual tester|"
    # --- other tech roles ---
    r"documentation engineer|developer (advocate|relations|experience)|devrel|solutions? engineer|"
    r"support engineer|application(s)? (support|analyst|engineer|specialist|developer)"
    r")\b",
    re.I,
)

# Roles that mention a tech word but aren't tech jobs.
_NOT_TECH = re.compile(
    r"\b(sales|account (executive|manager)|business development|bdr|sdr|marketing|gtm|go[\s-]to[\s-]market|customer engagement|"
    r"social media|creative|strategist|risk analyst|session director|"
    r"(business|market|partnership|community) developer|"
    r"recruit(er|ing)|talent|customer (success|support|service)|copywriter|"
    r"accountant|bookkeeper|legal|paralegal|nurse|"
    r"mechanical|civil|electrical engineer|chemical|hvac|construction)\b",
    re.I,
)

# Never tech, whatever else the title says.
_NEVER = re.compile(
    r"\b(teacher|lecturer)s?\b|(?<!\bai )\btutors?\b|\bdata (entry|clerk)\b|"
    r"\b(medical|clinical|inpatient|outpatient|revenue cycle) cod(er|ers|ing)\b|\bcoder\b.*\b(medical|inpatient|coding)\b|"
    # Guards, not information security.
    r"(?<!information )(?<!cyber )(?<!it )(?<!ict )\bsecurity (officer|guard|supervisor)s?\b",
    re.I,
)

# Clearly technical even with a word from _NOT_TECH in the title
# ("Salesforce Developer", "IT Risk Analyst", "Cybersecurity Sales... " is still sales).
_STRONG = re.compile(
    r"\b(software (engineer|engineering|developer|architect|tester|test|quality)|programmer|devops|devsecops|sre|"
    r"cyber ?security (engineer|analyst|architect)|information security (engineer|analyst|architect)|"
    r"(it|ict|technology) (risk|audit|auditor|compliance|governance)|"
    r"data (engineer|scientist|architect)|machine learning|ai (engineer|trainer|tutor)|"
    r"salesforce (developer|admin|administrator|architect|engineer)|crm (developer|administrator))\b|"
    r"(?<!business )(?<!market )(?<!partnership )(?<!community )\bdeveloper\b",
    re.I,
)


def is_tech(title: str, *extra: str) -> bool:
    if _NEVER.search(title):
        return False
    if _NOT_TECH.search(title):
        # "Sales Engineer", "Customer Success Engineer": only keep clearly technical titles.
        return bool(_STRONG.search(title))
    return bool(_TECH.search(" ".join([title, *extra])))
