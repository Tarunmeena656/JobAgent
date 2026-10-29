"""Creates an admin and a demo job seeker with a filled profile so the app has something to show."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import CandidateProfile, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.discovery import ensure_sources  # noqa: E402

Base.metadata.create_all(engine)
db = SessionLocal()

accounts = [
    ("admin@jobagent.dev", "Admin123!", "Aditi Rao", "admin"),
    ("demo@jobagent.dev", "Demo1234!", "Vikram Mehta", "seeker"),
]
for email, password, name, role in accounts:
    if not db.scalar(select(User).where(User.email == email)):
        user = User(email=email, password_hash=hash_password(password), name=name, role=role)
        db.add(user)
        db.flush()
        profile = CandidateProfile(user_id=user.id)
        if role == "seeker":
            profile.headline = "Full-Stack Developer (Node.js, React, Python)"
            profile.summary = "Backend-leaning full-stack developer with production experience in Node.js, NestJS, React and Python/FastAPI."
            profile.skills = ["JavaScript", "TypeScript", "Node.js", "React", "NestJS", "Python", "FastAPI", "PostgreSQL", "MongoDB", "AWS", "Docker", "REST APIs"]
            profile.experience_years = 3.9
            profile.experience = [
                {"title": "Full-Stack Developer", "company": "Rootlex Technology", "start": "2025-10-01", "end": "2026-10-01", "text": "Built REST APIs with Node.js, NestJS and FastAPI, React interfaces, and AI pipelines on AWS."},
                {"title": "MERN Stack Developer", "company": "Bigscal Technologies", "start": "2023-07-01", "end": "2025-10-01", "text": "Delivered MERN applications with Stripe and Razorpay payments on AWS Lambda."},
            ]
            profile.education = [{"text": "Master of Computer Application (MCA), RGPV"}]
            profile.projects = [{"text": "Contest platform: Node.js, PostgreSQL and React with AI question generation"}, {"text": "Chat backend: Node.js, PostgreSQL and Firestore with read receipts"}]
            profile.expected_ctc = 1200000
            profile.ctc_currency = "INR"
            profile.notice_period_days = 30
            profile.preferred_locations = ["Bhopal", "Indore", "Pune", "Bengaluru", "Remote"]
            profile.work_modes = ["remote", "hybrid"]
            profile.target_roles = ["Node.js Developer", "Full Stack Developer", "Python Developer", "AI Engineer"]
        db.add(profile)
        print(f"created {role}: {email} / {password}")
ensure_sources(db)
db.commit()
db.close()
print("done")
