import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Alert, Card, Chip, Empty, Loading, Score } from '../components/ui';
import { fmtAgo, fmtDateTime, fromLocalInput, statusLabel } from '../format';
import { useFetch } from '../hooks';
import { APPLICATION_STATUSES, type Application, type Draft, type Reminder } from '../types';

const STATUS_TONE: Record<string, 'slate' | 'brand' | 'green' | 'amber' | 'rose' | 'sky'> = {
  saved: 'slate',
  ready_to_apply: 'brand',
  draft_prepared: 'brand',
  awaiting_approval: 'amber',
  applied: 'sky',
  follow_up_due: 'amber',
  interview_scheduled: 'green',
  rejected: 'rose',
  offer_received: 'green',
  closed: 'slate',
};

export default function Applications() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const apps = useFetch(() => api.get<Application[]>(`/api/applications${status ? `?status=${status}` : ''}`), [status]);
  const drafts = useFetch(() => api.get<Draft[]>('/api/applications/drafts?status=draft'), []);
  const reminders = useFetch(() => api.get<Reminder[]>('/api/applications/reminders'), []);
  const [newReminder, setNewReminder] = useState({ application_id: '', kind: 'follow_up', due_at: '', note: '' });
  const [error, setError] = useState<string | null>(null);

  const addReminder = async () => {
    setError(null);
    try {
      await api.post('/api/applications/reminders', {
        application_id: newReminder.application_id ? Number(newReminder.application_id) : null,
        kind: newReminder.kind,
        due_at: fromLocalInput(newReminder.due_at),
        note: newReminder.note,
      });
      setNewReminder({ application_id: '', kind: 'follow_up', due_at: '', note: '' });
      reminders.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const finish = async (r: Reminder) => {
    await api.patch(`/api/applications/reminders/${r.id}`, { done: true });
    reminders.reload();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Applications</h1>
        <p className="text-sm text-slate-500">Every job you saved or applied to, with its draft, status history and reminders.</p>
      </div>
      {error && <Alert>{error}</Alert>}

      {drafts.data && drafts.data.length > 0 && (
        <Card title={`${drafts.data.length} draft${drafts.data.length > 1 ? 's' : ''} waiting for your approval`} subtitle="Nothing goes out until you approve it.">
          <ul className="divide-y divide-slate-100">
            {drafts.data.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div>
                  <p className="font-medium">
                    {d.job_title} · {d.company}
                  </p>
                  <p className="text-xs text-slate-500">
                    to {d.recipient_email || 'no recipient yet'} · {d.tone} · {fmtAgo(d.updated_at)}
                  </p>
                </div>
                <Link className="btn-primary" to={`/applications/${d.application_id}?draft=${d.id}`}>
                  Review
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Card
          title="Tracker"
          action={
            <select className="input w-auto" value={status} onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}>
              <option value="">all statuses</option>
              {APPLICATION_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {statusLabel(s)}
                </option>
              ))}
            </select>
          }
        >
          {apps.error && <Alert>{apps.error}</Alert>}
          {apps.loading && <Loading />}
          {apps.data?.length === 0 && <Empty title="No applications here" hint="Open a job and draft an application or save it to the tracker." action={<Link className="btn-primary" to="/jobs">Browse jobs</Link>} />}
          <ul className="divide-y divide-slate-100">
            {apps.data?.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                <Score value={a.match_score} />
                <div className="min-w-0 flex-1">
                  <Link to={`/applications/${a.id}`} className="font-medium hover:underline">
                    {a.job_title}
                  </Link>
                  <p className="text-slate-600">
                    {a.company} · updated {fmtAgo(a.updated_at)}
                    {a.interview_at && ` · interview ${fmtDateTime(a.interview_at)}`}
                  </p>
                </div>
                <Chip tone={STATUS_TONE[a.status] ?? 'slate'}>{statusLabel(a.status)}</Chip>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Reminders" subtitle="Follow-ups are added automatically a week after you send; interviews when you schedule them.">
          <ul className="space-y-2">
            {reminders.data?.length === 0 && <Empty title="Nothing pending" />}
            {reminders.data?.map((r) => (
              <li key={r.id} className="flex items-start justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <div>
                  <p className="font-medium capitalize">
                    {statusLabel(r.kind)}
                    {r.job_title && <span className="font-normal text-slate-600"> · {r.job_title}</span>}
                  </p>
                  <p className="text-xs text-slate-500">
                    {fmtDateTime(r.due_at)}
                    {r.note && ` · ${r.note}`}
                  </p>
                </div>
                <button className="btn-ghost px-2 py-1 text-xs" onClick={() => finish(r)}>
                  Done
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-4 grid gap-2 border-t border-slate-100 pt-4">
            <p className="label">Add a reminder</p>
            <select className="input" value={newReminder.application_id} onChange={(e) => setNewReminder({ ...newReminder, application_id: e.target.value })}>
              <option value="">not linked to an application</option>
              {apps.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.job_title} · {a.company}
                </option>
              ))}
            </select>
            <div className="grid grid-cols-2 gap-2">
              <select className="input" value={newReminder.kind} onChange={(e) => setNewReminder({ ...newReminder, kind: e.target.value })}>
                <option value="follow_up">follow up</option>
                <option value="interview">interview</option>
                <option value="custom">custom</option>
              </select>
              <input className="input" type="datetime-local" value={newReminder.due_at} onChange={(e) => setNewReminder({ ...newReminder, due_at: e.target.value })} />
            </div>
            <input className="input" placeholder="Note" value={newReminder.note} onChange={(e) => setNewReminder({ ...newReminder, note: e.target.value })} />
            <button className="btn-secondary" disabled={!newReminder.due_at} onClick={addReminder}>
              Add reminder
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}
