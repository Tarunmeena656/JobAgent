import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Job, JobSource

USER_AGENT = "JobAgent/1.0 (+job search assistant; contact via the source listing)"

SOURCES = {
    "remotive": {"name": "Remotive", "base_url": "https://remotive.com/api/remote-jobs"},
    "arbeitnow": {"name": "Arbeitnow", "base_url": "https://www.arbeitnow.com/api/job-board-api"},
}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html or "")
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def html_links(html: str) -> list[str]:
    parser = _Text()
    parser.feed(html or "")
    return parser.links


def fingerprint(title: str, company: str) -> str:
    key = re.sub(r"[^a-z0-9]+", " ", f"{title} {company}".lower()).strip()
    return hashlib.sha1(key.encode()).hexdigest()


EXP_RE = re.compile(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years|yrs)", re.IGNORECASE)
SALARY_RE = re.compile(r"(\$|€|£|₹|usd|eur|gbp|inr)\s?([\d,.]+)\s*(k)?(?:\s*(?:-|–|to)\s*(\$|€|£|₹)?\s?([\d,.]+)\s*(k)?)?", re.IGNORECASE)
CURRENCIES = {"$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP", "₹": "INR", "inr": "INR"}


def parse_experience(text: str) -> tuple[int | None, int | None]:
    m = EXP_RE.search(text)
    if not m:
        return None, None
    low = int(m.group(1))
    high = int(m.group(2)) if m.group(2) else None
    if low > 30:
        return None, None
    return low, high


def parse_salary(text: str) -> tuple[float | None, float | None, str]:
    m = SALARY_RE.search(text or "")
    if not m:
        return None, None, ""
    try:
        low = float(m.group(2).replace(",", "")) * (1000 if m.group(3) else 1)
        high = float(m.group(5).replace(",", "")) * (1000 if m.group(6) else 1) if m.group(5) else None
    except ValueError:
        return None, None, ""
    return low, high, CURRENCIES.get(m.group(1).lower(), "")


def work_mode_of(text: str, remote_flag: bool | None) -> str:
    if remote_flag:
        return "remote"
    lowered = (text or "").lower()
    if "hybrid" in lowered:
        return "hybrid"
    if "remote" in lowered:
        return "remote"
    if remote_flag is False:
        return "onsite"
    return "unknown"


def _get(url: str, params: dict) -> dict:
    time.sleep(config.SOURCE_REQUEST_DELAY_SECONDS)
    response = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_remotive(keywords: list[str], limit: int = 50) -> list[dict]:
    rows: list[dict] = []
    for keyword in keywords or [""]:
        data = _get(SOURCES["remotive"]["base_url"], {"search": keyword, "limit": limit})
        for j in data.get("jobs", []):
            description = html_to_text(j.get("description", ""))
            posted = j.get("publication_date")
            exp_min, exp_max = parse_experience(description)
            sal_min, sal_max, currency = parse_salary(j.get("salary") or "")
            rows.append(
                {
                    "source_job_id": str(j["id"]),
                    "canonical_url": j["url"],
                    "title": j["title"],
                    "company": j.get("company_name", ""),
                    "description": description,
                    "description_html": j.get("description", ""),
                    "location": j.get("candidate_required_location", "") or "",
                    "work_mode": "remote",
                    "experience_min": exp_min,
                    "experience_max": exp_max,
                    "salary_text": j.get("salary") or "",
                    "salary_min": sal_min,
                    "salary_max": sal_max,
                    "salary_currency": currency,
                    "tags": list(j.get("tags") or []),
                    "posted_at": datetime.fromisoformat(posted).replace(tzinfo=timezone.utc) if posted else None,
                    "posted_at_verified": bool(posted),
                }
            )
    return rows


def fetch_arbeitnow(keywords: list[str], pages: int = 2) -> list[dict]:
    rows: list[dict] = []
    needles = [k.lower() for k in keywords if k]
    for page in range(1, pages + 1):
        data = _get(SOURCES["arbeitnow"]["base_url"], {"page": page})
        for j in data.get("data", []):
            haystack = f"{j.get('title', '')} {' '.join(j.get('tags') or [])} {j.get('description', '')}".lower()
            if needles and not any(n in haystack for n in needles):
                continue
            description = html_to_text(j.get("description", ""))
            exp_min, exp_max = parse_experience(description)
            sal_min, sal_max, currency = parse_salary(description[:3000])
            created = j.get("created_at")
            rows.append(
                {
                    "source_job_id": j["slug"],
                    "canonical_url": j["url"],
                    "title": j["title"],
                    "company": j.get("company_name", ""),
                    "description": description,
                    "description_html": j.get("description", ""),
                    "location": j.get("location", "") or "",
                    "work_mode": work_mode_of(description, bool(j.get("remote"))),
                    "experience_min": exp_min,
                    "experience_max": exp_max,
                    "salary_text": "",
                    "salary_min": sal_min,
                    "salary_max": sal_max,
                    "salary_currency": currency,
                    "tags": list(j.get("tags") or []) + list(j.get("job_types") or []),
                    "posted_at": datetime.fromtimestamp(int(created), tz=timezone.utc) if created else None,
                    "posted_at_verified": bool(created),
                }
            )
        if not data.get("links", {}).get("next"):
            break
    return rows


FETCHERS = {"remotive": fetch_remotive, "arbeitnow": fetch_arbeitnow}


def ensure_sources(db: Session) -> list[JobSource]:
    sources = []
    for key, meta in SOURCES.items():
        source = db.scalar(select(JobSource).where(JobSource.key == key))
        if not source:
            source = JobSource(key=key, name=meta["name"], base_url=meta["base_url"])
            db.add(source)
            db.flush()
        sources.append(source)
    db.commit()
    return sources


def upsert_jobs(db: Session, source: JobSource, rows: list[dict], posted_within_days: int | None) -> dict:
    """Insert new listings, refresh ones seen before, skip duplicates. Returns counts and the touched job ids."""
    seen_at = datetime.now(timezone.utc)
    cutoff = seen_at - timedelta(days=posted_within_days) if posted_within_days else None
    counts = {"new": 0, "updated": 0, "duplicates": 0, "too_old": 0, "job_ids": []}
    for row in rows:
        if cutoff and row["posted_at"] and row["posted_at"] < cutoff:
            counts["too_old"] += 1
            continue
        fp = fingerprint(row["title"], row["company"])
        existing = db.scalar(select(Job).where(Job.canonical_url == row["canonical_url"]))
        if existing:
            existing.retrieved_at = seen_at
            existing.status = "open"
            existing.description = row["description"] or existing.description
            counts["updated"] += 1
            counts["job_ids"].append(existing.id)
            continue
        same_posting = db.scalar(select(Job).where(Job.fingerprint == fp, Job.status == "open"))
        if same_posting:
            counts["duplicates"] += 1
            counts["job_ids"].append(same_posting.id)
            continue
        job = Job(
            source_id=source.id,
            source_job_id=row["source_job_id"],
            canonical_url=row["canonical_url"],
            fingerprint=fp,
            title=row["title"][:300],
            company=row["company"][:200],
            description=row["description"],
            location=row["location"][:300],
            work_mode=row["work_mode"],
            experience_min=row["experience_min"],
            experience_max=row["experience_max"],
            salary_text=row["salary_text"][:200],
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
            salary_currency=row["salary_currency"],
            tags=row["tags"][:30],
            posted_at=row["posted_at"],
            posted_at_verified=row["posted_at_verified"],
            retrieved_at=seen_at,
        )
        db.add(job)
        db.flush()
        counts["new"] += 1
        counts["job_ids"].append(job.id)
    db.commit()
    return counts


def verify_job(job: Job) -> str:
    """Re-check the listing URL. Only a definite 404/410 marks it expired."""
    try:
        time.sleep(config.SOURCE_REQUEST_DELAY_SECONDS)
        response = httpx.get(job.canonical_url, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)
    except httpx.HTTPError:
        return job.status
    if response.status_code in (404, 410):
        return "expired"
    if response.status_code == 200:
        lowered = response.text.lower()
        if "this job is no longer available" in lowered or "job has expired" in lowered or "position has been filled" in lowered:
            return "expired"
        return "open"
    return job.status
