import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402,F401  (registers the tables)
from app.db import Base, engine  # noqa: E402

Base.metadata.create_all(engine)
print("tables created")
