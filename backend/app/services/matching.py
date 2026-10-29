import re

from ..models import CandidateProfile, Job
from ..skills import extract_skills, normalize_list
from .llm import LLMProvider, LLMResult

SENIOR_RE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|head|director|manager|architect)\b", re.IGNORECASE)
JUNIOR_RE = re.compile(r"\b(junior|jr\.?|intern|trainee|graduate|entry)\b", re.IGNORECASE)
DEGREE_RE = re.compile(r"\b(bachelor|master|degree|b\.?tech|b\.?e\.?|m\.?tech|mca|bca)\b", re.IGNORECASE)
WORDS_RE = re.compile(r"[a-z0-9.+#]+")
STOP = {"the", "and", "of", "a", "an", "for", "with", "in", "at", "to", "sr", "jr"}
# words that mean the same thing in a job title
SYNONYMS = {"engineer": "developer", "programmer": "developer", "dev": "developer", "fullstack": "full stack", "full-stack": "full stack"}

WEIGHTS = {"skills": 45, "role": 20, "experience": 15, "location": 10, "salary": 5, "qualifications": 5}


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    for word, replacement in SYNONYMS.items():
        lowered = re.sub(rf"\b{word}\b", replacement, lowered)
    return {w for w in WORDS_RE.findall(lowered) if w not in STOP and len(w) > 1}


def _role_score(job: Job, target_roles: list[str]) -> tuple[float | None, str]:
    if not target_roles:
        return None, "No target roles in profile"
    title = _tokens(job.title)
    best = 0.0
    best_role = ""
    for role in target_roles:
        words = _tokens(role)
        if not words:
            continue
        overlap = len(words & title) / len(words)
        if overlap > best:
            best, best_role = overlap, role
    # the generic words count a little when the title says developer/engineer
    if best == 0 and re.search(r"developer|engineer", job.title, re.IGNORECASE):
        best = 0.3
    return best, f"Title '{job.title}' vs target role '{best_role or target_roles[0]}'"


def score_job(profile: CandidateProfile, job: Job) -> dict:
    factors: list[dict] = []
    unknowns: list[str] = []
    strong: list[str] = []
    gaps: list[dict] = []

    job_skills = extract_skills(f"{job.title}\n{' '.join(job.tags)}\n{job.description}")
    profile_skills = set(normalize_list(profile.skills))
    title_skills = set(extract_skills(job.title))

    # skills. a listing that names only one or two technologies is weak evidence, so its weight shrinks
    if job_skills:
        weighted_total = 0.0
        weighted_hit = 0.0
        for skill in job_skills:
            weight = 2.0 if skill in title_skills else 1.0
            weighted_total += weight
            if skill in profile_skills:
                weighted_hit += weight
                strong.append(skill)
            else:
                gaps.append({"skill": skill, "status": "unconfirmed", "note": f"{skill} is not confirmed in the profile. Verify before applying."})
        value = weighted_hit / weighted_total
        weight = round(WEIGHTS["skills"] * min(1.0, len(job_skills) / 4), 1)
        factors.append({"name": "skills", "weight": weight, "score": round(value, 2), "status": "known", "evidence": f"{len(strong)} of {len(job_skills)} skills mentioned in the listing are in the profile"})
    else:
        unknowns.append("The listing does not name specific technologies")
        factors.append({"name": "skills", "weight": WEIGHTS["skills"], "score": None, "status": "unknown", "evidence": "No recognisable skills in the listing"})

    # role relevance
    role_value, role_evidence = _role_score(job, profile.target_roles)
    seniority_note = ""
    years = profile.experience_years
    if role_value is not None and years is not None:
        if SENIOR_RE.search(job.title) and years < 5:
            role_value *= 0.7
            seniority_note = f"; senior title with {years} years in profile"
        elif JUNIOR_RE.search(job.title) and years > 4:
            role_value *= 0.8
            seniority_note = f"; junior title with {years} years in profile"
    if role_value is None:
        unknowns.append("Target roles not set in the profile")
        factors.append({"name": "role", "weight": WEIGHTS["role"], "score": None, "status": "unknown", "evidence": role_evidence})
    else:
        factors.append({"name": "role", "weight": WEIGHTS["role"], "score": round(role_value, 2), "status": "known", "evidence": role_evidence + seniority_note})

    # experience
    if job.experience_min is None:
        unknowns.append("The listing does not state the years of experience required")
        factors.append({"name": "experience", "weight": WEIGHTS["experience"], "score": None, "status": "unknown", "evidence": "No experience range in the listing"})
    elif years is None:
        unknowns.append("Years of experience missing from the profile")
        factors.append({"name": "experience", "weight": WEIGHTS["experience"], "score": None, "status": "unknown", "evidence": f"Listing asks for {job.experience_min}+ years, profile has no total"})
    else:
        value = 1.0 if years >= job.experience_min else max(years / job.experience_min, 0) * 0.8
        factors.append({"name": "experience", "weight": WEIGHTS["experience"], "score": round(value, 2), "status": "known", "evidence": f"Listing asks for {job.experience_min}+ years, profile has {years}"})
        if years < job.experience_min:
            gaps.append({"skill": "Experience", "status": "gap", "note": f"Listing asks for {job.experience_min}+ years, profile shows {years}."})

    # location and work mode
    modes = [m.lower() for m in profile.work_modes]
    locations = [l.lower() for l in profile.preferred_locations]
    if job.work_mode == "remote":
        value = 1.0 if ("remote" in modes or not modes) else 0.5
        evidence = "Remote listing" + ("" if value == 1 else ", profile prefers on-site/hybrid")
        loc = job.location.lower()
        if loc and loc not in ("worldwide", "anywhere") and locations and not any(l in loc for l in locations):
            value = min(value, 0.6)
            evidence += f"; remote restricted to {job.location}"
        factors.append({"name": "location", "weight": WEIGHTS["location"], "score": value, "status": "known", "evidence": evidence})
    elif job.work_mode in ("onsite", "hybrid"):
        if not locations:
            unknowns.append("Preferred locations not set in the profile")
            factors.append({"name": "location", "weight": WEIGHTS["location"], "score": None, "status": "unknown", "evidence": f"{job.work_mode} in {job.location or 'unspecified location'}"})
        else:
            hit = any(l in job.location.lower() for l in locations)
            value = 1.0 if hit else 0.2
            factors.append({"name": "location", "weight": WEIGHTS["location"], "score": value, "status": "known", "evidence": f"{job.work_mode} in {job.location or 'unspecified location'}; preferred {', '.join(profile.preferred_locations)}"})
            if not hit:
                gaps.append({"skill": "Location", "status": "gap", "note": f"{job.work_mode.title()} role in {job.location}, outside the preferred locations."})
    else:
        unknowns.append("Work mode not stated in the listing")
        factors.append({"name": "location", "weight": WEIGHTS["location"], "score": None, "status": "unknown", "evidence": "Listing does not say remote, hybrid or on-site"})

    # salary
    if job.salary_max and profile.expected_ctc and job.salary_currency and job.salary_currency == profile.ctc_currency:
        value = 1.0 if profile.expected_ctc <= job.salary_max else max(0.0, 1 - (profile.expected_ctc - job.salary_max) / profile.expected_ctc)
        factors.append({"name": "salary", "weight": WEIGHTS["salary"], "score": round(value, 2), "status": "known", "evidence": f"Listing up to {job.salary_currency} {job.salary_max:,.0f}, expected {profile.ctc_currency} {profile.expected_ctc:,.0f}"})
    else:
        unknowns.append("Salary not comparable (missing in listing or profile, or different currency)")
        factors.append({"name": "salary", "weight": WEIGHTS["salary"], "score": None, "status": "unknown", "evidence": job.salary_text or "No salary in the listing"})

    # qualifications
    if DEGREE_RE.search(job.description):
        if profile.education:
            factors.append({"name": "qualifications", "weight": WEIGHTS["qualifications"], "score": 1.0, "status": "known", "evidence": "Listing mentions a degree; profile has education entries"})
        else:
            unknowns.append("Listing mentions a degree but the profile has no education entries")
            factors.append({"name": "qualifications", "weight": WEIGHTS["qualifications"], "score": None, "status": "unknown", "evidence": "Listing mentions a degree; profile education is empty"})
    else:
        factors.append({"name": "qualifications", "weight": WEIGHTS["qualifications"], "score": None, "status": "unknown", "evidence": "No qualification requirement found in the listing"})

    known = [f for f in factors if f["status"] == "known"]
    total_weight = sum(f["weight"] for f in known)
    score = round(sum(f["weight"] * f["score"] for f in known) / total_weight * 100) if total_weight else 0
    score = max(0, min(100, score))

    # a listing that does not match the target roles at all, or names no technologies, cannot be a high match
    caps = []
    if role_value == 0:
        caps.append((40, "the title does not match any of your target roles"))
    if not job_skills:
        caps.append((50, "the listing names no technologies"))
    elif not strong:
        caps.append((45, "none of the technologies named in the listing are in your profile"))
    for cap, reason in caps:
        if score > cap:
            score = cap
            unknowns.append(f"Score capped at {cap} because {reason}")

    explanation = explain(score, strong, gaps, unknowns)
    return {
        "score": score,
        "factors": factors,
        "strong_matches": strong,
        "gaps": gaps,
        "unknowns": unknowns,
        "explanation": explanation,
    }


def explain(score: int, strong: list[str], gaps: list[dict], unknowns: list[str]) -> str:
    parts = []
    if strong:
        parts.append(f"Strong matches: {', '.join(strong[:6])}.")
    unconfirmed = [g["skill"] for g in gaps if g["status"] == "unconfirmed"]
    hard = [g["note"] for g in gaps if g["status"] == "gap"]
    if unconfirmed:
        parts.append(f"Not confirmed in the profile: {', '.join(unconfirmed[:6])}; verify before applying.")
    parts.extend(hard[:2])
    if unknowns:
        parts.append(f"Not scored: {unknowns[0].lower()}.")
    return " ".join(parts) or f"Score {score} with no specific factors."


def llm_explanation(llm: LLMProvider, job: Job, result: dict) -> LLMResult | None:
    """Optional nicer wording. The score itself never comes from the model."""
    if not llm.enabled:
        return None
    out = llm.complete(
        "You explain job match scores to a job seeker in two sentences. Do not change or question the score, do not invent skills.",
        f"Job: {job.title} at {job.company}\nScore: {result['score']}/100\nFactors: {result['factors']}\nStrong: {result['strong_matches']}\n"
        f"Gaps: {result['gaps']}\nUnknown: {result['unknowns']}",
        max_tokens=200,
    )
    if out.text.strip():
        result["explanation"] = out.text.strip()
    return out
