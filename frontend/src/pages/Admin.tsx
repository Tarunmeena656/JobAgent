import { api } from '../api';
import { Alert, Card, Chip, Loading, Stat } from '../components/ui';
import { fmtDateTime } from '../format';
import { useFetch } from '../hooks';
import type { AdminUser, AuditEntry, Health, Source } from '../types';

export default function Admin() {
  const health = useFetch(() => api.get<Health>('/api/admin/health'), []);
  const users = useFetch(() => api.get<AdminUser[]>('/api/admin/users'), []);
  const sources = useFetch(() => api.get<Source[]>('/api/admin/sources'), []);
  const audit = useFetch(() => api.get<AuditEntry[]>('/api/admin/audit-logs?limit=50'), []);

  const toggleSource = async (s: Source) => {
    await api.patch(`/api/admin/sources/${s.id}`, { enabled: !s.enabled });
    sources.reload();
    health.reload();
  };

  const toggleUser = async (u: AdminUser) => {
    await api.patch(`/api/admin/users/${u.id}`, { is_active: !u.is_active });
    users.reload();
  };

  const setLimit = async (u: AdminUser) => {
    const value = prompt(`Daily LLM call limit for ${u.email}`, String(u.daily_llm_limit));
    if (value === null) return;
    await api.patch(`/api/admin/users/${u.id}`, { daily_llm_limit: Number(value) });
    users.reload();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-slate-500">Users, job sources, usage limits and system health.</p>
      </div>

      {health.error && <Alert>{health.error}</Alert>}
      {health.data && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="System" value={health.data.status} tone={health.data.status === 'ok' ? 'good' : 'bad'} hint={`database ${health.data.database}`} />
          <Stat label="LLM provider" value={health.data.llm_provider} hint={health.data.llm_provider === 'mock' ? 'templates only, no model calls' : 'model calls enabled'} />
          <Stat label="Email provider" value={health.data.email_provider} hint={health.data.email_provider === 'console' ? 'emails are logged, not sent' : 'real sending'} />
          <Stat
            label="Agent runs, 24 h"
            value={Object.values(health.data.runs_last_24h).reduce((a, b) => a + b, 0)}
            hint={Object.entries(health.data.runs_last_24h)
              .map(([k, v]) => `${k} ${v}`)
              .join(' · ')}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Job sources" subtitle="Public APIs that permit use. Disable a source to keep it out of searches.">
          {sources.loading && <Loading />}
          <ul className="divide-y divide-slate-100 text-sm">
            {sources.data?.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-2">
                <div>
                  <p className="font-medium">
                    {s.name} <span className="font-normal text-slate-500">({s.key})</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {s.base_url} · last run {fmtDateTime(s.last_run_at)} · <Chip tone={s.last_status === 'ok' ? 'green' : s.last_status === 'failed' ? 'rose' : 'slate'}>{s.last_status}</Chip>
                  </p>
                  {s.last_error && <p className="text-xs text-rose-700">{s.last_error}</p>}
                </div>
                <button className="btn-secondary" onClick={() => toggleSource(s)}>
                  {s.enabled ? 'Disable' : 'Enable'}
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Users">
          {users.loading && <Loading />}
          <ul className="divide-y divide-slate-100 text-sm">
            {users.data?.map((u) => (
              <li key={u.id} className="flex items-center justify-between gap-3 py-2">
                <div>
                  <p className="font-medium">
                    {u.name} <Chip tone={u.role === 'admin' ? 'brand' : 'slate'}>{u.role}</Chip> {!u.is_active && <Chip tone="rose">disabled</Chip>}
                  </p>
                  <p className="text-xs text-slate-500">
                    {u.email} · {u.applications} applications · LLM limit {u.daily_llm_limit}/day
                  </p>
                </div>
                <div className="flex gap-1">
                  <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setLimit(u)}>
                    Limit
                  </button>
                  <button className="btn-secondary px-2 py-1 text-xs" onClick={() => toggleUser(u)}>
                    {u.is_active ? 'Disable' : 'Enable'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Audit log" subtitle="Security-relevant actions and approvals">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 uppercase">
                <th className="py-1">When</th>
                <th>User</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {audit.data?.map((e) => (
                <tr key={e.id} className="border-t border-slate-100">
                  <td className="py-1 whitespace-nowrap">{fmtDateTime(e.created_at)}</td>
                  <td>{e.user_id ?? '–'}</td>
                  <td>{e.action}</td>
                  <td>
                    {e.entity_type} {e.entity_id ?? ''}
                  </td>
                  <td className="max-w-md truncate text-xs text-slate-500">{JSON.stringify(e.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
