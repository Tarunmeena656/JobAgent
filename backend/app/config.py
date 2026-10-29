import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    """Fills os.environ from a .env file without overriding values that are already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv(Path(os.environ.get("ENV_FILE", ROOT / "backend" / ".env")))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


DATABASE_URL = env("DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/jobagent")
# hosted databases hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named
for _prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(_prefix):]
        break
JWT_SECRET = env("JWT_SECRET", "change-me-in-production")
JWT_EXPIRES_MINUTES = int(env("JWT_EXPIRES_MINUTES", "1440"))
STORAGE_DIR = Path(env("STORAGE_DIR", ROOT / "storage"))
APP_URL = env("APP_URL", "http://localhost:5173")
CORS_ORIGINS = [o for o in env("CORS_ORIGINS", "http://localhost:5173").split(",") if o]

# mock keeps everything deterministic and offline; anthropic needs ANTHROPIC_API_KEY
LLM_PROVIDER = env("LLM_PROVIDER", "mock")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
LLM_MODEL = env("LLM_MODEL", "claude-opus-5-5")

# console prints the email to the log instead of sending it; smtp needs the SMTP_* settings
EMAIL_PROVIDER = env("EMAIL_PROVIDER", "console")
SMTP_HOST = env("SMTP_HOST")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER")
SMTP_PASSWORD = env("SMTP_PASSWORD")
SMTP_FROM = env("SMTP_FROM")

SOURCE_REQUEST_DELAY_SECONDS = float(env("SOURCE_REQUEST_DELAY_SECONDS", "1"))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
