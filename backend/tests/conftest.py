import os
import shutil
from pathlib import Path

TEST_STORAGE = Path(__file__).resolve().parent / ".storage"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5435/jobagent_test")
os.environ["STORAGE_DIR"] = str(TEST_STORAGE)
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMAIL_PROVIDER"] = "console"
os.environ["SOURCE_REQUEST_DELAY_SECONDS"] = "0"
os.environ["JWT_SECRET"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)
    yield
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def register(client: TestClient, email: str = "asha@example.com", name: str = "Asha Verma", password: str = "password123") -> dict:
    res = client.post("/api/auth/register", json={"email": email, "name": name, "password": password})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


PROFILE = {
    "headline": "Node.js developer",
    "summary": "Backend developer working with Node.js, TypeScript and PostgreSQL.",
    "skills": ["Node.js", "TypeScript", "PostgreSQL", "React", "Docker"],
    "experience_years": 4,
    "experience": [{"title": "Backend Developer", "company": "Acme", "start": "2022-01-01", "end": "2026-01-01", "text": "Built Node.js services with TypeScript on PostgreSQL."}],
    "education": [{"text": "B.Tech Computer Science"}],
    "projects": [{"text": "Payments API in Node.js and TypeScript with PostgreSQL"}],
    "expected_ctc": 1500000,
    "ctc_currency": "INR",
    "notice_period_days": 30,
    "preferred_locations": ["Pune", "Remote"],
    "work_modes": ["remote", "hybrid"],
    "target_roles": ["Node.js Developer", "Full Stack Developer"],
}


def seed_job(db, email_in_description: str | None = "Send your CV to Priya Sharma - priya.sharma@acme.example", **overrides):
    from app.models import Job, JobSource
    from app.services.discovery import fingerprint

    source = db.query(JobSource).filter_by(key="test").first()
    if not source:
        source = JobSource(key="test", name="Test board", base_url="https://jobs.example")
        db.add(source)
        db.flush()
    n = db.query(Job).count() + 1
    description = (
        "We are hiring a backend engineer. Required: Node.js, TypeScript, PostgreSQL and Azure. 3+ years of experience. "
        "Bachelor degree preferred. "
    ) + (email_in_description or "")
    fields = dict(
        source_id=source.id,
        source_job_id=f"t{n}",
        canonical_url=f"https://jobs.example/{n}",
        title="Senior Node.js Developer",
        company="Acme Ltd",
        description=description,
        location="Worldwide",
        work_mode="remote",
        experience_min=3,
        tags=["backend"],
        posted_at_verified=True,
    )
    fields.update(overrides)
    fields["fingerprint"] = fingerprint(fields["title"], fields["company"])
    job = Job(**fields)
    db.add(job)
    db.commit()
    return job
