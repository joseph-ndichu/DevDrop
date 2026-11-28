from .companies import company_boards
from .earlycareer import early_career
from .events import dev_events
from .jobs import arbeitnow, hn_who_is_hiring, himalayas, jobicy, wwr, yc_jobs
from .kenya_boards import (brightermonday, corporate_staffing, jobrapido, jobwebkenya, myjobmag,
                           ngo_jobs_africa, opportunities_for_africans, pigiame, summit_recruitment)
from .remote_boards import dailyremote, nodesk, remoteok, remotive, working_nomads

# Config name -> scraper.
BUILTIN = {
    "companies": company_boards,
    "early_career": early_career,
    "yc": yc_jobs,
    "hn_hiring": hn_who_is_hiring,
    "himalayas": himalayas,
    "jobicy": jobicy,
    "wwr": wwr,
    "arbeitnow": arbeitnow,
    "remoteok": remoteok,
    "remotive": remotive,
    "working_nomads": working_nomads,
    "nodesk": nodesk,
    "dailyremote": dailyremote,
    "myjobmag": myjobmag,
    "brightermonday": brightermonday,
    "jobwebkenya": jobwebkenya,
    "corporate_staffing": corporate_staffing,
    "summit": summit_recruitment,
    "pigiame": pigiame,
    "jobrapido": jobrapido,
    "ngo_jobs_africa": ngo_jobs_africa,
    "opportunities_for_africans": opportunities_for_africans,
    "dev_events": dev_events,
}

# Scrapers that take a section of sources.yaml as their argument.
CONFIG_SECTIONS = {company_boards: "companies"}

# The `source` names these scrapers give their listings. Stored listings from any
# other built-in source (one that has since been removed) are deleted on startup.
SOURCE_NAMES = {
    "Company boards", "Intern & new-grad lists", "YC Startups", "HN Who is hiring",
    "Himalayas", "Jobicy", "We Work Remotely", "Arbeitnow", "dev.events",
    "Remote OK", "Remotive", "Working Nomads", "NoDesk", "DailyRemote",
    "MyJobMag", "BrighterMonday", "Jobweb Kenya", "Corporate Staffing", "Summit Recruitment",
    "PigiaMe", "Jobrapido", "NGO Jobs in Africa", "Opportunities For Africans",
}
