from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notification, User
from ..schemas import NotificationOut
from ..security import current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(unread_only: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(100)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    return db.scalars(stmt).all()


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = db.get(Notification, notification_id)
    if not note or note.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    note.read = True
    db.commit()
    return note


@router.post("/read-all", status_code=204)
def mark_all_read(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False)).values(read=True))
    db.commit()
