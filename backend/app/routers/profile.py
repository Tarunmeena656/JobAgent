import shutil

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import CandidateProfile, User
from ..schemas import ProfileIn, ProfileOut
from ..security import current_user
from ..services import audit
from ..services.orchestrator import rematch_in_background
from ..skills import normalize_list

router = APIRouter(prefix="/api/profile", tags=["profile"])


def get_profile(db: Session, user: User) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
    return profile


@router.get("", response_model=ProfileOut)
def read(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_profile(db, user)


@router.patch("", response_model=ProfileOut)
def update(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = get_profile(db, user)
    changes = body.model_dump(exclude_unset=True)
    if "skills" in changes and changes["skills"] is not None:
        changes["skills"] = normalize_list(changes["skills"])
    for key, value in changes.items():
        setattr(profile, key, value)
    db.commit()
    audit.log(db, user.id, "profile_update", "profile", profile.id, {"fields": list(changes)})
    if changes:
        rematch_in_background(user.id)
    return profile


@router.delete("", status_code=204)
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Deletes the account and everything attached to it, including uploaded files."""
    shutil.rmtree(config.STORAGE_DIR / str(user.id), ignore_errors=True)
    audit.log(db, None, "account_deleted", "user", user.id, {"email": user.email})
    db.delete(user)
    db.commit()
