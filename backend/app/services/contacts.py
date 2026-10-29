import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Job, RecruiterContact
from .discovery import USER_AGENT, html_links, html_to_text

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NAME_BEFORE_RE = re.compile(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})\s*(?:[-–,:(<]|\bat\b|\bemail\b)?\s*$")
SKIP_PARTS = ("noreply", "no-reply", "donotreply", "example.com", "sentry", "unsubscribe", "privacy@", "support@", "@2x", ".png", ".jpg")
RECRUITER_WORDS = re.compile(r"recruit|talent|hiring|hr\b|people|careers|jobs|apply|application", re.IGNORECASE)

_robots: dict[str, RobotFileParser] = {}


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in _robots:
        rp = RobotFileParser()
        try:
            rp.set_url(base + "/robots.txt")
            rp.read()
        except Exception:
            rp = None  # type: ignore[assignment]
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def find_emails(text: str) -> list[dict]:
    """Emails that are literally in the text, with a name when one is written right before it."""
    found: list[dict] = []
    seen: set[str] = set()
    for m in EMAIL_RE.finditer(text):
        email = m.group(0).strip(".").lower()
        if email in seen or any(part in email for part in SKIP_PARTS):
            continue
        seen.add(email)
        before = text[max(0, m.start() - 60) : m.start()]
        name_match = NAME_BEFORE_RE.search(before.strip())
        name = name_match.group(1) if name_match else ""
        context = text[max(0, m.start() - 120) : m.end() + 60]
        found.append(
            {
                "email": email,
                "name": name,
                "role": "recruiter" if RECRUITER_WORDS.search(context) else "",
                "confidence": 0.9 if RECRUITER_WORDS.search(context) else 0.7,
            }
        )
    return found


def fetch_page(url: str) -> str:
    if not allowed_by_robots(url):
        return ""
    time.sleep(config.SOURCE_REQUEST_DELAY_SECONDS)
    try:
        response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)
    except httpx.HTTPError:
        return ""
    if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
        return ""
    return response.text


def extract_contacts(db: Session, job: Job, fetch_source_page: bool = True) -> list[RecruiterContact]:
    """Only emails that are published in the listing or on its page. Nothing is guessed."""
    db.query(RecruiterContact).filter(RecruiterContact.job_id == job.id).delete()
    now = datetime.now(timezone.utc)
    records: list[RecruiterContact] = []

    candidates = [(c, job.canonical_url, "listing text from the source API") for c in find_emails(job.description)]
    if fetch_source_page:
        html = fetch_page(job.canonical_url)
        if html:
            page_text = html_to_text(html) + "\n" + "\n".join(l for l in html_links(html) if l.lower().startswith("mailto:"))
            page_text = page_text.replace("mailto:", " ")
            for c in find_emails(page_text):
                candidates.append((c, job.canonical_url, "listing page"))

    seen: set[str] = set()
    for c, source_url, where in candidates:
        if c["email"] in seen:
            continue
        seen.add(c["email"])
        records.append(
            RecruiterContact(
                job_id=job.id,
                name=c["name"],
                email=c["email"],
                role=c["role"],
                status="PUBLICLY_LISTED",
                source_url=source_url,
                retrieved_at=now,
                confidence=c["confidence"],
                notes=f"Found in the {where}.",
            )
        )
    if not records:
        records.append(
            RecruiterContact(
                job_id=job.id,
                status="NOT_FOUND",
                source_url=job.canonical_url,
                retrieved_at=now,
                confidence=0,
                notes="No email address is published in the listing or on its page. Apply through the source link.",
            )
        )
    db.add_all(records)
    db.commit()
    return records


def mark_bounced(db: Session, email: str, detail: str) -> None:
    for contact in db.scalars(select(RecruiterContact).where(RecruiterContact.email == email)):
        contact.status = "BOUNCED"
        contact.notes = f"Bounce observed: {detail[:300]}"
    db.commit()
