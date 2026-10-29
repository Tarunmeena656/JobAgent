from sqlalchemy.orm import Session

from ..models import Notification


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "", link: str = "") -> Notification:
    note = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(note)
    db.commit()
    return note
