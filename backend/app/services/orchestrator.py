"""Central workflow: runs the agents in order, records every run, retries, and never sends anything."""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import AgentRun, CandidateProfile, Job, JobMatch, JobSource, User
from . import contacts, discovery, matching
from .llm import LLMResult, get_llm
from .notifications import notify

log = logging.getLogger("jobagent.orchestrator")
HIGH_MATCH = 70
RETRIES = 2


def run_agent(db: Session, user_id: int | None, agent: str, payload: dict, fn: Callable[[], dict], parent_id: int | None = None) -> AgentRun:
    """Execute one agent step with retries and backoff, recording status, timing, cost and errors."""
    run = AgentRun(user_id=user_id, parent_run_id=parent_id, agent=agent, status="running", input=payload, started_at=datetime.now(timezone.utc))
    db.add(run)
    db.commit()
    started = time.perf_counter()
    for attempt in range(1, RETRIES + 2):
        try:
            output = fn()
            usage: LLMResult | None = output.pop("_llm", None) if isinstance(output, dict) else None
            if usage:
                run.tokens_in += usage.tokens_in
                run.tokens_out += usage.tokens_out
                run.cost_usd += usage.cost_usd
            run.attempts = attempt
            run.output = output
            run.status = "succeeded"
            run.error = ""
            break
        except Exception as err:  # noqa: BLE001 - every failure must be recorded, whatever it is
            # roll back first: whatever the agent half-did is gone, then record the failure
            db.rollback()
            log.exception("agent %s failed (attempt %s)", agent, attempt)
            run.attempts = attempt
            run.error = f"{type(err).__name__}: {err}"[:2000]
            run.status = "failed"
            db.commit()
            if attempt <= RETRIES:
                time.sleep(0.5 * attempt)
    run.finished_at = datetime.now(timezone.utc)
    run.duration_ms = int((time.perf_counter() - started) * 1000)
    db.add(run)
    db.commit()
    return run


def match_jobs_for_user(db: Session, user: User, job_ids: list[int], parent_id: int | None = None) -> dict:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        return {"matched": 0, "high": 0, "skipped": "no profile"}
    llm = get_llm()
    usage = LLMResult(text="")
    high = 0
    matched = 0
    for job in db.scalars(select(Job).where(Job.id.in_(job_ids))):
        result = matching.score_job(profile, job)
        out = matching.llm_explanation(llm, job, result)
        if out:
            usage.tokens_in += out.tokens_in
            usage.tokens_out += out.tokens_out
            usage.cost_usd += out.cost_usd
        existing = db.scalar(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id))
        was_high = existing.score >= HIGH_MATCH if existing else False
        if existing:
            existing.score = result["score"]
            existing.factors = result["factors"]
            existing.strong_matches = result["strong_matches"]
            existing.gaps = result["gaps"]
            existing.unknowns = result["unknowns"]
            existing.explanation = result["explanation"]
            existing.model = llm.name if out else "rules"
        else:
            db.add(JobMatch(user_id=user.id, job_id=job.id, model=llm.name if out else "rules", **result))
        matched += 1
        if result["score"] >= HIGH_MATCH:
            high += 1
            if not was_high:
                notify(db, user.id, "high_match", f"{result['score']}/100 match: {job.title} at {job.company}", result["explanation"], f"/jobs/{job.id}")
    db.commit()
    return {"matched": matched, "high": high, "_llm": usage}


def discover(db: Session, source: JobSource, keywords: list[str], posted_within_days: int | None) -> dict:
    fetcher = discovery.FETCHERS[source.key]
    source.last_run_at = datetime.now(timezone.utc)
    try:
        rows = fetcher(keywords)
    except Exception as err:
        source.last_status = "failed"
        source.last_error = str(err)[:500]
        db.commit()
        raise
    counts = discovery.upsert_jobs(db, source, rows, posted_within_days)
    source.last_status = "ok"
    source.last_error = ""
    db.commit()
    return {"fetched": len(rows), **counts}


def search_pipeline(db: Session, user: User, keywords: list[str], posted_within_days: int | None, source_keys: list[str] | None) -> AgentRun:
    """Discovery -> matching -> contacts for the good matches. Drafts are only made when the user asks."""
    payload = {"keywords": keywords, "posted_within_days": posted_within_days, "sources": source_keys}
    pipeline = AgentRun(user_id=user.id, agent="pipeline", status="running", input=payload, started_at=datetime.now(timezone.utc))
    db.add(pipeline)
    db.commit()
    started = time.perf_counter()
    summary: dict = {"sources": {}, "job_ids": []}

    sources = [s for s in discovery.ensure_sources(db) if s.enabled and (not source_keys or s.key in source_keys)]
    for source in sources:
        run = run_agent(db, user.id, f"discovery:{source.key}", payload, lambda s=source: discover(db, s, keywords, posted_within_days), pipeline.id)
        summary["sources"][source.key] = run.output if run.status == "succeeded" else {"error": run.error}
        if run.status == "failed":
            notify(db, user.id, "source_failed", f"{source.name} could not be read", run.error[:200], "/agent-runs")
        summary["job_ids"].extend(run.output.get("job_ids", []))

    job_ids = sorted(set(summary["job_ids"]))
    summary["jobs_touched"] = len(job_ids)
    summary.pop("job_ids")
    if job_ids:
        match_run = run_agent(db, user.id, "matcher", {"jobs": len(job_ids)}, lambda: match_jobs_for_user(db, user, job_ids, pipeline.id), pipeline.id)
        summary["matching"] = match_run.output if match_run.status == "succeeded" else {"error": match_run.error}

        good = db.scalars(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id.in_(job_ids), JobMatch.score >= HIGH_MATCH)).all()

        def extract_all() -> dict:
            found = 0
            for m in good[:25]:
                job = db.get(Job, m.job_id)
                existing = db.query(contacts.RecruiterContact).filter_by(job_id=job.id).count()
                if existing:
                    continue
                records = contacts.extract_contacts(db, job)
                found += sum(1 for r in records if r.status == "PUBLICLY_LISTED")
            return {"jobs_checked": min(len(good), 25), "emails_found": found}

        contact_run = run_agent(db, user.id, "contacts", {"jobs": len(good)}, extract_all, pipeline.id)
        summary["contacts"] = contact_run.output if contact_run.status == "succeeded" else {"error": contact_run.error}

    pipeline.output = summary
    pipeline.status = "succeeded"
    pipeline.finished_at = datetime.now(timezone.utc)
    pipeline.duration_ms = int((time.perf_counter() - started) * 1000)
    db.commit()
    return pipeline


def start_search_in_background(user_id: int, keywords: list[str], posted_within_days: int | None, source_keys: list[str] | None) -> None:
    def work() -> None:
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if user:
                search_pipeline(db, user, keywords, posted_within_days, source_keys)
        except Exception:  # noqa: BLE001
            log.exception("search pipeline crashed")
        finally:
            db.close()

    threading.Thread(target=work, daemon=True).start()


def rematch_in_background(user_id: int) -> None:
    def work() -> None:
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            job_ids = [j.id for j in db.scalars(select(Job).where(Job.status == "open"))]
            if user and job_ids:
                run_agent(db, user.id, "matcher", {"jobs": len(job_ids), "reason": "profile updated"}, lambda: match_jobs_for_user(db, user, job_ids))
        except Exception:  # noqa: BLE001
            log.exception("rematch crashed")
        finally:
            db.close()

    threading.Thread(target=work, daemon=True).start()
