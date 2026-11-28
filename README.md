# DevDrop

Fresh tech jobs and events for engineers, posted in the last 48 hours.

A local web app that scrapes tech jobs and tech events with
[Scrapling](https://github.com/D4Vinci/Scrapling) and shows **only listings posted
in the last 24 or 48 hours**. A listing with no posting date, or an older one,
is dropped.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8765
```

Open http://localhost:8765. The first scrape takes about a minute.

## Sources

All fetching goes through Scrapling (`app/scrapers/`). Configure them in `sources.yaml`.

| Source | Kind | How it's read |
|---|---|---|
| Company career boards (~140 tech companies on Greenhouse, Lever, Ashby, Workable, Breezy, including M-KOPA and Cellulant in Kenya) | jobs | Official public job-board APIs |
| SimplifyJobs internships + new-grad lists, New-Grad-2027 | jobs (interns, new grads) | `listings.json` in the GitHub repos |
| Y Combinator startup jobs | jobs | HTML page; Scrapling pulls the embedded JSON |
| "Ask HN: Who is hiring?" thread | jobs | Algolia HN API |
| Himalayas, Jobicy, Arbeitnow | jobs | JSON APIs |
| We Work Remotely (6 feeds), NoDesk | jobs | RSS |
| Remote OK, Remotive, Working Nomads | jobs | JSON APIs |
| DailyRemote | jobs | Listing pages, scraped with Scrapling |
| Kenya: Jobweb Kenya, Summit Recruitment & Search, NGO Jobs in Africa, Opportunities For Africans | jobs | WordPress RSS feeds |
| Kenya: MyJobMag, BrighterMonday, Corporate Staffing Services, PigiaMe, Jobrapido | jobs | Listing pages, scraped with Scrapling |
| dev.events | events | RSS (the posting date is when the event was added) |

**Company boards** are where most tech jobs originate (LinkedIn and others
re-list them later). Edit the `companies:` list in `sources.yaml` to follow the
companies you care about.

Event platforms such as Luma, Meetup, Devpost, Devfolio and GDG aren't used:
they publish when an event happens, but not when it was posted.

## Rules

- **48-hour window**: a listing is kept only if its source states a posting
  date within the last 48 hours (`app/models.py: is_fresh`). Listings in Kenya
  or open to Kenya are kept for 3 days, and the Kenya tab has a "3 days" button
  for those posted 2–3 days ago. Stored listings are deleted once they age out.
- **Tech only**: sources that mix roles are filtered by title (`app/tech.py`).
- **Categories** (`app/classify.py`): each job gets a level (Internship, Junior,
  Mid, Senior, Lead / Staff, Manager), a field (Frontend, Backend, Full-stack,
  Mobile, Data & AI, DevOps & Cloud, Security, QA & Testing, Design & Product,
  Software Engineering) and a type (Full-time, Part-time, Contract), mostly from
  the title, falling back to the source's own labels. Events get a type:
  Conference, Hackathon, Workshop, Meetup or Webinar.
- **Kenya tab** (`app/kenya.py`): jobs located in Kenya (from the location:
  "Kenya", Nairobi and other towns, or the KE code), plus remote jobs open to
  Kenya (worldwide, EMEA or Africa). Events in Kenya are shown below the jobs.
- **Refresh**: sources are re-scraped every `refresh_hours` (default 2), or on
  demand with the Refresh button.
# DevDrop
# DevDrop
