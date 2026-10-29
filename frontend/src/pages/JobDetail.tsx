import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { Alert, Card, Chip, Empty, Loading, Score } from '../components/ui';
import { fmtDate, fmtDateTime, money } from '../format';
import { useFetch } from '../hooks';
import { TONES, type Contact, type Draft, type JobDetail as JobDetailData, type Resume } from '../types';

const CONTACT_TONE: Record<Contact['status'], 'green' | 'amber' | 'slate' | 'rose'> = {
  PUBLICLY_LISTED: 'green',
  SOURCE_UNVERIFIED: 'amber',
  NOT_FOUND: 'slate',
  BOUNCED: 'rose',
};

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const job = useFetch(() => api.get<JobDetailData>(`/api/jobs/${id}`), [id]);
  const resumes = useFetch(() => api.get<Resume[]>('/api/resumes'), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tone, setTone] = useState<string>('professional');
  const [contactId, setContactId] = useState<number | ''>('');
  const [recipient, setRecipient] = useState('');
  const [resumeId, setResumeId] = useState<number | ''>('');

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
      job.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const draft = async () => {
    setBusy('draft');
    setError(null);
    try {
      const body: Record<string, unknown> = { job_id: Number(id), tone };
      if (contactId) body.contact_id = contactId;
      else if (recipient) body.recipient_email = recipient;
      if (resumeId) body.resume_id = resumeId;
      const d = await api.post<Draft>('/api/applications/drafts', body);
      navigate(`/applications/${d.application_id}?draft=${d.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(null);
    }
  };

  if (job.error) return <Alert>{job.error}</Alert>;
  if (!job.data) return <Loading />;
  const j = job.data;
  const listed = j.contacts.filter((c) => c.status === 'PUBLICLY_LISTED');

  return (
    <div className="space-y-6">
      <Link to="/jobs" className="text-sm text-slate-500 hover:underline">
        ← All jobs
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{j.title}</h1>
          <p className="text-slate-600">
            {j.company}
            {j.location && ` · ${j.location}`}
            {j.work_mode !== 'unknown' && ` · ${j.work_mode}`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {j.source} · {j.posted_at ? `posted ${fmtDate(j.posted_at)}${j.posted_at_verified ? '' : ' (unverified)'}` : 'posting date not provided by the source'} · retrieved {fmtDateTime(j.retrieved_at)} ·{' '}
            <a className="text-indigo-600 hover:underline" href={j.canonical_url} target="_blank" rel="noreferrer">
              original listing
            </a>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Score value={j.match?.score} />
          <button className="btn-secondary" disabled={busy !== null} onClick={() => run('match', () => api.post(`/api/jobs/${id}/match`))}>
            {busy === 'match' ? 'Scoring…' : j.match ? 'Re-score' : 'Score this job'}
          </button>
          <button className="btn-ghost" disabled={busy !== null} onClick={() => run('verify', () => api.post(`/api/jobs/${id}/verify`))}>
            {busy === 'verify' ? 'Checking…' : 'Check if still open'}
          </button>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {j.status !== 'open' && <Alert kind="info">This listing is marked {j.status}.</Alert>}

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-6">
          <Card title="Why this score" subtitle={j.match ? `Scored by ${j.match.model} on ${fmtDateTime(j.match.created_at)}. Each factor only counts when both sides have the information.` : 'Not scored yet'}>
            {!j.match && <Empty title="No score yet" hint="Complete your profile, then score this job." />}
            {j.match && (
              <div className="space-y-4">
                <p className="text-sm">{j.match.explanation}</p>
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <p className="label">Strong matches</p>
                    <div className="flex flex-wrap gap-1.5">
                      {j.match.strong_matches.length === 0 && <span className="text-sm text-slate-500">none</span>}
                      {j.match.strong_matches.map((s) => (
                        <Chip key={s} tone="green">
                          {s}
                        </Chip>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="label">Potential gaps</p>
                    <ul className="space-y-1 text-sm">
                      {j.match.gaps.length === 0 && <li className="text-slate-500">none found</li>}
                      {j.match.gaps.map((g) => (
                        <li key={g.skill}>
                          <Chip tone={g.status === 'gap' ? 'rose' : 'amber'}>{g.status === 'gap' ? 'gap' : 'unconfirmed'}</Chip> <span className="text-slate-700">{g.note}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 uppercase">
                      <th className="py-1">Factor</th>
                      <th>Weight</th>
                      <th>Score</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {j.match.factors.map((f) => (
                      <tr key={f.name} className="border-t border-slate-100">
                        <td className="py-1.5 capitalize">{f.name}</td>
                        <td>{f.weight}</td>
                        <td>{f.status === 'unknown' ? <Chip>unknown</Chip> : `${Math.round((f.score ?? 0) * 100)}%`}</td>
                        <td className="text-slate-600">{f.evidence}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {j.match.unknowns.length > 0 && (
                  <p className="text-xs text-slate-500">Not scored (missing information, not a gap): {j.match.unknowns.join('; ')}.</p>
                )}
              </div>
            )}
          </Card>

          <Card title="Job description" subtitle={`${j.experience_min != null ? `${j.experience_min}${j.experience_max ? '–' + j.experience_max : '+'} years` : 'experience not stated'} · ${j.salary_max != null ? `${money(j.salary_min, j.salary_currency)} – ${money(j.salary_max, j.salary_currency)}` : j.salary_text || 'salary not stated'}`}>
            <div className="mb-3 flex flex-wrap gap-1.5">
              {j.tags.map((t) => (
                <Chip key={t}>{t}</Chip>
              ))}
            </div>
            <pre className="max-h-[32rem] overflow-y-auto font-sans text-sm whitespace-pre-wrap text-slate-700">{j.description}</pre>
          </Card>
        </div>

        <div className="space-y-6">
          <Card
            title="Recruiter contacts"
            subtitle="Only addresses printed in the listing or on its page. Nothing is guessed from names or domains."
            action={
              <button className="btn-secondary text-xs" disabled={busy !== null} onClick={() => run('contacts', () => api.post(`/api/jobs/${id}/contacts`))}>
                {busy === 'contacts' ? 'Looking…' : j.contacts.length ? 'Look again' : 'Look for emails'}
              </button>
            }
          >
            {j.contacts.length === 0 && <Empty title="Not checked yet" />}
            <ul className="space-y-2">
              {j.contacts.map((c) => (
                <li key={c.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{c.email || 'No email published'}</span>
                    <Chip tone={CONTACT_TONE[c.status]}>{c.status.replace(/_/g, ' ')}</Chip>
                  </div>
                  {(c.name || c.role) && (
                    <p className="text-slate-600">
                      {c.name}
                      {c.role && ` · ${c.role}`}
                    </p>
                  )}
                  <p className="text-xs text-slate-500">
                    {c.notes} Source:{' '}
                    <a className="text-indigo-600 hover:underline" href={c.source_url} target="_blank" rel="noreferrer">
                      link
                    </a>{' '}
                    · {fmtDateTime(c.retrieved_at)} · confidence {Math.round(c.confidence * 100)}%
                  </p>
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Prepare an application" subtitle="Creates an editable draft. Nothing is sent until you approve it.">
            {j.application_id ? (
              <Alert kind="info">
                You already have an application for this job ({j.application_status?.replace(/_/g, ' ')}).{' '}
                <Link className="underline" to={`/applications/${j.application_id}`}>
                  Open it
                </Link>
                .
              </Alert>
            ) : (
              <div className="space-y-3">
                <label className="block">
                  <span className="label">Send to</span>
                  <select className="input" value={contactId} onChange={(e) => setContactId(e.target.value ? Number(e.target.value) : '')}>
                    <option value="">{listed.length ? 'choose a listed contact' : 'no public email found'}</option>
                    {listed.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.email}
                        {c.name && ` (${c.name})`}
                      </option>
                    ))}
                  </select>
                </label>
                {!contactId && (
                  <label className="block">
                    <span className="label">Or type the application email yourself</span>
                    <input className="input" type="email" value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="careers@company.com" />
                  </label>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="label">Tone</span>
                    <select className="input" value={tone} onChange={(e) => setTone(e.target.value)}>
                      {TONES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="label">Attach resume</span>
                    <select className="input" value={resumeId} onChange={(e) => setResumeId(e.target.value ? Number(e.target.value) : '')}>
                      <option value="">none</option>
                      {resumes.data?.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.label} ({r.filename})
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button className="btn-primary w-full" disabled={busy !== null} onClick={draft}>
                  {busy === 'draft' ? 'Writing…' : 'Draft application email'}
                </button>
                <button className="btn-ghost w-full" disabled={busy !== null} onClick={() => run('save', () => api.post('/api/applications', { job_id: Number(id) }).then(() => navigate('/applications')))}>
                  Just save to tracker
                </button>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
