import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Alert, Card, Chip, Empty, Field, Loading, Score } from '../components/ui';
import { fmtDateTime, fromLocalInput, statusLabel, toLocalInput } from '../format';
import { useFetch } from '../hooks';
import { APPLICATION_STATUSES, TONES, type ApplicationDetail as ApplicationDetailData, type Draft, type Resume } from '../types';

export default function ApplicationDetail() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const app = useFetch(() => api.get<ApplicationDetailData>(`/api/applications/${id}`), [id]);
  const resumes = useFetch(() => api.get<Resume[]>('/api/resumes'), []);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [status, setStatus] = useState('');
  const [interviewAt, setInterviewAt] = useState('');

  useEffect(() => {
    if (!app.data) return;
    setNotes(app.data.notes);
    setStatus(app.data.status);
    setInterviewAt(toLocalInput(app.data.interview_at));
    const wanted = Number(params.get('draft'));
    const chosen = app.data.drafts.find((d) => d.id === wanted) ?? app.data.drafts[0] ?? null;
    setDraft(chosen);
    setDirty(false);
  }, [app.data, params]);

  const act = async (label: string, fn: () => Promise<unknown>, done?: string) => {
    setBusy(label);
    setError(null);
    setMessage(null);
    try {
      await fn();
      if (done) setMessage(done);
      app.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const saveDraft = () =>
    act('save', async () => {
      if (!draft) return;
      const saved = await api.patch<Draft>(`/api/applications/drafts/${draft.id}`, {
        subject: draft.subject,
        body: draft.body,
        recipient_email: draft.recipient_email || undefined,
        tone: draft.tone,
        attachments: draft.attachments,
      });
      setDraft(saved);
      setDirty(false);
    }, 'Draft saved. Approve it again before sending.');

  const regenerate = (section: string) =>
    act(`regen-${section}`, async () => {
      if (!draft) return;
      const next = await api.post<Draft>(`/api/applications/drafts/${draft.id}/regenerate`, { section, tone: draft.tone });
      setDraft(next);
      setDirty(false);
    });

  const approve = () => act('approve', () => api.post(`/api/applications/${id}/approve`, { draft_id: draft?.id }), 'Approved. You can send it now.');
  const send = () =>
    act('send', async () => {
      const res = await api.post<{ status: string; error: string; provider: string }>(`/api/applications/${id}/send`, { draft_id: draft?.id });
      if (res.status !== 'sent') throw new Error(`Send failed: ${res.error}`);
      setMessage(`Sent through the ${res.provider} provider. A follow-up reminder was added for next week.`);
    });

  const saveTracker = () =>
    act('tracker', () => api.patch(`/api/applications/${id}`, { status, notes, interview_at: interviewAt ? fromLocalInput(interviewAt) : undefined }), 'Tracker updated.');

  const newDraft = () =>
    act('new', async () => {
      const d = await api.post<Draft>('/api/applications/drafts', { job_id: app.data!.job_id, tone: 'professional' });
      setParams({ draft: String(d.id) });
    });

  if (app.error) return <Alert>{app.error}</Alert>;
  if (!app.data) return <Loading />;
  const a = app.data;

  return (
    <div className="space-y-6">
      <Link to="/applications" className="text-sm text-slate-500 hover:underline">
        ← All applications
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{a.job_title}</h1>
          <p className="text-slate-600">
            {a.company} ·{' '}
            <Link className="text-link" to={`/jobs/${a.job_id}`}>
              job details
            </Link>{' '}
            ·{' '}
            <a className="text-link" href={a.canonical_url} target="_blank" rel="noreferrer">
              original listing
            </a>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Score value={a.match_score} />
          <Chip tone="sky">{statusLabel(a.status)}</Chip>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {message && <Alert kind="success">{message}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Card
          title="Application email"
          subtitle="Edit anything. Approval covers the exact recipient, subject, body and attachments shown; any later edit needs a new approval."
          action={
            a.drafts.length > 1 ? (
              <select className="input w-auto" value={draft?.id ?? ''} onChange={(e) => setParams({ draft: e.target.value })}>
                {a.drafts.map((d) => (
                  <option key={d.id} value={d.id}>
                    draft #{d.id} · {d.status} · {d.tone}
                  </option>
                ))}
              </select>
            ) : undefined
          }
        >
          {!draft && <Empty title="No draft yet" action={<button className="btn-primary" disabled={busy !== null} onClick={newDraft}>Draft an email</button>} />}
          {draft && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <Chip tone={draft.status === 'sent' ? 'green' : draft.approved ? 'brand' : 'amber'}>{draft.status === 'sent' ? 'sent' : draft.approved ? 'approved' : 'needs approval'}</Chip>
                <span>generated by {draft.generated_by}</span>
                <span>· updated {fmtDateTime(draft.updated_at)}</span>
                {dirty && <span className="text-amber-700">· unsaved changes</span>}
              </div>
              <div className="grid gap-3 md:grid-cols-[2fr_1fr]">
                <Field label="To">
                  <input className="input" type="email" value={draft.recipient_email} disabled={draft.status === 'sent'} onChange={(e) => (setDraft({ ...draft, recipient_email: e.target.value }), setDirty(true))} />
                </Field>
                <Field label="Tone">
                  <select className="input" value={draft.tone} disabled={draft.status === 'sent'} onChange={(e) => (setDraft({ ...draft, tone: e.target.value }), setDirty(true))}>
                    {TONES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Subject">
                <input className="input" value={draft.subject} disabled={draft.status === 'sent'} onChange={(e) => (setDraft({ ...draft, subject: e.target.value }), setDirty(true))} />
              </Field>
              <Field label="Body">
                <textarea className="input font-mono text-sm" rows={16} value={draft.body} disabled={draft.status === 'sent'} onChange={(e) => (setDraft({ ...draft, body: e.target.value }), setDirty(true))} />
              </Field>
              <Field label="Attachments">
                <div className="flex flex-wrap gap-3 text-sm">
                  {resumes.data?.length === 0 && <span className="text-slate-500">No resumes uploaded.</span>}
                  {resumes.data?.map((r) => (
                    <label key={r.id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        disabled={draft.status === 'sent'}
                        checked={draft.attachments.includes(r.id)}
                        onChange={(e) => (setDraft({ ...draft, attachments: e.target.checked ? [...draft.attachments, r.id] : draft.attachments.filter((x) => x !== r.id) }), setDirty(true))}
                      />
                      {r.label} ({r.filename})
                    </label>
                  ))}
                </div>
              </Field>
              {draft.status !== 'sent' && (
                <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                  <button className="btn-secondary" disabled={busy !== null || !dirty} onClick={saveDraft}>
                    {busy === 'save' ? 'Saving…' : 'Save changes'}
                  </button>
                  <div className="flex items-center gap-1 text-xs text-slate-500">
                    Rewrite:
                    {['intro', 'fit', 'logistics', 'closing', 'all'].map((s) => (
                      <button key={s} className="btn-ghost px-2 py-1 text-xs" disabled={busy !== null} onClick={() => regenerate(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                  <div className="ml-auto flex gap-2">
                    <button className="btn-secondary" disabled={busy !== null || dirty || draft.approved} onClick={approve}>
                      {busy === 'approve' ? 'Approving…' : draft.approved ? 'Approved' : 'Approve this email'}
                    </button>
                    <button className="btn-primary" disabled={busy !== null || dirty || !draft.approved} onClick={send} title={draft.approved ? 'Send through the configured email provider' : 'Approve first'}>
                      {busy === 'send' ? 'Sending…' : 'Send'}
                    </button>
                  </div>
                </div>
              )}
              {draft.status === 'sent' && (
                <div className="flex justify-end">
                  <button className="btn-ghost" disabled={busy !== null} onClick={newDraft}>
                    Write a follow-up draft
                  </button>
                </div>
              )}
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <Card title="Tracker">
            <div className="space-y-3">
              <Field label="Status">
                <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                  {APPLICATION_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {statusLabel(s)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Interview date and time" hint="Setting it creates an interview reminder.">
                <input className="input" type="datetime-local" value={interviewAt} onChange={(e) => setInterviewAt(e.target.value)} />
              </Field>
              <Field label="Notes">
                <textarea className="input" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Interview details, recruiter name, what was discussed" />
              </Field>
              <button className="btn-secondary w-full" disabled={busy !== null} onClick={saveTracker}>
                {busy === 'tracker' ? 'Saving…' : 'Update tracker'}
              </button>
            </div>
          </Card>

          <Card title="Sends" subtitle="What actually left the system">
            {a.sends.length === 0 && <p className="text-sm text-slate-500">Nothing sent yet.</p>}
            <ul className="space-y-2 text-sm">
              {a.sends.map((s) => (
                <li key={s.id} className="rounded-lg bg-slate-50 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <span>{s.recipient_email}</span>
                    <Chip tone={s.status === 'sent' ? 'green' : 'rose'}>{s.status}</Chip>
                  </div>
                  <p className="text-xs text-slate-500">
                    {fmtDateTime(s.sent_at)} · {s.provider}
                    {s.provider_message_id && ` · ${s.provider_message_id}`}
                  </p>
                  {s.error && <p className="text-xs text-rose-700">{s.error}</p>}
                </li>
              ))}
            </ul>
          </Card>

          <Card title="History">
            <ul className="space-y-1 text-sm">
              {a.events.map((e) => (
                <li key={e.id} className="flex justify-between gap-2">
                  <span>
                    {statusLabel(e.event_type)}
                    {e.to_status && e.to_status !== e.from_status && <span className="text-slate-500"> → {statusLabel(e.to_status)}</span>}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">{fmtDateTime(e.created_at)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
