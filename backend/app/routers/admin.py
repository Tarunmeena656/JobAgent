from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import AgentRun, Application, AuditLog, JobSource, User
from ..schemas import AdminUserOut, AdminUserUpdateIn, AuditOut, HealthOut, SourceOut, SourceUpdateIn
from ..security import require_admin
from ..services import audit, discovery
from ..services.llm import get_llm

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
def users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = []
    for user in db.scalars(select(User).order_by(User.created_at.desc())):
        out = AdminUserOut.model_validate(user)
        out.applications = db.scalar(select(func.count()).select_from(Application).where(Application.user_id == user.id)) or 0
        rows.append(out)
    return rows


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, body: AdminUserUpdateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    audit.log(db, admin.id, "admin_user_update", "user", user.id, changes)
    return AdminUserOut.model_validate(user)


@router.get("/sources", response_model=list[SourceOut])
def sources(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return discovery.ensure_sources(db)


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, body: SourceUpdateIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    source = db.get(JobSource, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(source, key, value)
    db.commit()
    audit.log(db, admin.id, "admin_source_update", "job_source", source.id, changes)
    return source


@router.get("/health", response_model=HealthOut)
def health(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        db.execute(text("select 1"))
        database = "ok"
    except Exception as err:  # noqa: BLE001
        database = f"error: {err}"
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    runs = {status: n for status, n in db.execute(select(AgentRun.status, func.count()).where(AgentRun.created_at >= since).group_by(AgentRun.status))}
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        database=database,
        llm_provider=get_llm().name,
        email_provider=config.EMAIL_PROVIDER,
        sources=[SourceOut.model_validate(s) for s in discovery.ensure_sources(db)],
        runs_last_24h=runs,
    )


@router.get("/audit-logs", response_model=list[AuditOut])
def audit_logs(limit: int = Query(default=100, ge=1, le=500), admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
