import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CandidateProfile, PasswordResetToken, User
from ..schemas import LoginIn, PasswordResetConfirm, PasswordResetRequest, RegisterIn, TokenOut, UserOut
from ..security import create_token, current_user, hash_password, verify_password
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("jobagent.auth")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), name=body.name.strip())
    db.add(user)
    db.flush()
    db.add(CandidateProfile(user_id=user.id))
    db.commit()
    audit.log(db, user.id, "register", "user", user.id, ip=request.client.host if request.client else "")
    return TokenOut(token=create_token(user), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is wrong")
    if not user.is_active:
        raise HTTPException(403, "This account is disabled")
    audit.log(db, user.id, "login", "user", user.id, ip=request.client.host if request.client else "")
    return TokenOut(token=create_token(user), user=UserOut.model_validate(user))


@router.post("/logout", status_code=204)
def logout(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # tokens are stateless; the client drops it. The event is still recorded.
    audit.log(db, user.id, "logout", "user", user.id, ip=request.client.host if request.client else "")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/password-reset/request", status_code=202)
def request_reset(body: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # same answer whether or not the email exists
    if user:
        token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
        # without an email provider the link is written to the server log
        log.info("password reset link for %s: /reset-password?token=%s", user.email, token)
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset/confirm")
def confirm_reset(body: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if not record or record.used_at or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Reset link is invalid or has expired")
    user = db.get(User, record.user_id)
    user.password_hash = hash_password(body.password)
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    audit.log(db, user.id, "password_reset", "user", user.id)
    return {"message": "Password updated"}
