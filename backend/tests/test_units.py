from datetime import date

from app.models import CandidateProfile, Job, JobMatch, RecruiterContact, User
from app.services import contacts, discovery, drafts, matching, resume_parser
from app.skills import extract_skills, normalize_list


def profile(**overrides) -> CandidateProfile:
    fields = dict(
        skills=["Node.js", "TypeScript", "PostgreSQL", "React"],
        experience_years=4,
        target_roles=["Node.js Developer"],
        work_modes=["remote"],
        preferred_locations=["Pune"],
        expected_ctc=1500000,
        ctc_currency="INR",
        education=[{"text": "B.Tech"}],
        experience=[{"title": "Backend Developer", "text": "Node.js services with TypeScript on PostgreSQL"}],
        projects=[{"text": "Payments API in Node.js and TypeScript"}],
    )
    fields.update(overrides)
    return CandidateProfile(**fields)


def job(**overrides) -> Job:
    fields = dict(
        title="Senior Node.js Developer",
        company="Acme",
        description="Required: Node.js, TypeScript, PostgreSQL and Azure. 3+ years. Bachelor degree preferred.",
        work_mode="remote",
        location="Worldwide",
        experience_min=3,
        tags=[],
        salary_currency="",
        salary_text="",
        canonical_url="https://jobs.example/1",
    )
    fields.update(overrides)
    return Job(**fields)


def test_skill_extraction_handles_aliases_and_odd_characters():
    found = extract_skills("Worked with node, react.js, C#, .NET and postgres; also CI/CD pipelines")
    assert {"Node.js", "React", "C#", ".NET", "PostgreSQL", "CI/CD"} <= set(found)
    assert "Go" not in extract_skills("Let's go to the next step")
    assert normalize_list(["node", "TS", "postgres", "Figma"]) == ["Node.js", "TypeScript", "PostgreSQL", "Figma"]


def test_match_score_is_explainable():
    result = matching.score_job(profile(), job())
    assert 0 <= result["score"] <= 100
    assert {"Node.js", "TypeScript", "PostgreSQL"} <= set(result["strong_matches"])
    azure = [g for g in result["gaps"] if g["skill"] == "Azure"]
    assert azure and azure[0]["status"] == "unconfirmed"
    names = {f["name"]: f for f in result["factors"]}
    assert names["skills"]["status"] == "known"
    assert names["experience"]["score"] == 1.0
    assert names["salary"]["status"] == "unknown"
    assert any("Salary" in u for u in result["unknowns"])
    assert "Azure" in result["explanation"]


def test_missing_information_is_unknown_not_a_gap():
    result = matching.score_job(profile(experience_years=None, target_roles=[]), job(experience_min=5))
    names = {f["name"]: f for f in result["factors"]}
    assert names["experience"]["status"] == "unknown"
    assert names["role"]["status"] == "unknown"
    assert not [g for g in result["gaps"] if g["skill"] == "Experience"]
    # a listing with no recognisable technologies does not pretend to score skills
    plain = matching.score_job(profile(), job(title="Senior Developer", description="Great team, nice office.", experience_min=None))
    assert {f["name"]: f for f in plain["factors"]}["skills"]["status"] == "unknown"


def test_unrelated_roles_are_capped():
    writer = matching.score_job(profile(), job(title="Freelance Writer", description="Write docs about Node.js and React. Remote, worldwide.", experience_min=None))
    assert writer["score"] <= 40
    assert any("capped at 40" in u for u in writer["unknowns"])
    vague = matching.score_job(profile(), job(title="Software Developer", description="Join a great team.", experience_min=None))
    assert vague["score"] <= 50
    assert any("capped at 50" in u for u in vague["unknowns"])
    # a listing naming one skill carries less weight than one naming several
    one = matching.score_job(profile(), job(description="Needs Node.js.", experience_min=None))
    many = matching.score_job(profile(), job(description="Needs Node.js, TypeScript, PostgreSQL, React.", experience_min=None))
    assert {f["name"]: f for f in one["factors"]}["skills"]["weight"] < {f["name"]: f for f in many["factors"]}["skills"]["weight"]


def test_scores_react_to_experience_and_location():
    short = matching.score_job(profile(experience_years=1), job(experience_min=3))
    assert short["score"] < matching.score_job(profile(), job())["score"]
    assert any(g["skill"] == "Experience" for g in short["gaps"])
    onsite_far = matching.score_job(profile(), job(work_mode="onsite", location="Berlin"))
    onsite_near = matching.score_job(profile(), job(work_mode="onsite", location="Pune, India"))
    assert onsite_near["score"] > onsite_far["score"]


def test_discovery_helpers():
    assert discovery.html_to_text("<p>Hello <b>world</b></p><ul><li>one</li></ul>") == "Hello world\none"
    assert discovery.parse_experience("We need 3-5 years of experience") == (3, 5)
    assert discovery.parse_experience("5+ years") == (5, None)
    assert discovery.parse_experience("no numbers here") == (None, None)
    assert discovery.parse_salary("$100k - $120k per year") == (100000.0, 120000.0, "USD")
    assert discovery.parse_salary("₹12,00,000") == (1200000.0, None, "INR")
    assert discovery.fingerprint("Senior Node.js Developer", "Acme Ltd.") == discovery.fingerprint("senior node js developer", "ACME LTD")
    assert discovery.work_mode_of("Hybrid role in Berlin", False) == "hybrid"


def test_email_extraction_never_guesses():
    text = (
        "Join us! Send your CV to Priya Sharma - priya.sharma@acme.example or apply online. "
        "Do not reply to noreply@acme.example. Logo: image@2x.png. Again priya.sharma@acme.example."
    )
    found = contacts.find_emails(text)
    assert [c["email"] for c in found] == ["priya.sharma@acme.example"]
    assert found[0]["name"] == "Priya Sharma"
    assert contacts.find_emails("Contact the hiring manager, John Smith, for details") == []


def test_resume_parser_reads_sections_and_years():
    text = """Tarun Meena
meenatarun656@gmail.com | +91 98765 43210
Summary
Backend developer who likes Node.js and Python.
Skills
Node.js, TypeScript, React, PostgreSQL, Docker
Experience
Full-Stack Developer, Rootlex Technology Oct 2025 - Present
Built REST APIs with NestJS and FastAPI.
MERN Stack Developer, Bigscal Technologies Jul 2023 - Oct 2025
Shipped MERN applications on AWS Lambda.
Education
Master of Computer Application (MCA), RGPV, 2023
Projects
Contest platform with AI question generation
"""
    parsed, usage = resume_parser.parse_resume(text)
    assert usage is None
    assert parsed["name"] == "Tarun Meena"
    assert parsed["email"] == "meenatarun656@gmail.com"
    assert {"Node.js", "TypeScript", "React", "PostgreSQL", "Docker"} <= set(parsed["skills"])
    assert len(parsed["experience"]) == 2
    assert parsed["experience"][0]["start"] == "2025-10-01"
    assert parsed["experience_years"] and parsed["experience_years"] > 2.5
    assert parsed["education"][0]["text"].startswith("Master of Computer Application")
    assert parsed["projects"][0]["text"].startswith("Contest platform")
    assert resume_parser.total_years([{"start": "2020-01-01", "end": "2021-01-01"}, {"start": "2020-06-01", "end": "2022-01-01"}]) == 2.0
    assert resume_parser._parse_month_year("present") == date.today()


def test_draft_uses_only_profile_facts():
    user = User(name="Asha Verma", email="asha@example.com", password_hash="x")
    match = JobMatch(score=80, strong_matches=["Node.js", "TypeScript"], gaps=[{"skill": "Azure", "status": "unconfirmed"}], factors=[], unknowns=[])
    contact = RecruiterContact(name="Priya Sharma", email="priya@acme.example", status="PUBLICLY_LISTED")
    sections = drafts.build_sections(user, profile(notice_period_days=30), job(), match, contact, "professional")
    body = drafts.join_sections(sections)
    assert body.startswith("Dear Priya Sharma,")
    assert "Senior Node.js Developer role at Acme" in body
    assert "Node.js, TypeScript" in body
    assert "Payments API" in body
    assert "notice period 30 days" in body
    assert "Azure" not in body
    assert body.rstrip().endswith("Asha Verma")
    concise = drafts.join_sections(drafts.build_sections(user, profile(), job(), match, None, "concise"))
    assert concise.startswith("Hello Hiring Team,")
    assert len(concise) < len(body)
    assert drafts.subject_for(user, job()) == "Application for Senior Node.js Developer – Asha Verma"
