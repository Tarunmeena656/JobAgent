# JobAgent – AI job search and application agent

Web app that does the research part of a job search and leaves the decisions to you. It discovers jobs
from permitted public sources, de-duplicates them, scores each one against your approved profile with an
explainable 0–100 match, extracts recruiter emails only when they are actually published, drafts
application emails from your own profile facts, and tracks applications, reminders and interviews.

**Nothing is sent without you.** A draft becomes an email only after you approve exactly that recipient,
subject, body and attachments, and the send endpoint checks for that approval record before it does
anything. Any edit after approval needs a fresh approval.

Stack: React 19 + TypeScript + Tailwind (Vite) · Python 3.12 + FastAPI + SQLAlchemy · PostgreSQL ·
custom state-machine orchestrator · LLM behind a provider abstraction (Anthropic or a deterministic mock).

## What is in the box

| Area                 | What it does                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| Auth & profile       | Register, sign in/out, password reset, profile with skills, experience, CTC, notice, locations, work mode, target roles, account deletion |
| Resume parsing       | PDF/DOCX upload, text extraction, heuristic parser (contact, skills, dated experience, education, projects), review screen, multiple labelled versions, owner-only access |
| Job discovery agent  | Remotive and Arbeitnow public APIs (no key, terms allow use), normalisation, fingerprint de-duplication, source URL and retrieval time on every job, posting date only when the source gives one, expiry check on request |
| Resume matching agent| Weighted factors: skills (weight shrinks when the listing names few technologies), role relevance, experience, location/work mode, salary (same currency only), qualifications. Unknown inputs are reported as unknown, never as gaps. Caps for unrelated titles and listings with no technologies |
| Contact extraction   | Emails literally present in the listing text or page (robots.txt respected), statuses PUBLICLY_LISTED / NOT_FOUND / BOUNCED (only on an observed bounce), source URL, timestamp and confidence stored. Nothing is inferred from names or domains |
| Email writer agent   | Template built from profile facts, matched skills and evidence lines from your projects; three tones; per-section regeneration; optional LLM rewrite that is rejected if it mentions a skill the profile lacks |
| Approval and sending | Drafts → approve (hash of content) → send through console (default, logs only) or SMTP; send status, provider message id and errors recorded; duplicate sends refused; failures never marked as sent; bounces mark the contact |
| Tracker              | Statuses from Saved to Closed, events history, notes, interview date, automatic follow-up reminder after sending, duplicate-application protection, manual corrections |
| Dashboard & search   | Counts for the selected range, high matches, jobs with public emails, drafts awaiting approval, status breakdown, upcoming reminders; job list filters and sorts by score, company, location, work mode, experience, salary, source, verified date |
| Notifications        | In-app: high match, draft awaiting approval, send failed, source failed; follow-ups show on the dashboard |
| Orchestrator         | Every agent step is an `agent_runs` row with input, output, attempts (retry with backoff), timing, tokens and cost; the search pipeline runs in the background and can be re-run |
| Admin                | Users (enable/disable, role, daily LLM limit), sources (enable/disable, last status), health, audit log |

## Screenshots

| Sign in | Dashboard |
| --- | --- |
| ![Sign in](docs/screenshots/login.png) | ![Dashboard](docs/screenshots/dashboard.png) |

| Jobs with match scores | Why this score, contacts, draft |
| --- | --- |
| ![Jobs](docs/screenshots/jobs.png) | ![Job detail](docs/screenshots/job-detail.png) |

| Application: draft, approve, send, track | Agent activity and notifications |
| --- | --- |
| ![Application](docs/screenshots/application-detail.png) | ![Agent activity](docs/screenshots/activity.png) |

## Running it

### Docker (everything)

```bash
docker compose up --build
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs

Then register, or seed demo accounts:

```bash
docker compose exec api python scripts/seed.py
# admin@jobagent.dev / Admin123!   demo@jobagent.dev / Demo1234!  (demo has a filled profile)
```

### Without Docker

Needs Python 3.12+, Node 22 and a PostgreSQL you can reach.

```bash
# database
createdb jobagent            # or: docker run -d -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16

# backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # source .venv/bin/activate on mac/linux
pip install -r requirements-dev.txt
copy .env.example .env                               # set DATABASE_URL
python scripts/seed.py                               # tables + demo accounts
uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                                          # http://localhost:5173, proxies /api to :8000
# API_TARGET=http://127.0.0.1:8010 npm run dev    # proxy to an API on another port
```

### Tests

```bash
cd backend && pytest          # 19 tests: unit (parser, matcher, contacts, drafts) + API flows against a test database
cd frontend && npm run build  # typecheck + production build
```

The API tests use `TEST_DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@127.0.0.1:5435/jobagent_test`)
and drop/recreate the tables for every test.

## Configuration

| Variable               | Default                                    | Notes                                                           |
| ---------------------- | ------------------------------------------ | --------------------------------------------------------------- |
| `DATABASE_URL`         | `postgresql+psycopg://postgres:postgres@127.0.0.1:5432/jobagent` | SQLAlchemy URL                            |
| `JWT_SECRET`           | change-me                                  | sign-in tokens, 24 h                                            |
| `STORAGE_DIR`          | `./storage`                                | uploaded resumes, one folder per user                           |
| `CORS_ORIGINS`         | `http://localhost:5173`                    | comma separated                                                 |
| `LLM_PROVIDER`         | `mock`                                     | `mock` = no model calls; `anthropic` needs `ANTHROPIC_API_KEY` |
| `LLM_MODEL`            | `claude-opus-5-5`                          |                                                                 |
| `EMAIL_PROVIDER`       | `console`                                  | `console` logs the email; `smtp` sends with the `SMTP_*` values |
| `SOURCE_REQUEST_DELAY_SECONDS` | `1`                                | pause between calls to a job source                             |

With the mock provider everything still works: parsing, scoring, contact extraction and drafting are
rule and template based. The model, when enabled, only rewrites the draft in the chosen tone, adds a
nicer score explanation and enriches resume parsing, and each of those has a deterministic fallback.
The score itself never comes from the model.

## API

All routes are under `/api`, JSON, bearer token from register/login. Interactive docs at `/docs`.

| Method | Endpoint                                        | Purpose                                           |
| ------ | ----------------------------------------------- | ------------------------------------------------- |
| POST   | `/auth/register`, `/auth/login`, `/auth/logout` | accounts                                          |
| POST   | `/auth/password-reset/request`, `/confirm`      | reset flow (link is logged without an email provider) |
| GET/PATCH/DELETE | `/profile`                            | candidate profile, account deletion               |
| POST   | `/resumes/upload`                               | multipart upload, parsed on the spot              |
| GET/PATCH/DELETE | `/resumes/{id}`, GET `/resumes/{id}/file` | review/correct/approve, apply to profile, download |
| POST   | `/jobs/search`                                  | start the discovery → match → contacts pipeline   |
| GET    | `/jobs`, `/jobs/{id}`                           | browse with filters and sorting, detail with evidence and contacts |
| POST   | `/jobs/{id}/match`, `/jobs/{id}/contacts`, `/jobs/{id}/verify` | score now, extract emails now, re-check the listing |
| POST   | `/applications/drafts`                          | generate a draft (creates the application)        |
| GET/PATCH | `/applications/drafts/{id}`, POST `/regenerate` | edit, rewrite a section                        |
| POST   | `/applications/{id}/approve`, `/applications/{id}/send` | explicit approval, then send               |
| GET/POST/PATCH | `/applications`, `/applications/{id}`  | tracker                                           |
| GET/POST/PATCH | `/applications/reminders`               | follow-ups and interviews                         |
| GET    | `/dashboard/summary?days=7`                     | dashboard numbers                                 |
| GET/POST | `/notifications`, `/notifications/{id}/read`  | in-app notifications                              |
| GET/POST | `/agent-runs`, `/agent-runs/{id}/retry`       | workflow history, re-run a search                 |
| GET/PATCH | `/admin/users`, `/admin/sources`, GET `/admin/health`, `/admin/audit-logs` | admin        |

## Layout

```
backend/app
  main.py              FastAPI app, CORS, routers, serves frontend/dist when it exists
  config.py            settings from the environment (.env is read if present)
  db.py, models.py     SQLAlchemy session and the 15 tables from the spec
  schemas.py           request/response models
  security.py          bcrypt, JWT, current_user / require_admin
  skills.py            skill dictionary with aliases, extraction from free text
  routers/             auth, profile, resumes, jobs, applications, dashboard, notifications, runs, admin
  services/
    orchestrator.py    run_agent (retries, agent_runs rows), search pipeline, background threads
    discovery.py       Remotive + Arbeitnow clients, normalisation, de-duplication, expiry check
    matching.py        the score and its explanation
    contacts.py        email extraction with provenance, robots.txt, bounce marking
    drafts.py          email sections per tone, evidence from the profile, optional LLM rewrite
    resume_parser.py   PDF/DOCX text, sections, dated experience, years
    llm.py             provider abstraction: mock | anthropic
    email_provider.py  console | smtp
    audit.py, notifications.py
backend/scripts        init_db.py, seed.py
backend/tests          conftest (test database), test_units.py, test_flow.py
frontend/src
  pages/               Login, Dashboard, Jobs, JobDetail, Applications, ApplicationDetail, Profile, Runs, Admin
  components/          Layout (nav, notifications), ui (cards, chips, fields, modal)
  index.css            theme tokens (navy brand, teal accent), base styles, button/input/card/chip classes
  api.ts, auth.tsx, hooks.ts, format.ts, types.ts
docker-compose.yml     db + api + web (nginx)
docs/screenshots       the images above
```

## Design notes

- **Permissions and validation live in ordinary code.** Every router checks ownership; the send endpoint
  verifies an approval record whose content hash matches the draft; the score is computed by
  `matching.py`, not by a model.
- **Provenance everywhere.** Jobs keep source, source id, canonical URL and retrieval time; contacts keep
  source URL, time, status and confidence; sends keep provider and message id; every agent step is a
  run row.
- **Honest unknowns.** When the profile or the listing lacks a piece of information the factor is marked
  unknown and left out of the score instead of being counted against the candidate.
- **Background work.** Searches run in a background thread with their own database session and show up
  as agent runs. For production the same functions would move to a Celery/RQ worker on Redis; the
  orchestrator does not depend on the thread.
- **UI.** Tailwind v4. The palette lives as theme tokens in `index.css` (`brand-*` navy, `accent-*` teal, semantic
  emerald/amber/rose/sky for states). Shared classes are `@utility` blocks; the button variants sit in
  `@layer components` so a plain utility such as `md:hidden` still overrides them. Dark sidebar, sticky header,
  works down to phone width.
- **Privacy.** The model only receives skills, role titles and project lines, never email, phone or CTC.
  Resumes are stored per user and served only to their owner. Deleting the account removes the files.

## Not in this version

OAuth/OIDC sign-in, Gmail/Microsoft Graph sending (SMTP only), inbox synchronisation, pgvector semantic
search, Playwright-based crawling of career pages, Celery workers. The hooks are there: `email_provider.py`
takes a new provider, `discovery.FETCHERS` takes a new source, and `orchestrator.start_search_in_background`
is the one function a queue would replace.
