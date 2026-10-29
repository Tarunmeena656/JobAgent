import { useState } from 'react';
import { api } from '../api';
import { Alert, Card, Chip, Empty, Loading } from '../components/ui';
import { fmtAgo, fmtDateTime } from '../format';
import { useFetch } from '../hooks';
import type { AgentRun, Notification } from '../types';

const TONE: Record<AgentRun['status'], 'green' | 'rose' | 'amber' | 'slate'> = { succeeded: 'green', failed: 'rose', running: 'amber', queued: 'slate' };

export default function Runs() {
  const [agent, setAgent] = useState('');
  const runs = useFetch(() => api.get<AgentRun[]>(`/api/agent-runs?limit=100${agent ? `&agent=${agent}` : ''}`), [agent]);
  const notes = useFetch(() => api.get<Notification[]>('/api/notifications'), []);
  const [open, setOpen] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const retry = async (run: AgentRun) => {
    await api.post(`/api/agent-runs/${run.id}/retry`);
    setMessage('Search restarted. Refresh in a few seconds.');
    setTimeout(runs.reload, 3000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Agent activity</h1>
        <p className="text-sm text-slate-500">Every agent run with its input, output, attempts, timing and model usage. Failed runs keep their error.</p>
      </div>
      {message && <Alert kind="info">{message}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card
          title="Runs"
          action={
            <div className="flex items-center gap-2">
              <select className="input w-auto" value={agent} onChange={(e) => setAgent(e.target.value)}>
                <option value="">all agents</option>
                {['pipeline', 'discovery', 'matcher', 'contacts', 'email_writer', 'resume_parser'].map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
              <button className="btn-secondary" onClick={runs.reload}>
                Refresh
              </button>
            </div>
          }
        >
          {runs.error && <Alert>{runs.error}</Alert>}
          {runs.loading && <Loading />}
          {runs.data?.length === 0 && <Empty title="No runs yet" hint="Start a job search or upload a resume." />}
          <ul className="divide-y divide-slate-100">
            {runs.data?.map((run) => (
              <li key={run.id} className="py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={TONE[run.status]}>{run.status}</Chip>
                  <span className="font-medium">{run.agent}</span>
                  <span className="text-slate-500">#{run.id}</span>
                  {run.parent_run_id && <span className="text-xs text-slate-400">part of #{run.parent_run_id}</span>}
                  <span className="ml-auto text-xs text-slate-500">
                    {fmtAgo(run.created_at)} · {run.duration_ms} ms · {run.attempts} attempt{run.attempts === 1 ? '' : 's'}
                    {run.tokens_in + run.tokens_out > 0 && ` · ${run.tokens_in + run.tokens_out} tokens · $${run.cost_usd.toFixed(4)}`}
                  </span>
                  <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setOpen(open === run.id ? null : run.id)}>
                    {open === run.id ? 'Hide' : 'Details'}
                  </button>
                  {run.agent === 'pipeline' && (
                    <button className="btn-secondary px-2 py-1 text-xs" onClick={() => retry(run)}>
                      Run again
                    </button>
                  )}
                </div>
                {run.error && <p className="mt-1 text-xs text-rose-700">{run.error}</p>}
                {open === run.id && (
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    <pre className="overflow-x-auto rounded-lg bg-slate-50 p-2 text-xs">input: {JSON.stringify(run.input, null, 1)}</pre>
                    <pre className="overflow-x-auto rounded-lg bg-slate-50 p-2 text-xs">output: {JSON.stringify(run.output, null, 1)}</pre>
                    <p className="text-xs text-slate-500 md:col-span-2">
                      started {fmtDateTime(run.started_at)} · finished {fmtDateTime(run.finished_at)}
                    </p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Notifications" action={<button className="btn-ghost text-xs" onClick={() => api.post('/api/notifications/read-all').then(notes.reload)}>Mark all read</button>}>
          {notes.data?.length === 0 && <Empty title="No notifications" />}
          <ul className="space-y-2">
            {notes.data?.map((n) => (
              <li key={n.id} className={`rounded-lg px-3 py-2 text-sm ${n.read ? 'bg-white' : 'bg-indigo-50'}`}>
                <p className="font-medium">{n.title}</p>
                {n.body && <p className="text-xs text-slate-600">{n.body}</p>}
                <p className="text-xs text-slate-400">
                  {n.kind} · {fmtAgo(n.created_at)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
