import io
import logging

from docx import Document

from app.models import AgentRun, Reminder, User
from app.services import contacts, discovery, orchestrator
from tests.conftest import PROFILE, register, seed_job


def test_register_login_and_me(client):
    headers = register(client)
    assert client.post("/api/auth/register", json={"email": "asha@example.com", "name": "x", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-pass"}).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "ASHA@example.com", "password": "password123"})
    assert ok.status_code == 200
    me = client.get("/api/auth/me", headers=headers)
    assert me.json()["name"] == "Asha Verma"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/profile", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.post("/api/auth/logout", headers=headers).status_code == 204


def test_password_reset_flow(client, caplog):
    register(client)
    with caplog.at_level(logging.INFO, logger="jobagent.auth"):
        assert client.post("/api/auth/password-reset/request", json={"email": "asha@example.com"}).status_code == 202
        assert client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"}).status_code == 202
    token = next(m.split("token=")[1] for m in caplog.messages if "token=" in m)
    assert client.post("/api/auth/password-reset/confirm", json={"token": "bad", "password": "newpassword1"}).status_code == 400
    assert client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "newpassword1"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "newpassword1"}).status_code == 200
    assert client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "another123"}).status_code == 400


def test_profile_update_normalises_skills(client):
    headers = register(client)
    res = client.patch("/api/profile", headers=headers, json={**PROFILE, "skills": ["node", "ts", "postgres"]})
    assert res.status_code == 200, res.text
    assert res.json()["skills"] == ["Node.js", "TypeScript", "PostgreSQL"]
    assert res.json()["target_roles"] == PROFILE["target_roles"]
    assert client.patch("/api/profile", headers=headers, json={"experience_years": -1}).status_code == 422


def make_docx() -> bytes:
    doc = Document()
    for line in [
        "Asha Verma",
        "asha@example.com | +91 99999 11111",
        "Skills",
        "Node.js, TypeScript, PostgreSQL, React",
        "Experience",
        "Backend Developer, Acme Jan 2022 - Present",
        "Built Node.js services with TypeScript.",
        "Education",
        "B.Tech Computer Science, 2021",
        "Projects",
        "Payments API in Node.js",
    ]:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_resume_upload_review_and_apply(client):
    headers = register(client)
    bad = client.post("/api/resumes/upload", headers=headers, files={"file": ("notes.txt", b"hello", "text/plain")})
    assert bad.status_code == 415

    res = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("asha.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"label": "Backend"},
    )
    assert res.status_code == 201, res.text
    resume = res.json()
    assert resume["status"] == "parsed"
    assert {"Node.js", "TypeScript", "PostgreSQL", "React"} <= set(resume["parsed"]["skills"])
    assert resume["parsed"]["name"] == "Asha Verma"
    assert resume["parsed"]["experience"][0]["start"] == "2022-01-01"

    review = client.patch(
        f"/api/resumes/{resume['id']}",
        headers=headers,
        json={"parsed": {"skills": ["Node.js", "TypeScript", "PostgreSQL", "Docker"], "name": "Asha V."}, "approve": True, "apply_to_profile": True},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "approved"
    assert review.json()["parsed"]["name"] == "Asha V."
    profile = client.get("/api/profile", headers=headers).json()
    assert profile["skills"] == ["Node.js", "TypeScript", "PostgreSQL", "Docker"]
    assert profile["experience_years"] and profile["experience_years"] > 3

    assert len(client.get("/api/resumes", headers=headers).json()) == 1
    assert client.get(f"/api/resumes/{resume['id']}/file", headers=headers).status_code == 200
    other = register(client, "other@example.com", "Other")
    assert client.get(f"/api/resumes/{resume['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/resumes/{resume['id']}", headers=headers).status_code == 204
    assert client.get("/api/resumes", headers=headers).json() == []


def test_jobs_matching_and_contacts(client, db, monkeypatch):
    headers = register(client)
    client.patch("/api/profile", headers=headers, json=PROFILE)
    job = seed_job(db)
    plain = seed_job(db, email_in_description=None, title="Python Developer", company="Beta Inc")
    monkeypatch.setattr(contacts, "fetch_page", lambda url: "")

    matched = client.post(f"/api/jobs/{job.id}/match", headers=headers)
    assert matched.status_code == 200, matched.text
    match = matched.json()["match"]
    assert match["score"] >= 60
    assert "Node.js" in match["strong_matches"]
    assert any(g["skill"] == "Azure" for g in match["gaps"])

    listed = client.get("/api/jobs?min_score=50&sort=score", headers=headers).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == job.id
    assert client.get("/api/jobs?q=python", headers=headers).json()["total"] == 1
    assert client.get("/api/jobs?company=acme", headers=headers).json()["total"] == 1
    assert client.get("/api/jobs?work_mode=onsite", headers=headers).json()["total"] == 0

    found = client.post(f"/api/jobs/{job.id}/contacts", headers=headers)
    assert found.status_code == 200
    assert found.json()[0]["status"] == "PUBLICLY_LISTED"
    assert found.json()[0]["email"] == "priya.sharma@acme.example"
    assert found.json()[0]["source_url"] == job.canonical_url
    none = client.post(f"/api/jobs/{plain.id}/contacts", headers=headers).json()
    assert none == [dict(none[0])] and none[0]["status"] == "NOT_FOUND"
    assert client.get("/api/jobs?with_emails=true", headers=headers).json()["total"] == 1
    detail = client.get(f"/api/jobs/{job.id}", headers=headers).json()
    assert detail["public_emails"] == 1 and len(detail["contacts"]) == 1
    assert client.get("/api/jobs/999", headers=headers).status_code == 404


def test_duplicate_listings_are_not_stored_twice(db):
    source = discovery.ensure_sources(db)[0]
    row = {
        "source_job_id": "1", "canonical_url": "https://remotive.com/j/1", "title": "Node Developer", "company": "Acme", "description": "Node.js",
        "location": "Worldwide", "work_mode": "remote", "experience_min": None, "experience_max": None, "salary_text": "", "salary_min": None,
        "salary_max": None, "salary_currency": "", "tags": [], "posted_at": None, "posted_at_verified": False,
    }
    first = discovery.upsert_jobs(db, source, [row], None)
    again = discovery.upsert_jobs(db, source, [row, {**row, "canonical_url": "https://other.example/1", "source_job_id": "2"}], None)
    assert first["new"] == 1
    assert again["updated"] == 1 and again["duplicates"] == 1 and again["new"] == 0
    assert len(set(again["job_ids"])) == 1


def test_search_pipeline_records_runs_and_notifies(client, db, monkeypatch):
    headers = register(client)
    client.patch("/api/profile", headers=headers, json=PROFILE)
    user = db.query(User).first()
    rows = [
        {
            "source_job_id": "r1", "canonical_url": "https://remotive.com/j/r1", "title": "Node.js Developer", "company": "Remote Co",
            "description": "Node.js, TypeScript, PostgreSQL, React. 2+ years. Email jobs@remoteco.example", "location": "Worldwide", "work_mode": "remote",
            "experience_min": 2, "experience_max": None, "salary_text": "", "salary_min": None, "salary_max": None, "salary_currency": "",
            "tags": ["node"], "posted_at": None, "posted_at_verified": False,
        }
    ]
    monkeypatch.setitem(discovery.FETCHERS, "remotive", lambda keywords: rows)
    monkeypatch.setitem(discovery.FETCHERS, "arbeitnow", lambda keywords: (_ for _ in ()).throw(RuntimeError("source down")))
    monkeypatch.setattr(contacts, "fetch_page", lambda url: "")

    run = orchestrator.search_pipeline(db, user, ["node"], 30, None)
    assert run.status == "succeeded"
    assert run.output["sources"]["remotive"]["new"] == 1
    assert "error" in run.output["sources"]["arbeitnow"]
    assert run.output["matching"]["matched"] == 1
    assert run.output["contacts"]["emails_found"] == 1

    agents = {r.agent: r for r in db.query(AgentRun).filter(AgentRun.parent_run_id == run.id)}
    assert agents["discovery:arbeitnow"].status == "failed" and agents["discovery:arbeitnow"].attempts == 3
    assert agents["matcher"].status == "succeeded"

    kinds = {n["kind"] for n in client.get("/api/notifications", headers=headers).json()}
    assert {"high_match", "source_failed"} <= kinds
    runs = client.get("/api/agent-runs", headers=headers).json()
    assert any(r["agent"] == "pipeline" for r in runs)
    assert client.post("/api/jobs/search", headers=headers, json={"sources": ["nope"]}).status_code == 400


def test_draft_approve_send_and_track(client, db, monkeypatch):
    headers = register(client)
    client.patch("/api/profile", headers=headers, json=PROFILE)
    job = seed_job(db)
    monkeypatch.setattr(contacts, "fetch_page", lambda url: "")
    client.post(f"/api/jobs/{job.id}/match", headers=headers)
    client.post(f"/api/jobs/{job.id}/contacts", headers=headers)

    draft_res = client.post("/api/applications/drafts", headers=headers, json={"job_id": job.id, "tone": "friendly"})
    assert draft_res.status_code == 201, draft_res.text
    draft = draft_res.json()
    assert draft["recipient_email"] == "priya.sharma@acme.example"
    assert "Senior Node.js Developer" in draft["body"] and "Azure" not in draft["body"]
    assert draft["status"] == "draft" and draft["approved"] is False
    app_id = draft["application_id"]
    assert client.get(f"/api/applications/{app_id}", headers=headers).json()["status"] == "awaiting_approval"
    assert client.post("/api/applications/drafts", headers=headers, json={"job_id": job.id, "tone": "shouty"}).status_code == 400

    # sending without approval is refused
    assert client.post(f"/api/applications/{app_id}/send", headers=headers, json={"draft_id": draft["id"]}).status_code == 403

    edited = client.patch(f"/api/applications/drafts/{draft['id']}", headers=headers, json={"body": draft["body"] + "\n\nPS: I can start in May."})
    assert edited.status_code == 200
    regenerated = client.post(f"/api/applications/drafts/{draft['id']}/regenerate", headers=headers, json={"section": "closing", "tone": "concise"})
    assert regenerated.json()["tone"] == "concise"

    approved = client.post(f"/api/applications/{app_id}/approve", headers=headers, json={"draft_id": draft["id"]})
    assert approved.status_code == 200 and approved.json()["approved"] is True
    assert client.get(f"/api/applications/{app_id}", headers=headers).json()["status"] == "ready_to_apply"

    # an edit after approval invalidates it
    client.patch(f"/api/applications/drafts/{draft['id']}", headers=headers, json={"subject": "Changed subject"})
    assert client.post(f"/api/applications/{app_id}/send", headers=headers, json={"draft_id": draft["id"]}).status_code == 403
    client.post(f"/api/applications/{app_id}/approve", headers=headers, json={"draft_id": draft["id"]})

    sent = client.post(f"/api/applications/{app_id}/send", headers=headers, json={"draft_id": draft["id"]})
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent" and sent.json()["provider"] == "console"
    assert client.post(f"/api/applications/{app_id}/send", headers=headers, json={"draft_id": draft["id"]}).status_code == 409
    assert client.patch(f"/api/applications/drafts/{draft['id']}", headers=headers, json={"body": "x"}).status_code == 409

    detail = client.get(f"/api/applications/{app_id}", headers=headers).json()
    assert detail["status"] == "applied"
    assert [e["event_type"] for e in detail["events"]][-1] == "sent"
    assert detail["sends"][0]["provider_message_id"].startswith("console-")
    reminders = client.get("/api/applications/reminders", headers=headers).json()
    assert reminders and reminders[0]["kind"] == "follow_up" and "Acme" in reminders[0]["job_title"]

    # tracker updates, interview reminder, duplicate protection
    assert client.post("/api/applications", headers=headers, json={"job_id": job.id}).status_code == 409
    assert client.patch(f"/api/applications/{app_id}", headers=headers, json={"status": "nonsense"}).status_code == 400
    updated = client.patch(f"/api/applications/{app_id}", headers=headers, json={"interview_at": "2030-01-10T10:00:00Z", "notes": "Panel round"})
    assert updated.json()["status"] == "interview_scheduled"
    assert db.query(Reminder).filter_by(kind="interview").count() == 1
    done = client.patch(f"/api/applications/reminders/{reminders[0]['id']}", headers=headers, json={"done": True})
    assert done.json()["done"] is True

    summary = client.get("/api/dashboard/summary", headers=headers).json()
    assert summary["applications_total"] == 1 and summary["by_status"]["interview_scheduled"] == 1
    assert summary["with_public_emails"] == 1 and len(summary["upcoming_interviews"]) == 1

    other = register(client, "other@example.com", "Other")
    assert client.get(f"/api/applications/{app_id}", headers=other).status_code == 404
    assert client.get(f"/api/applications/drafts/{draft['id']}", headers=other).status_code == 404


def test_send_failure_is_recorded_not_faked(client, db, monkeypatch):
    from app.routers import applications as apps_router
    from app.services.email_provider import SendError

    class Broken:
        name = "smtp"

        def send(self, *args):
            raise SendError("550 mailbox unavailable", bounced=True)

    headers = register(client)
    client.patch("/api/profile", headers=headers, json=PROFILE)
    job = seed_job(db)
    monkeypatch.setattr(contacts, "fetch_page", lambda url: "")
    client.post(f"/api/jobs/{job.id}/contacts", headers=headers)
    draft = client.post("/api/applications/drafts", headers=headers, json={"job_id": job.id}).json()
    client.post(f"/api/applications/{draft['application_id']}/approve", headers=headers, json={"draft_id": draft["id"]})
    monkeypatch.setattr(apps_router, "get_email_provider", lambda: Broken())

    res = client.post(f"/api/applications/{draft['application_id']}/send", headers=headers, json={"draft_id": draft["id"]})
    assert res.status_code == 200 and res.json()["status"] == "failed" and "550" in res.json()["error"]
    assert client.get(f"/api/applications/{draft['application_id']}", headers=headers).json()["status"] == "ready_to_apply"
    assert client.get(f"/api/jobs/{job.id}/contacts", headers=headers).json()[0]["status"] == "BOUNCED"
    assert any(n["kind"] == "send_failed" for n in client.get("/api/notifications", headers=headers).json())


def test_admin_endpoints(client, db):
    headers = register(client)
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    user = db.query(User).first()
    user.role = "admin"
    db.commit()
    admin = {"Authorization": client.post("/api/auth/login", json={"email": "asha@example.com", "password": "password123"}).json()["token"]}
    admin = {"Authorization": f"Bearer {admin['Authorization']}"}
    users = client.get("/api/admin/users", headers=admin).json()
    assert users[0]["email"] == "asha@example.com"
    sources = client.get("/api/admin/sources", headers=admin).json()
    assert {s["key"] for s in sources} == {"remotive", "arbeitnow"}
    off = client.patch(f"/api/admin/sources/{sources[0]['id']}", headers=admin, json={"enabled": False})
    assert off.json()["enabled"] is False
    health = client.get("/api/admin/health", headers=admin).json()
    assert health["status"] == "ok" and health["llm_provider"] == "mock"
    assert client.get("/api/admin/audit-logs", headers=admin).json()[0]["action"] == "admin_source_update"
    disabled = client.patch(f"/api/admin/users/{user.id}", headers=admin, json={"is_active": False})
    assert disabled.json()["is_active"] is False
    assert client.get("/api/auth/me", headers=admin).status_code == 401
