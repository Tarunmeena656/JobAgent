from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

APPLICATION_STATUSES = [
    "saved",
    "ready_to_apply",
    "draft_prepared",
    "awaiting_approval",
    "applied",
    "follow_up_due",
    "interview_scheduled",
    "rejected",
    "offer_received",
    "closed",
]
TONES = ["professional", "friendly", "concise"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(Out):
    id: int
    email: str
    name: str
    role: str
    created_at: datetime


class TokenOut(BaseModel):
    token: str
    user: UserOut


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


# profile
class ProfileIn(BaseModel):
    headline: str | None = Field(default=None, max_length=200)
    summary: str | None = None
    skills: list[str] | None = None
    experience_years: float | None = Field(default=None, ge=0, le=60)
    experience: list[dict] | None = None
    education: list[dict] | None = None
    projects: list[dict] | None = None
    current_ctc: float | None = Field(default=None, ge=0)
    expected_ctc: float | None = Field(default=None, ge=0)
    ctc_currency: str | None = Field(default=None, max_length=8)
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    availability: str | None = Field(default=None, max_length=120)
    preferred_locations: list[str] | None = None
    work_modes: list[str] | None = None
    target_roles: list[str] | None = None


class ProfileOut(Out):
    id: int
    user_id: int
    headline: str
    summary: str
    skills: list
    experience_years: float | None
    experience: list
    education: list
    projects: list
    current_ctc: float | None
    expected_ctc: float | None
    ctc_currency: str
    notice_period_days: int | None
    availability: str
    preferred_locations: list
    work_modes: list
    target_roles: list
    updated_at: datetime


# resumes
class ResumeOut(Out):
    id: int
    label: str
    filename: str
    content_type: str
    status: str
    parsed: dict
    created_at: datetime


class ResumeReviewIn(BaseModel):
    parsed: dict | None = None
    label: str | None = Field(default=None, max_length=120)
    approve: bool = False
    apply_to_profile: bool = False


# jobs
class JobSearchIn(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=10)
    posted_within_days: int | None = Field(default=30, ge=1, le=365)
    sources: list[str] | None = None


class SourceOut(Out):
    id: int
    key: str
    name: str
    base_url: str
    enabled: bool
    last_run_at: datetime | None
    last_status: str
    last_error: str


class SourceUpdateIn(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


class ContactOut(Out):
    id: int
    job_id: int
    name: str
    email: str
    role: str
    status: str
    source_url: str
    retrieved_at: datetime
    confidence: float
    notes: str


class MatchOut(Out):
    score: int
    factors: list
    strong_matches: list
    gaps: list
    unknowns: list
    explanation: str
    model: str
    created_at: datetime


class JobOut(BaseModel):
    id: int
    source: str
    title: str
    company: str
    location: str
    work_mode: str
    experience_min: int | None
    experience_max: int | None
    salary_text: str
    salary_currency: str
    salary_min: float | None
    salary_max: float | None
    tags: list
    posted_at: datetime | None
    posted_at_verified: bool
    retrieved_at: datetime
    status: str
    canonical_url: str
    match: MatchOut | None = None
    public_emails: int = 0
    application_id: int | None = None
    application_status: str | None = None


class JobDetailOut(JobOut):
    description: str
    contacts: list[ContactOut] = Field(default_factory=list)


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


# applications and drafts
class DraftGenerateIn(BaseModel):
    job_id: int
    tone: str = "professional"
    contact_id: int | None = None
    recipient_email: EmailStr | None = None
    resume_id: int | None = None


class DraftUpdateIn(BaseModel):
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = None
    recipient_email: EmailStr | None = None
    tone: str | None = None
    attachments: list[int] | None = None


class DraftRegenerateIn(BaseModel):
    section: str = Field(pattern="^(greeting|intro|fit|logistics|closing|all)$")
    tone: str | None = None


class DraftOut(Out):
    id: int
    job_id: int
    application_id: int
    contact_id: int | None
    recipient_email: str
    subject: str
    body: str
    tone: str
    attachments: list
    generated_by: str
    status: str
    created_at: datetime
    updated_at: datetime
    job_title: str = ""
    company: str = ""
    approved: bool = False


class ApplicationCreateIn(BaseModel):
    job_id: int
    resume_id: int | None = None
    status: str = "saved"


class ApplicationUpdateIn(BaseModel):
    status: str | None = None
    notes: str | None = None
    interview_at: datetime | None = None
    resume_id: int | None = None


class EventOut(Out):
    id: int
    event_type: str
    from_status: str
    to_status: str
    details: dict
    created_at: datetime


class SendOut(Out):
    id: int
    status: str
    provider: str
    provider_message_id: str
    recipient_email: str
    error: str
    sent_at: datetime


class ApplicationOut(Out):
    id: int
    job_id: int
    resume_id: int | None
    status: str
    notes: str
    interview_at: datetime | None
    created_at: datetime
    updated_at: datetime
    job_title: str = ""
    company: str = ""
    canonical_url: str = ""
    match_score: int | None = None
    latest_draft_id: int | None = None
    draft_status: str | None = None


class ApplicationDetailOut(ApplicationOut):
    events: list[EventOut] = Field(default_factory=list)
    drafts: list[DraftOut] = Field(default_factory=list)
    sends: list[SendOut] = Field(default_factory=list)


class ApproveIn(BaseModel):
    draft_id: int


class ReminderIn(BaseModel):
    application_id: int | None = None
    kind: str = Field(default="follow_up", pattern="^(follow_up|interview|custom)$")
    due_at: datetime
    note: str = ""


class ReminderUpdateIn(BaseModel):
    done: bool | None = None
    due_at: datetime | None = None
    note: str | None = None


class ReminderOut(Out):
    id: int
    application_id: int | None
    kind: str
    due_at: datetime
    note: str
    done: bool
    created_at: datetime
    job_title: str = ""


# dashboard, notifications, runs, admin
class DashboardOut(BaseModel):
    days: int
    jobs_today: int
    jobs_in_range: int
    new_matching: int
    high_match: int
    with_public_emails: int
    drafts_awaiting: int
    applications_total: int
    by_status: dict[str, int]
    upcoming_reminders: list[ReminderOut]
    upcoming_interviews: list[ApplicationOut]


class NotificationOut(Out):
    id: int
    kind: str
    title: str
    body: str
    link: str
    read: bool
    created_at: datetime


class AgentRunOut(Out):
    id: int
    user_id: int | None
    parent_run_id: int | None
    agent: str
    status: str
    input: dict
    output: dict
    error: str
    attempts: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int
    created_at: datetime


class AdminUserOut(UserOut):
    is_active: bool
    daily_llm_limit: int
    applications: int = 0


class AdminUserUpdateIn(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(seeker|admin)$")
    daily_llm_limit: int | None = Field(default=None, ge=0)


class AuditOut(Out):
    id: int
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    details: dict
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    database: str
    llm_provider: str
    email_provider: str
    sources: list[SourceOut]
    runs_last_24h: dict[str, int]
