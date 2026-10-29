export type User = { id: number; email: string; name: string; role: 'seeker' | 'admin'; created_at: string };

export type Profile = {
  id: number;
  user_id: number;
  headline: string;
  summary: string;
  skills: string[];
  experience_years: number | null;
  experience: ExperienceEntry[];
  education: { text: string }[];
  projects: { text: string }[];
  current_ctc: number | null;
  expected_ctc: number | null;
  ctc_currency: string;
  notice_period_days: number | null;
  availability: string;
  preferred_locations: string[];
  work_modes: string[];
  target_roles: string[];
  updated_at: string;
};

export type ExperienceEntry = { title?: string; company?: string; start?: string; end?: string; text?: string };

export type Resume = {
  id: number;
  label: string;
  filename: string;
  content_type: string;
  status: 'parsed' | 'approved';
  parsed: {
    name?: string;
    email?: string;
    phone?: string;
    summary?: string;
    skills?: string[];
    experience?: ExperienceEntry[];
    experience_years?: number | null;
    education?: { text: string }[];
    projects?: { text: string }[];
  };
  created_at: string;
};

export type Factor = { name: string; weight: number; score: number | null; status: 'known' | 'unknown'; evidence: string };
export type Gap = { skill: string; status: 'unconfirmed' | 'gap'; note: string };

export type Match = {
  score: number;
  factors: Factor[];
  strong_matches: string[];
  gaps: Gap[];
  unknowns: string[];
  explanation: string;
  model: string;
  created_at: string;
};

export type Contact = {
  id: number;
  job_id: number;
  name: string;
  email: string;
  role: string;
  status: 'PUBLICLY_LISTED' | 'SOURCE_UNVERIFIED' | 'NOT_FOUND' | 'BOUNCED';
  source_url: string;
  retrieved_at: string;
  confidence: number;
  notes: string;
};

export type Job = {
  id: number;
  source: string;
  title: string;
  company: string;
  location: string;
  work_mode: string;
  experience_min: number | null;
  experience_max: number | null;
  salary_text: string;
  salary_currency: string;
  salary_min: number | null;
  salary_max: number | null;
  tags: string[];
  posted_at: string | null;
  posted_at_verified: boolean;
  retrieved_at: string;
  status: string;
  canonical_url: string;
  match: Match | null;
  public_emails: number;
  application_id: number | null;
  application_status: string | null;
};

export type JobDetail = Job & { description: string; contacts: Contact[] };
export type JobList = { items: Job[]; total: number; page: number; page_size: number };

export type Draft = {
  id: number;
  job_id: number;
  application_id: number;
  contact_id: number | null;
  recipient_email: string;
  subject: string;
  body: string;
  tone: string;
  attachments: number[];
  generated_by: string;
  status: 'draft' | 'approved' | 'sent' | 'failed';
  created_at: string;
  updated_at: string;
  job_title: string;
  company: string;
  approved: boolean;
};

export type ApplicationEvent = { id: number; event_type: string; from_status: string; to_status: string; details: Record<string, unknown>; created_at: string };
export type Send = { id: number; status: string; provider: string; provider_message_id: string; recipient_email: string; error: string; sent_at: string };

export type Application = {
  id: number;
  job_id: number;
  resume_id: number | null;
  status: string;
  notes: string;
  interview_at: string | null;
  created_at: string;
  updated_at: string;
  job_title: string;
  company: string;
  canonical_url: string;
  match_score: number | null;
  latest_draft_id: number | null;
  draft_status: string | null;
};

export type ApplicationDetail = Application & { events: ApplicationEvent[]; drafts: Draft[]; sends: Send[] };

export type Reminder = { id: number; application_id: number | null; kind: string; due_at: string; note: string; done: boolean; created_at: string; job_title: string };

export type Dashboard = {
  days: number;
  jobs_today: number;
  jobs_in_range: number;
  new_matching: number;
  high_match: number;
  with_public_emails: number;
  drafts_awaiting: number;
  applications_total: number;
  by_status: Record<string, number>;
  upcoming_reminders: Reminder[];
  upcoming_interviews: Application[];
};

export type Notification = { id: number; kind: string; title: string; body: string; link: string; read: boolean; created_at: string };

export type AgentRun = {
  id: number;
  user_id: number | null;
  parent_run_id: number | null;
  agent: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string;
  attempts: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number;
  created_at: string;
};

export type Source = { id: number; key: string; name: string; base_url: string; enabled: boolean; last_run_at: string | null; last_status: string; last_error: string };
export type AdminUser = User & { is_active: boolean; daily_llm_limit: number; applications: number };
export type Health = { status: string; database: string; llm_provider: string; email_provider: string; sources: Source[]; runs_last_24h: Record<string, number> };
export type AuditEntry = { id: number; user_id: number | null; action: string; entity_type: string; entity_id: number | null; details: Record<string, unknown>; created_at: string };

export const APPLICATION_STATUSES = [
  'saved',
  'ready_to_apply',
  'draft_prepared',
  'awaiting_approval',
  'applied',
  'follow_up_due',
  'interview_scheduled',
  'rejected',
  'offer_received',
  'closed',
] as const;

export const TONES = ['professional', 'friendly', 'concise'] as const;
