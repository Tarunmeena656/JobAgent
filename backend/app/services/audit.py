from sqlalchemy.orm import Session

from ..models import AuditLog


def log(db: Session, user_id: int | None, action: str, entity_type: str = "", entity_id: int | None = None, details: dict | None = None, ip: str = "") -> None:
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}, ip=ip))
    db.commit()
