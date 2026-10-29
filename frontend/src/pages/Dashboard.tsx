import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Alert, Card, Empty, Loading, Stat } from '../components/ui';
import { fmtDateTime, statusLabel } from '../format';
import { useFetch } from '../hooks';
import type { Dashboard as DashboardData } from '../types';

export default function Dashboard() {
  const [days, setDays] = useState(7);
  const { data, error, loading, reload } = useFetch(() => api.get<DashboardData>(`/api/dashboard/summary?days=${days}`), [days]);

  if (error) return <Alert>{error}</Alert>;
  if (loading || !data) return <Loading />;

  const statuses = Object.entries(data.by_status).filter(([, n]) => n > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-slate-500">What the agents found and what is waiting for you.</p>
        </div>
        <label className="text-sm text-slate-600">
          Range{' '}
          <select className="input inline-block w-auto" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[1, 7, 14, 30, 90].map((d) => (
              <option key={d} value={d}>
                last {d} day{d > 1 ? 's' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Jobs found today" value={data.jobs_today} hint={`${data.jobs_in_range} in the last ${data.days} days`} />
        <Stat label="New jobs that fit" value={data.new_matching} hint="score 50 or more, in range" />
        <Stat label="High matches" value={data.high_match} hint="score 70 or more" tone="good" />
        <Stat label="With a public recruiter email" value={data.with_public_emails} hint="among your matched jobs" />
        <Stat label="Drafts awaiting approval" value={data.drafts_awaiting} tone={data.drafts_awaiting ? 'warn' : 'default'} />
        <Stat label="Applications" value={data.applications_total} />
        <Stat label="Follow-ups and interviews due" value={data.upcoming_reminders.length} hint={`next ${data.days} days`} />
        <Stat label="Interviews scheduled" value={data.by_status.interview_scheduled ?? 0} tone="good" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Application status" subtitle="Click through to the tracker">
          {statuses.length === 0 ? (
            <Empty title="No applications yet" hint="Run a job search, pick a match and draft an application." action={<Link className="btn-primary" to="/jobs">Find jobs</Link>} />
          ) : (
            <ul className="divide-y divide-slate-100">
              {statuses.map(([status, n]) => (
                <li key={status} className="flex items-center justify-between py-2 text-sm">
                  <Link to={`/applications?status=${status}`} className="capitalize hover:underline">
                    {statusLabel(status)}
                  </Link>
                  <span className="font-semibold">{n}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Coming up" subtitle="Follow-ups and interviews" action={<button className="btn-ghost text-xs" onClick={reload}>Refresh</button>}>
          {data.upcoming_reminders.length === 0 && data.upcoming_interviews.length === 0 ? (
            <Empty title="Nothing due" hint="Reminders are created when you send an application or schedule an interview." />
          ) : (
            <ul className="space-y-2">
              {data.upcoming_interviews.map((app) => (
                <li key={`i${app.id}`} className="rounded-lg bg-emerald-50 px-3 py-2 text-sm">
                  <Link to={`/applications/${app.id}`} className="font-medium hover:underline">
                    Interview: {app.job_title} at {app.company}
                  </Link>
                  <p className="text-xs text-emerald-800">{fmtDateTime(app.interview_at)}</p>
                </li>
              ))}
              {data.upcoming_reminders.map((r) => (
                <li key={r.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <p className="font-medium capitalize">
                    {statusLabel(r.kind)}
                    {r.job_title && <span className="font-normal text-slate-600"> · {r.job_title}</span>}
                  </p>
                  <p className="text-xs text-slate-500">
                    {fmtDateTime(r.due_at)}
                    {r.note && ` · ${r.note}`}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
