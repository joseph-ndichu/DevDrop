from .africa_boards import myjobmag, ringier_boards
from .companies import company_boards
from .earlycareer import early_career
from .events import dev_events
from .hubs import big_tech_hubs
from .jobs import arbeitnow, hn_who_is_hiring, himalayas, jobicy, wwr, yc_jobs

# Config name -> scraper.
BUILTIN = {
    "companies": company_boards,
    "hubs": big_tech_hubs,
    "early_career": early_career,
    "yc": yc_jobs,
    "hn_hiring": hn_who_is_hiring,
    "himalayas": himalayas,
    "jobicy": jobicy,
    "wwr": wwr,
    "arbeitnow": arbeitnow,
    "myjobmag": myjobmag,
    "brightermonday": ringier_boards,
    "dev_events": dev_events,
}

# Scrapers that take a section of sources.yaml as their argument.
CONFIG_SECTIONS = {company_boards: "companies", big_tech_hubs: "hubs"}

# The `source` names these scrapers give their listings. Stored listings from any
# other built-in source (one that has since been removed) are deleted on startup.
SOURCE_NAMES = {
    "Company boards", "Intern & new-grad lists", "YC Startups", "HN Who is hiring",
    "Himalayas", "Jobicy", "We Work Remotely", "Arbeitnow", "dev.events",
    "MyJobMag", "BrighterMonday", "Jobberman", "Big tech hubs",
}
