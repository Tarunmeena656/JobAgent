import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Resume, User
from ..schemas import ResumeOut, ResumeReviewIn
from ..security import current_user
from ..services import audit, resume_parser
from ..services.llm import get_llm
from ..services.orchestrator import rematch_in_background, run_agent
from ..skills import normalize_list
from .profile import get_profile

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

ALLOWED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def owned_resume(resume_id: int, user: User, db: Session) -> Resume:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    return resume


@router.post("/upload", response_model=ResumeOut, status_code=201)
def upload(file: UploadFile = File(...), label: str = Form("General"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    suffix = ALLOWED.get(file.content_type or "") or (Path(file.filename or "").suffix.lower() if Path(file.filename or "").suffix.lower() in (".pdf", ".docx") else None)
    if not suffix:
        raise HTTPException(415, "Upload a PDF or DOCX file")
    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Resume must be under 5 MB")

    folder = config.STORAGE_DIR / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)

    resume = Resume(user_id=user.id, label=label.strip()[:120] or "General", filename=file.filename or f"resume{suffix}", content_type=file.content_type or "", storage_path=str(path))
    db.add(resume)
    db.commit()

    def parse() -> dict:
        text = resume_parser.extract_text(path, resume.content_type)
        parsed, usage = resume_parser.parse_resume(text, get_llm())
        resume.text = text
        resume.parsed = parsed
        db.commit()
        return {"skills": len(parsed["skills"]), "experience_entries": len(parsed["experience"]), "chars": len(text), "_llm": usage}

    run = run_agent(db, user.id, "resume_parser", {"resume_id": resume.id, "filename": resume.filename}, parse)
    if run.status == "failed":
        raise HTTPException(422, f"Could not read the file: {run.error}")
    audit.log(db, user.id, "resume_upload", "resume", resume.id, {"filename": resume.filename})
    return resume


@router.get("", response_model=list[ResumeOut])
def list_resumes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())).all()


@router.get("/{resume_id}", response_model=ResumeOut)
def read(resume_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return owned_resume(resume_id, user, db)


@router.get("/{resume_id}/file")
def download(resume_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    resume = owned_resume(resume_id, user, db)
    return FileResponse(resume.storage_path, filename=resume.filename, media_type=resume.content_type or "application/octet-stream")


@router.patch("/{resume_id}", response_model=ResumeOut)
def review(resume_id: int, body: ResumeReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The user corrects what the parser got wrong, approves it, and can push it into the profile."""
    resume = owned_resume(resume_id, user, db)
    if body.parsed is not None:
        parsed = dict(resume.parsed)
        parsed.update(body.parsed)
        if "skills" in body.parsed:
            parsed["skills"] = normalize_list(parsed.get("skills") or [])
        resume.parsed = parsed
    if body.label:
        resume.label = body.label.strip()[:120]
    if body.approve:
        resume.status = "approved"
    if body.apply_to_profile:
        profile = get_profile(db, user)
        p = resume.parsed
        profile.skills = normalize_list(p.get("skills") or [])
        profile.experience = p.get("experience") or []
        profile.education = p.get("education") or []
        profile.projects = p.get("projects") or []
        if p.get("summary"):
            profile.summary = p["summary"]
        if p.get("experience_years") is not None:
            profile.experience_years = p["experience_years"]
    db.commit()
    audit.log(db, user.id, "resume_review", "resume", resume.id, {"approve": body.approve, "apply_to_profile": body.apply_to_profile})
    if body.apply_to_profile:
        rematch_in_background(user.id)
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete(resume_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    resume = owned_resume(resume_id, user, db)
    Path(resume.storage_path).unlink(missing_ok=True)
    db.delete(resume)
    db.commit()
    audit.log(db, user.id, "resume_delete", "resume", resume_id)
