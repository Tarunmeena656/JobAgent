from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Application, Job, JobMatch, JobSource, RecruiterContact, User
from ..schemas import ContactOut, JobDetailOut, JobListOut, JobOut, JobSearchIn, MatchOut
from ..security import current_user
from ..services import audit, contacts, discovery
from ..services.orchestrator import match_jobs_for_user, run_agent, start_search_in_background
from .profile import get_profile

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SORTS = {
    "score": JobMatch.score.desc().nulls_last(),
    "posted": Job.posted_at.desc().nulls_last(),
    "retrieved": Job.retrieved_at.desc(),
    "company": Job.company.asc(),
    "title": Job.title.asc(),
    "salary": Job.salary_max.desc().nulls_last(),
    "experience": Job.experience_min.asc().nulls_last(),
}


def serialize_job(db: Session, job: Job, user: User, match: JobMatch | None = None, detail: bool = False) -> JobOut | JobDetailOut:
    if match is None:
        match = db.scalar(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id))
    application = db.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job.id))
    public_emails = db.scalar(select(func.count()).select_from(RecruiterContact).where(RecruiterContact.job_id == job.id, RecruiterContact.status == "PUBLICLY_LISTED")) or 0
    data = {
        "id": job.id,
        "source": job.source.name if job.source else "",
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_mode": job.work_mode,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "salary_text": job.salary_text,
        "salary_currency": job.salary_currency,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "tags": job.tags,
        "posted_at": job.posted_at,
        "posted_at_verified": job.posted_at_verified,
        "retrieved_at": job.retrieved_at,
        "status": job.status,
        "canonical_url": job.canonical_url,
        "match": MatchOut.model_validate(match) if match else None,
        "public_emails": public_emails,
        "application_id": application.id if application else None,
        "application_status": application.status if application else None,
    }
    if detail:
        rows = db.scalars(select(RecruiterContact).where(RecruiterContact.job_id == job.id).order_by(RecruiterContact.confidence.desc())).all()
        return JobDetailOut(**data, description=job.description, contacts=[ContactOut.model_validate(c) for c in rows])
    return JobOut(**data)


@router.post("/search", status_code=202)
def search(body: JobSearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Starts the discovery pipeline in the background. Progress shows up under /api/agent-runs."""
    profile = get_profile(db, user)
    keywords = [k.strip() for k in body.keywords if k.strip()] or list(profile.target_roles)[:4]
    if not keywords:
        raise HTTPException(400, "Add target roles to your profile or pass keywords")
    for key in body.sources or []:
        if key not in discovery.SOURCES:
            raise HTTPException(400, f"Unknown source {key}")
    audit.log(db, user.id, "job_search", details={"keywords": keywords, "sources": body.sources})
    start_search_in_background(user.id, keywords, body.posted_within_days, body.sources)
    return {"message": "Search started", "keywords": keywords}


@router.get("", response_model=JobListOut)
def list_jobs(
    q: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    company: str | None = None,
    location: str | None = None,
    work_mode: str | None = None,
    min_experience: int | None = None,
    max_experience: int | None = None,
    salary_min: float | None = None,
    source: str | None = None,
    posted_within_days: int | None = Query(default=None, ge=1),
    verified_date_only: bool = False,
    with_emails: bool = False,
    status: str = "open",
    sort: str = "score",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Job, JobMatch).outerjoin(JobMatch, (JobMatch.job_id == Job.id) & (JobMatch.user_id == user.id)).join(JobSource, Job.source_id == JobSource.id)
    if status != "all":
        stmt = stmt.where(Job.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.company.ilike(like), Job.description.ilike(like)))
    if min_score is not None:
        stmt = stmt.where(JobMatch.score >= min_score)
    if company:
        stmt = stmt.where(Job.company.ilike(f"%{company}%"))
    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if work_mode:
        stmt = stmt.where(Job.work_mode == work_mode)
    if min_experience is not None:
        stmt = stmt.where(or_(Job.experience_min.is_(None), Job.experience_min >= min_experience))
    if max_experience is not None:
        stmt = stmt.where(or_(Job.experience_min.is_(None), Job.experience_min <= max_experience))
    if salary_min is not None:
        stmt = stmt.where(Job.salary_max >= salary_min)
    if source:
        stmt = stmt.where(JobSource.key == source)
    if posted_within_days:
        stmt = stmt.where(Job.posted_at >= datetime.now(timezone.utc) - timedelta(days=posted_within_days))
    if verified_date_only:
        stmt = stmt.where(Job.posted_at_verified.is_(True))
    if with_emails:
        stmt = stmt.where(Job.id.in_(select(RecruiterContact.job_id).where(RecruiterContact.status == "PUBLICLY_LISTED")))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(SORTS.get(sort, SORTS["score"]), Job.id.desc()).offset((page - 1) * page_size).limit(page_size)
    items = [serialize_job(db, job, user, match) for job, match in db.execute(stmt).all()]
    return JobListOut(items=items, total=total, page=page, page_size=page_size)


def get_job(job_id: int, db: Session) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/{job_id}", response_model=JobDetailOut)
def read(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serialize_job(db, get_job(job_id, db), user, detail=True)


@router.post("/{job_id}/match", response_model=JobDetailOut)
def match(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = get_job(job_id, db)
    run = run_agent(db, user.id, "matcher", {"job_id": job.id}, lambda: match_jobs_for_user(db, user, [job.id]))
    if run.status == "failed":
        raise HTTPException(500, f"Matching failed: {run.error}")
    if run.output.get("skipped"):
        raise HTTPException(400, "Complete your profile before matching")
    return serialize_job(db, job, user, detail=True)


@router.get("/{job_id}/contacts", response_model=list[ContactOut])
def list_contacts(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_job(job_id, db)
    return db.scalars(select(RecruiterContact).where(RecruiterContact.job_id == job_id).order_by(RecruiterContact.confidence.desc())).all()


@router.post("/{job_id}/contacts", response_model=list[ContactOut])
def extract(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = get_job(job_id, db)
    run = run_agent(db, user.id, "contacts", {"job_id": job.id}, lambda: {"records": len(contacts.extract_contacts(db, job))})
    if run.status == "failed":
        raise HTTPException(502, f"Contact extraction failed: {run.error}")
    return db.scalars(select(RecruiterContact).where(RecruiterContact.job_id == job_id).order_by(RecruiterContact.confidence.desc())).all()


@router.post("/{job_id}/verify", response_model=JobDetailOut)
def verify(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = get_job(job_id, db)
    job.status = discovery.verify_job(job)
    job.retrieved_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_job(db, job, user, detail=True)
