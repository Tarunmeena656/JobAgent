import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, query } from '../api';
import { Alert, Card, Chip, Empty, Loading, Score } from '../components/ui';
import { fmtAgo, fmtDate, money } from '../format';
import { useFetch } from '../hooks';
import type { Job, JobList } from '../types';

const SORTS = [
  ['score', 'Match score'],
  ['posted', 'Posting date'],
  ['retrieved', 'Found'],
  ['company', 'Company'],
  ['title', 'Role'],
  ['salary', 'Salary'],
  ['experience', 'Experience'],
];

export default function Jobs() {
  const [params, setParams] = useSearchParams();
  const get = (key: string, fallback = '') => params.get(key) ?? fallback;
  const page = Number(get('page', '1'));
  const [keywords, setKeywords] = useState('');
  const [days, setDays] = useState(30);
  const [searching, setSearching] = useState<string | null>(null);

  const jobs = useFetch(() => api.get<JobList>(`/api/jobs${query(Object.fromEntries(params.entries()))}`), [params.toString()]);

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!('page' in changes)) next.delete('page');
    setParams(next);
  };

  const startSearch = async (e: FormEvent) => {
    e.preventDefault();
    setSearching(null);
    try {
      const res = await api.post<{ keywords: string[] }>('/api/jobs/search', {
        keywords: keywords
          .split(',')
          .map((k) => k.trim())
          .filter(Boolean),
        posted_within_days: days,
      });
      setSearching(`Searching for ${res.keywords.join(', ')}. New jobs, scores and contacts appear here as the agents finish; refresh in a minute.`);
      setTimeout(jobs.reload, 8000);
    } catch (err) {
      setSearching((err as Error).message);
    }
  };

  const pages = jobs.data ? Math.max(1, Math.ceil(jobs.data.total / jobs.data.page_size)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Jobs</h1>
        <p className="text-sm text-slate-500">Discovered from permitted sources, de-duplicated, scored against your profile. Posting dates are shown only when the source gives one.</p>
      </div>

      <Card title="Run a search" subtitle="Leave keywords empty to use the target roles from your profile.">
        <form className="flex flex-wrap items-end gap-3" onSubmit={startSearch}>
          <label className="min-w-64 flex-1">
            <span className="label">Keywords</span>
            <input className="input" value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="node.js developer, python developer" />
          </label>
          <label>
            <span className="label">Posted within</span>
            <select className="input" value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {[7, 14, 30, 60, 90].map((d) => (
                <option key={d} value={d}>
                  {d} days
                </option>
              ))}
            </select>
          </label>
          <button className="btn-primary">Search sources</button>
        </form>
        {searching && (
          <div className="mt-3">
            <Alert kind="info">{searching}</Alert>
          </div>
        )}
      </Card>

      <Card
        title={`${jobs.data?.total ?? 0} jobs`}
        action={
          <button className="btn-ghost text-xs" onClick={jobs.reload}>
            Refresh
          </button>
        }
      >
        <div className="mb-4 grid gap-2 md:grid-cols-4 lg:grid-cols-8">
          <input className="input md:col-span-2" placeholder="Search title, company, text" value={get('q')} onChange={(e) => update({ q: e.target.value })} />
          <input className="input" placeholder="Company" value={get('company')} onChange={(e) => update({ company: e.target.value })} />
          <input className="input" placeholder="Location" value={get('location')} onChange={(e) => update({ location: e.target.value })} />
          <select className="input" value={get('work_mode')} onChange={(e) => update({ work_mode: e.target.value })}>
            <option value="">any mode</option>
            <option value="remote">remote</option>
            <option value="hybrid">hybrid</option>
            <option value="onsite">on-site</option>
          </select>
          <select className="input" value={get('min_score')} onChange={(e) => update({ min_score: e.target.value })}>
            <option value="">any score</option>
            <option value="70">70+</option>
            <option value="50">50+</option>
            <option value="30">30+</option>
          </select>
          <select className="input" value={get('source')} onChange={(e) => update({ source: e.target.value })}>
            <option value="">any source</option>
            <option value="remotive">Remotive</option>
            <option value="arbeitnow">Arbeitnow</option>
          </select>
          <select className="input" value={get('sort', 'score')} onChange={(e) => update({ sort: e.target.value })}>
            {SORTS.map(([k, label]) => (
              <option key={k} value={k}>
                sort: {label}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input type="checkbox" checked={get('with_emails') === 'true'} onChange={(e) => update({ with_emails: e.target.checked ? 'true' : '' })} />
            Only jobs with a public recruiter email
          </label>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input type="checkbox" checked={get('verified_date_only') === 'true'} onChange={(e) => update({ verified_date_only: e.target.checked ? 'true' : '' })} />
            Only verified posting dates
          </label>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input type="checkbox" checked={get('status') === 'all'} onChange={(e) => update({ status: e.target.checked ? 'all' : '' })} />
            Include expired
          </label>
        </div>

        {jobs.error && <Alert>{jobs.error}</Alert>}
        {jobs.loading && <Loading />}
        {jobs.data && jobs.data.items.length === 0 && <Empty title="No jobs match these filters" hint="Run a search above or loosen the filters." />}
        <ul className="divide-y divide-slate-100">
          {jobs.data?.items.map((job) => (
            <JobRow key={job.id} job={job} />
          ))}
        </ul>

        {pages > 1 && (
          <div className="mt-4 flex items-center justify-end gap-2 text-sm">
            <button className="btn-secondary" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
              Previous
            </button>
            <span>
              Page {page} of {pages}
            </span>
            <button className="btn-secondary" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>
              Next
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}

function JobRow({ job }: { job: Job }) {
  return (
    <li className="flex flex-wrap items-start gap-3 py-3">
      <Score value={job.match?.score} />
      <div className="min-w-0 flex-1">
        <Link to={`/jobs/${job.id}`} className="font-medium hover:underline">
          {job.title}
        </Link>
        <p className="text-sm text-slate-600">
          {job.company}
          {job.location && ` · ${job.location}`}
          {job.work_mode !== 'unknown' && ` · ${job.work_mode}`}
          {job.experience_min != null && ` · ${job.experience_min}${job.experience_max ? '–' + job.experience_max : '+'} yrs`}
          {job.salary_max != null && ` · ${money(job.salary_min, job.salary_currency)} – ${money(job.salary_max, job.salary_currency)}`}
        </p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {job.match?.strong_matches.slice(0, 5).map((s) => (
            <Chip key={s} tone="brand">
              {s}
            </Chip>
          ))}
          {job.public_emails > 0 && <Chip tone="green">public email</Chip>}
          {job.status !== 'open' && <Chip tone="rose">{job.status}</Chip>}
          {job.application_status && <Chip tone="sky">{job.application_status.replace(/_/g, ' ')}</Chip>}
        </div>
      </div>
      <div className="text-right text-xs text-slate-500">
        <p>{job.source}</p>
        <p>{job.posted_at ? `posted ${fmtDate(job.posted_at)}${job.posted_at_verified ? '' : ' (unverified)'}` : 'posting date unknown'}</p>
        <p>found {fmtAgo(job.retrieved_at)}</p>
      </div>
    </li>
  );
}
