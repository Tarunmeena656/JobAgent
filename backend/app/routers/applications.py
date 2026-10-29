import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Application, ApplicationDraft, ApplicationEvent, Approval, EmailSend, Job, JobMatch, RecruiterContact, Reminder, Resume, User
from ..schemas import (
    APPLICATION_STATUSES,
    TONES,
    ApplicationCreateIn,
    ApplicationDetailOut,
    ApplicationOut,
    ApplicationUpdateIn,
    ApproveIn,
    DraftGenerateIn,
    DraftOut,
    DraftRegenerateIn,
    DraftUpdateIn,
    EventOut,
    ReminderIn,
    ReminderOut,
    ReminderUpdateIn,
    SendOut,
)
from ..security import current_user
from ..services import audit, contacts, drafts
from ..services.email_provider import SendError, get_email_provider
from ..services.llm import get_llm
from ..services.notifications import notify
from ..services.orchestrator import run_agent
from .profile import get_profile

router = APIRouter(prefix="/api/applications", tags=["applications"])


# ------------------------------------------------------------------ helpers


def owned_application(app_id: int, user: User, db: Session) -> Application:
    app = db.get(Application, app_id)
    if not app or app.user_id != user.id:
        raise HTTPException(404, "Application not found")
    return app


def owned_draft(draft_id: int, user: User, db: Session) -> ApplicationDraft:
    draft = db.get(ApplicationDraft, draft_id)
    if not draft or draft.user_id != user.id:
        raise HTTPException(404, "Draft not found")
    return draft


def add_event(db: Session, app: Application, actor: User | None, event_type: str, to_status: str | None = None, details: dict | None = None) -> None:
    from_status = app.status
    if to_status and to_status != app.status:
        app.status = to_status
    db.add(ApplicationEvent(application_id=app.id, actor_user_id=actor.id if actor else None, event_type=event_type, from_status=from_status, to_status=app.status, details=details or {}))
    db.commit()


def content_hash(draft: ApplicationDraft) -> str:
    raw = f"{draft.recipient_email}\n{draft.subject}\n{draft.body}\n{sorted(draft.attachments)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def serialize_app(db: Session, app: Application) -> ApplicationOut:
    match = db.scalar(select(JobMatch).where(JobMatch.user_id == app.user_id, JobMatch.job_id == app.job_id))
    latest = db.scalar(select(ApplicationDraft).where(ApplicationDraft.application_id == app.id).order_by(ApplicationDraft.created_at.desc()))
    out = ApplicationOut.model_validate(app)
    out.job_title = app.job.title
    out.company = app.job.company
    out.canonical_url = app.job.canonical_url
    out.match_score = match.score if match else None
    out.latest_draft_id = latest.id if latest else None
    out.draft_status = latest.status if latest else None
    return out


def serialize_draft(db: Session, draft: ApplicationDraft) -> DraftOut:
    out = DraftOut.model_validate(draft)
    job = db.get(Job, draft.job_id)
    out.job_title = job.title if job else ""
    out.company = job.company if job else ""
    approval = db.scalar(select(Approval).where(Approval.draft_id == draft.id).order_by(Approval.approved_at.desc()))
    out.approved = bool(approval and approval.content_hash == content_hash(draft))
    return out


def get_or_create_application(db: Session, user: User, job: Job, resume_id: int | None = None) -> Application:
    app = db.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job.id))
    if app:
        return app
    app = Application(user_id=user.id, job_id=job.id, resume_id=resume_id, status="saved")
    db.add(app)
    db.commit()
    add_event(db, app, user, "created", details={"job": job.title})
    return app


# ------------------------------------------------------------------ drafts (static paths first)


@router.post("/drafts", response_model=DraftOut, status_code=201)
def generate_draft(body: DraftGenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Builds an editable draft from the approved profile and the job. Nothing is sent here."""
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if body.tone not in TONES:
        raise HTTPException(400, f"Tone must be one of {', '.join(TONES)}")
    profile = get_profile(db, user)
    if not profile.skills and not profile.summary:
        raise HTTPException(400, "Fill in your profile (or approve a parsed resume) before drafting")
    if body.resume_id:
        resume = db.get(Resume, body.resume_id)
        if not resume or resume.user_id != user.id:
            raise HTTPException(404, "Resume not found")

    contact = None
    recipient = body.recipient_email or ""
    if body.contact_id:
        contact = db.get(RecruiterContact, body.contact_id)
        if not contact or contact.job_id != job.id or contact.status != "PUBLICLY_LISTED":
            raise HTTPException(400, "Choose a publicly listed contact for this job")
        recipient = contact.email
    if not recipient:
        listed = db.scalar(select(RecruiterContact).where(RecruiterContact.job_id == job.id, RecruiterContact.status == "PUBLICLY_LISTED").order_by(RecruiterContact.confidence.desc()))
        if listed:
            contact, recipient = listed, listed.email

    match = db.scalar(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id))
    app = get_or_create_application(db, user, job, body.resume_id)
    if body.resume_id:
        app.resume_id = body.resume_id

    def write() -> dict:
        sections = drafts.build_sections(user, profile, job, match, contact, body.tone)
        body_text = drafts.join_sections(sections)
        usage = drafts.llm_body(get_llm(), user, profile, job, match, body.tone, body_text)
        generated_by = "template"
        if usage and usage.text:
            body_text = usage.text
            generated_by = f"llm:{usage.model}"
        draft = ApplicationDraft(
            user_id=user.id,
            job_id=job.id,
            application_id=app.id,
            contact_id=contact.id if contact else None,
            recipient_email=recipient,
            subject=drafts.subject_for(user, job),
            body=body_text,
            tone=body.tone,
            attachments=[body.resume_id] if body.resume_id else ([app.resume_id] if app.resume_id else []),
            generated_by=generated_by,
        )
        db.add(draft)
        db.commit()
        return {"draft_id": draft.id, "generated_by": generated_by, "_llm": usage}

    run = run_agent(db, user.id, "email_writer", {"job_id": job.id, "tone": body.tone}, write)
    if run.status == "failed":
        raise HTTPException(500, f"Draft generation failed: {run.error}")
    draft = db.get(ApplicationDraft, run.output["draft_id"])
    add_event(db, app, user, "draft_generated", "awaiting_approval", {"draft_id": draft.id})
    notify(db, user.id, "awaiting_approval", f"Draft ready for {job.title} at {job.company}", "Review and approve it before anything is sent.", f"/applications/{app.id}")
    return serialize_draft(db, draft)


@router.get("/drafts", response_model=list[DraftOut])
def list_drafts(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(ApplicationDraft).where(ApplicationDraft.user_id == user.id).order_by(ApplicationDraft.updated_at.desc())
    if status:
        stmt = stmt.where(ApplicationDraft.status == status)
    return [serialize_draft(db, d) for d in db.scalars(stmt)]


@router.get("/drafts/{draft_id}", response_model=DraftOut)
def read_draft(draft_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serialize_draft(db, owned_draft(draft_id, user, db))


@router.patch("/drafts/{draft_id}", response_model=DraftOut)
def update_draft(draft_id: int, body: DraftUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    draft = owned_draft(draft_id, user, db)
    if draft.status == "sent":
        raise HTTPException(409, "This draft was already sent")
    changes = body.model_dump(exclude_unset=True)
    if "tone" in changes and changes["tone"] not in TONES:
        raise HTTPException(400, f"Tone must be one of {', '.join(TONES)}")
    if "attachments" in changes:
        for rid in changes["attachments"] or []:
            resume = db.get(Resume, rid)
            if not resume or resume.user_id != user.id:
                raise HTTPException(404, f"Resume {rid} not found")
    for key, value in changes.items():
        setattr(draft, key, value)
    # any edit after approval needs a fresh approval; the hash check at send time enforces it
    if draft.status == "approved":
        draft.status = "draft"
    db.commit()
    return serialize_draft(db, draft)


@router.post("/drafts/{draft_id}/regenerate", response_model=DraftOut)
def regenerate(draft_id: int, body: DraftRegenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    draft = owned_draft(draft_id, user, db)
    if draft.status == "sent":
        raise HTTPException(409, "This draft was already sent")
    tone = body.tone or draft.tone
    if tone not in TONES:
        raise HTTPException(400, f"Tone must be one of {', '.join(TONES)}")
    job = db.get(Job, draft.job_id)
    profile = get_profile(db, user)
    match = db.scalar(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id))
    contact = db.get(RecruiterContact, draft.contact_id) if draft.contact_id else None
    sections = drafts.build_sections(user, profile, job, match, contact, tone)
    if body.section == "all":
        draft.body = drafts.join_sections(sections)
    else:
        current = [p for p in draft.body.split("\n\n")]
        index = drafts.SECTIONS.index(body.section)
        if index < len(current):
            current[index] = sections[body.section]
            draft.body = "\n\n".join(p for p in current if p)
        else:
            draft.body = drafts.join_sections(sections)
    draft.tone = tone
    draft.generated_by = "template"
    if draft.status == "approved":
        draft.status = "draft"
    db.commit()
    return serialize_draft(db, draft)


# ------------------------------------------------------------------ reminders (static paths)


@router.post("/reminders", response_model=ReminderOut, status_code=201)
def create_reminder(body: ReminderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.application_id:
        owned_application(body.application_id, user, db)
    reminder = Reminder(user_id=user.id, application_id=body.application_id, kind=body.kind, due_at=body.due_at, note=body.note)
    db.add(reminder)
    db.commit()
    if body.application_id and body.kind == "follow_up":
        app = db.get(Application, body.application_id)
        if app.status == "applied":
            add_event(db, app, user, "reminder_set", "follow_up_due", {"due_at": body.due_at.isoformat()})
    return serialize_reminder(db, reminder)


def serialize_reminder(db: Session, reminder: Reminder) -> ReminderOut:
    out = ReminderOut.model_validate(reminder)
    if reminder.application_id:
        app = db.get(Application, reminder.application_id)
        out.job_title = f"{app.job.title} at {app.job.company}" if app else ""
    return out


@router.get("/reminders", response_model=list[ReminderOut])
def list_reminders(include_done: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Reminder).where(Reminder.user_id == user.id).order_by(Reminder.due_at)
    if not include_done:
        stmt = stmt.where(Reminder.done.is_(False))
    return [serialize_reminder(db, r) for r in db.scalars(stmt)]


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut)
def update_reminder(reminder_id: int, body: ReminderUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reminder = db.get(Reminder, reminder_id)
    if not reminder or reminder.user_id != user.id:
        raise HTTPException(404, "Reminder not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(reminder, key, value)
    db.commit()
    return serialize_reminder(db, reminder)


# ------------------------------------------------------------------ applications


@router.post("", response_model=ApplicationOut, status_code=201)
def create(body: ApplicationCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if body.status not in APPLICATION_STATUSES:
        raise HTTPException(400, "Unknown status")
    existing = db.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job.id))
    if existing:
        raise HTTPException(409, f"You already have an application for this job (id {existing.id})")
    app = get_or_create_application(db, user, job, body.resume_id)
    if body.status != "saved":
        add_event(db, app, user, "status_set", body.status)
    return serialize_app(db, app)


@router.get("", response_model=list[ApplicationOut])
def list_applications(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Application).where(Application.user_id == user.id).order_by(Application.updated_at.desc())
    if status:
        stmt = stmt.where(Application.status == status)
    return [serialize_app(db, a) for a in db.scalars(stmt)]


@router.get("/{app_id}", response_model=ApplicationDetailOut)
def read(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = owned_application(app_id, user, db)
    base = serialize_app(db, app)
    events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == app.id).order_by(ApplicationEvent.created_at)).all()
    draft_rows = db.scalars(select(ApplicationDraft).where(ApplicationDraft.application_id == app.id).order_by(ApplicationDraft.created_at.desc())).all()
    sends = db.scalars(select(EmailSend).where(EmailSend.draft_id.in_([d.id for d in draft_rows])).order_by(EmailSend.sent_at.desc())).all() if draft_rows else []
    return ApplicationDetailOut(**base.model_dump(), events=[EventOut.model_validate(e) for e in events], drafts=[serialize_draft(db, d) for d in draft_rows], sends=[SendOut.model_validate(s) for s in sends])


@router.patch("/{app_id}", response_model=ApplicationOut)
def update(app_id: int, body: ApplicationUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    app = owned_application(app_id, user, db)
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in APPLICATION_STATUSES:
        raise HTTPException(400, f"Status must be one of {', '.join(APPLICATION_STATUSES)}")
    if "resume_id" in changes and changes["resume_id"]:
        resume = db.get(Resume, changes["resume_id"])
        if not resume or resume.user_id != user.id:
            raise HTTPException(404, "Resume not found")
    for key, value in changes.items():
        if key != "status":
            setattr(app, key, value)
    if "interview_at" in changes and changes["interview_at"]:
        db.add(Reminder(user_id=user.id, application_id=app.id, kind="interview", due_at=changes["interview_at"], note=f"Interview: {app.job.title} at {app.job.company}"))
        if "status" not in changes:
            changes["status"] = "interview_scheduled"
    db.commit()
    if "status" in changes:
        add_event(db, app, user, "status_changed", changes["status"], {"manual": True})
    else:
        add_event(db, app, user, "updated", details={"fields": list(changes)})
    return serialize_app(db, app)


@router.post("/{app_id}/approve", response_model=DraftOut)
def approve(app_id: int, body: ApproveIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Explicit human approval of exactly this recipient, subject, body and attachments."""
    app = owned_application(app_id, user, db)
    draft = owned_draft(body.draft_id, user, db)
    if draft.application_id != app.id:
        raise HTTPException(400, "Draft belongs to another application")
    if draft.status == "sent":
        raise HTTPException(409, "Already sent")
    if not draft.recipient_email:
        raise HTTPException(400, "Add a recipient email before approving")
    if not draft.subject.strip() or not draft.body.strip():
        raise HTTPException(400, "Subject and body cannot be empty")
    db.add(Approval(draft_id=draft.id, user_id=user.id, recipient_email=draft.recipient_email, content_hash=content_hash(draft)))
    draft.status = "approved"
    db.commit()
    add_event(db, app, user, "approved", "ready_to_apply", {"draft_id": draft.id, "recipient": draft.recipient_email})
    audit.log(db, user.id, "draft_approved", "draft", draft.id, {"recipient": draft.recipient_email}, ip=request.client.host if request.client else "")
    return serialize_draft(db, draft)


@router.post("/{app_id}/send", response_model=SendOut)
def send(app_id: int, body: ApproveIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sends an approved draft. Refuses without a matching approval record, and never sends twice."""
    app = owned_application(app_id, user, db)
    draft = owned_draft(body.draft_id, user, db)
    if draft.application_id != app.id:
        raise HTTPException(400, "Draft belongs to another application")
    digest = content_hash(draft)
    approval = db.scalar(select(Approval).where(Approval.draft_id == draft.id).order_by(Approval.approved_at.desc()))
    if not approval or approval.content_hash != digest:
        raise HTTPException(403, "This draft has not been approved in its current form")
    already = db.scalar(select(EmailSend).where(EmailSend.draft_id == draft.id, EmailSend.status == "sent"))
    if already:
        raise HTTPException(409, "This draft was already sent")

    attachments = []
    for rid in draft.attachments:
        resume = db.get(Resume, rid)
        if resume and resume.user_id == user.id:
            attachments.append(Path(resume.storage_path))

    provider = get_email_provider()
    key = f"draft-{draft.id}-{digest[:16]}-{approval.id}"
    record = EmailSend(draft_id=draft.id, idempotency_key=key, provider=provider.name, status="failed", recipient_email=draft.recipient_email)
    try:
        record.provider_message_id = provider.send(draft.recipient_email, draft.subject, draft.body, attachments)
        record.status = "sent"
    except SendError as err:
        record.error = str(err)
        if err.bounced:
            contacts.mark_bounced(db, draft.recipient_email, str(err))
    db.add(record)
    db.commit()

    if record.status == "sent":
        draft.status = "sent"
        db.commit()
        add_event(db, app, user, "sent", "applied", {"draft_id": draft.id, "provider": provider.name, "message_id": record.provider_message_id})
        db.add(Reminder(user_id=user.id, application_id=app.id, kind="follow_up", due_at=datetime.now(timezone.utc) + timedelta(days=7), note=f"Follow up with {app.job.company} about {app.job.title}"))
        db.commit()
        audit.log(db, user.id, "email_sent", "draft", draft.id, {"recipient": draft.recipient_email, "provider": provider.name}, ip=request.client.host if request.client else "")
    else:
        add_event(db, app, user, "send_failed", details={"draft_id": draft.id, "error": record.error[:300]})
        notify(db, user.id, "send_failed", f"Email to {draft.recipient_email} failed", record.error[:300], f"/applications/{app.id}")
        audit.log(db, user.id, "email_send_failed", "draft", draft.id, {"error": record.error[:300]})
    return SendOut.model_validate(record)
