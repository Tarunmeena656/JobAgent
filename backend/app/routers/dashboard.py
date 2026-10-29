from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Application, ApplicationDraft, Job, JobMatch, RecruiterContact, Reminder, User
from ..schemas import APPLICATION_STATUSES, DashboardOut
from ..security import current_user
from ..services.orchestrator import HIGH_MATCH
from .applications import serialize_app, serialize_reminder

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardOut)
def summary(days: int = Query(default=7, ge=1, le=90), user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def count(stmt) -> int:
        return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    open_jobs = select(Job.id).where(Job.status == "open")
    my_matches = select(JobMatch.job_id).where(JobMatch.user_id == user.id)
    by_status = {s: 0 for s in APPLICATION_STATUSES}
    for status, n in db.execute(select(Application.status, func.count()).where(Application.user_id == user.id).group_by(Application.status)):
        by_status[status] = n

    reminders = db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.done.is_(False), Reminder.due_at <= now + timedelta(days=days)).order_by(Reminder.due_at).limit(10)).all()
    interviews = db.scalars(select(Application).where(Application.user_id == user.id, Application.interview_at >= now).order_by(Application.interview_at).limit(5)).all()

    return DashboardOut(
        days=days,
        jobs_today=count(open_jobs.where(Job.retrieved_at >= today)),
        jobs_in_range=count(open_jobs.where(Job.retrieved_at >= since)),
        new_matching=count(select(JobMatch.id).join(Job, Job.id == JobMatch.job_id).where(JobMatch.user_id == user.id, JobMatch.score >= 50, Job.status == "open", Job.retrieved_at >= since)),
        high_match=count(select(JobMatch.id).join(Job, Job.id == JobMatch.job_id).where(JobMatch.user_id == user.id, JobMatch.score >= HIGH_MATCH, Job.status == "open")),
        with_public_emails=count(select(RecruiterContact.job_id).where(RecruiterContact.status == "PUBLICLY_LISTED", RecruiterContact.job_id.in_(my_matches)).distinct()),
        drafts_awaiting=count(select(ApplicationDraft.id).where(ApplicationDraft.user_id == user.id, ApplicationDraft.status == "draft")),
        applications_total=sum(by_status.values()),
        by_status=by_status,
        upcoming_reminders=[serialize_reminder(db, r) for r in reminders],
        upcoming_interviews=[serialize_app(db, a) for a in interviews],
    )
