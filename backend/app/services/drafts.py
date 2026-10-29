from ..models import CandidateProfile, Job, JobMatch, RecruiterContact, User
from .llm import LLMProvider, LLMResult

TONES = {
    "professional": {"greeting": "Dear", "opener": "I am writing to apply for", "closing": "Kind regards"},
    "friendly": {"greeting": "Hi", "opener": "I'd love to be considered for", "closing": "Best"},
    "concise": {"greeting": "Hello", "opener": "Applying for", "closing": "Regards"},
}
SECTIONS = ["greeting", "intro", "fit", "logistics", "closing"]


def _evidence(profile: CandidateProfile, skills: list[str], limit: int = 2) -> list[str]:
    """Projects or roles from the profile that mention the matched skills. Nothing is made up."""
    lines: list[str] = []
    wanted = [s.lower() for s in skills]
    for item in list(profile.projects) + list(profile.experience):
        text = item.get("text") or item.get("description") or item.get("title") or ""
        if any(w in text.lower() for w in wanted) and text not in lines:
            lines.append(text.strip())
        if len(lines) >= limit:
            break
    return lines


def build_sections(user: User, profile: CandidateProfile, job: Job, match: JobMatch | None, contact: RecruiterContact | None, tone: str) -> dict[str, str]:
    t = TONES.get(tone, TONES["professional"])
    strong = list(match.strong_matches) if match else []
    name = contact.name if contact and contact.name else "Hiring Team"
    years = f"{profile.experience_years:g} years" if profile.experience_years else None
    role = profile.target_roles[0] if profile.target_roles else (profile.headline or "software developer")

    greeting = f"{t['greeting']} {name},"

    intro = f"{t['opener']} the {job.title} role at {job.company}."
    if years:
        intro += f" I am a {role} with {years} of experience"
        intro += f", most recently {profile.experience[0].get('title')}." if profile.experience and profile.experience[0].get("title") else "."
    elif profile.headline:
        intro += f" I am a {profile.headline}."

    fit_lines = []
    if strong:
        fit_lines.append(f"The listing asks for {', '.join(strong[:5])}, which I use day to day.")
    for line in _evidence(profile, strong):
        fit_lines.append(line if len(line) < 220 else line[:217] + "...")
    if not fit_lines and profile.summary:
        fit_lines.append(profile.summary[:300])
    fit = " ".join(fit_lines) if tone != "concise" else (fit_lines[0] if fit_lines else "")

    logistics_bits = []
    if profile.notice_period_days is not None:
        logistics_bits.append(f"notice period {profile.notice_period_days} days" if profile.notice_period_days else "available immediately")
    elif profile.availability:
        logistics_bits.append(f"available {profile.availability}")
    if profile.expected_ctc and job.salary_currency == profile.ctc_currency:
        logistics_bits.append(f"expected compensation {profile.ctc_currency} {profile.expected_ctc:,.0f}")
    if job.work_mode == "remote" and "remote" in [m.lower() for m in profile.work_modes]:
        logistics_bits.append("set up for remote work")
    elif job.location and profile.preferred_locations:
        logistics_bits.append(f"open to {job.location}")
    logistics = ("For planning: " + ", ".join(logistics_bits) + ".") if logistics_bits else ""

    closing = f"My resume is attached. I would welcome a conversation about the role.\n\n{t['closing']},\n{user.name}"
    if tone == "concise":
        closing = f"Resume attached.\n\n{t['closing']},\n{user.name}"
    return {"greeting": greeting, "intro": intro, "fit": fit, "logistics": logistics, "closing": closing}


def join_sections(sections: dict[str, str]) -> str:
    return "\n\n".join(sections[s] for s in SECTIONS if sections.get(s))


def subject_for(user: User, job: Job) -> str:
    return f"Application for {job.title} – {user.name}"


def llm_body(llm: LLMProvider, user: User, profile: CandidateProfile, job: Job, match: JobMatch | None, tone: str, template: str) -> LLMResult | None:
    """Optional rewrite by the model. It only gets facts that are already in the profile, and the result is
    rejected if it mentions a skill the profile does not have."""
    if not llm.enabled:
        return None
    gaps = [g["skill"] for g in (match.gaps if match else [])]
    out = llm.complete(
        "You write short job application emails. Use ONLY the facts given. Never add skills, employers, degrees, "
        "certifications or years that are not listed. Keep the candidate's name and the job title exactly. Plain text.",
        f"Tone: {tone}\nCandidate: {user.name}\nSkills: {', '.join(profile.skills)}\nExperience years: {profile.experience_years}\n"
        f"Recent roles: {[e.get('title') for e in profile.experience[:3]]}\nProjects: {[p.get('text') for p in profile.projects[:3]]}\n"
        f"Job: {job.title} at {job.company}\nMatched skills: {match.strong_matches if match else []}\n"
        f"Do not claim these (not in profile): {gaps}\n\nRewrite this draft in the requested tone, same facts:\n{template}",
        max_tokens=600,
    )
    text = out.text.strip()
    if not text or any(g.lower() in text.lower() for g in gaps):
        out.text = ""
    return out
