from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentRun, User
from ..schemas import AgentRunOut
from ..security import current_user
from ..services.orchestrator import start_search_in_background

router = APIRouter(prefix="/api/agent-runs", tags=["agent runs"])


@router.get("", response_model=list[AgentRunOut])
def list_runs(agent: str | None = None, limit: int = Query(default=50, ge=1, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
    if user.role != "admin":
        stmt = stmt.where(AgentRun.user_id == user.id)
    if agent:
        stmt = stmt.where(AgentRun.agent.like(f"{agent}%"))
    return db.scalars(stmt).all()


@router.get("/{run_id}", response_model=AgentRunOut)
def read(run_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if not run or (run.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Run not found")
    return run


@router.post("/{run_id}/retry", status_code=202)
def retry(run_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Re-runs a failed or finished search pipeline with the same input. Other agents are retried by their own endpoints."""
    run = db.get(AgentRun, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(404, "Run not found")
    if run.agent != "pipeline":
        raise HTTPException(400, "Only search pipelines can be retried here")
    start_search_in_background(user.id, run.input.get("keywords", []), run.input.get("posted_within_days"), run.input.get("sources"))
    return {"message": "Search restarted"}
