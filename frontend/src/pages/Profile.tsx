import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import { Alert, Card, Chip, Empty, Field, Loading, Modal, TagInput } from '../components/ui';
import { fmtDate } from '../format';
import { useFetch } from '../hooks';
import type { Profile as ProfileData, Resume } from '../types';

const WORK_MODES = ['remote', 'hybrid', 'onsite'];

export default function Profile() {
  const { user, logout } = useAuth();
  const profile = useFetch(() => api.get<ProfileData>('/api/profile'), []);
  const resumes = useFetch(() => api.get<Resume[]>('/api/resumes'), []);
  const [form, setForm] = useState<ProfileData | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [review, setReview] = useState<Resume | null>(null);

  useEffect(() => {
    if (profile.data) setForm(profile.data);
  }, [profile.data]);

  const set = <K extends keyof ProfileData>(key: K, value: ProfileData[K]) => setForm((f) => (f ? { ...f, [key]: value } : f));

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setError(null);
    try {
      const { id, user_id, updated_at, ...body } = form;
      void id;
      void user_id;
      void updated_at;
      const next = await api.patch<ProfileData>('/api/profile', body);
      setForm(next);
      setSaved('Profile saved. Matches are being recalculated in the background.');
      setTimeout(() => setSaved(null), 4000);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const upload = async (file: File, label: string) => {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('label', label || 'General');
      const resume = await api.upload<Resume>('/api/resumes/upload', fd);
      resumes.reload();
      setReview(resume);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const remove = async (resume: Resume) => {
    if (!confirm(`Delete ${resume.filename}?`)) return;
    await api.delete(`/api/resumes/${resume.id}`);
    resumes.reload();
  };

  const deleteAccount = async () => {
    if (!confirm('Delete your account, resumes, applications and contact records? This cannot be undone.')) return;
    await api.delete('/api/profile');
    await logout();
  };

  if (profile.error) return <Alert>{profile.error}</Alert>;
  if (!form) return <Loading />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Profile & resume</h1>
        <p className="text-sm text-slate-500">Everything the agents know about you. Nothing here is sent anywhere without your approval.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      {saved && <Alert kind="success">{saved}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <form className="space-y-6" onSubmit={save}>
          <Card title="About you">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Headline">
                <input className="input" value={form.headline} onChange={(e) => set('headline', e.target.value)} placeholder="Full-Stack Developer (Node.js, React)" />
              </Field>
              <Field label="Years of experience">
                <input className="input" type="number" step="0.1" min={0} value={form.experience_years ?? ''} onChange={(e) => set('experience_years', e.target.value === '' ? null : Number(e.target.value))} />
              </Field>
              <div className="md:col-span-2">
                <Field label="Summary">
                  <textarea className="input" rows={3} value={form.summary} onChange={(e) => set('summary', e.target.value)} />
                </Field>
              </div>
              <div className="md:col-span-2">
                <Field label="Skills" hint="Comma separated. Names are normalised (node → Node.js).">
                  <TagInput value={form.skills} onChange={(v) => set('skills', v)} />
                </Field>
              </div>
              <div className="md:col-span-2">
                <Field label="Target roles" hint="Used for job searches and the role-relevance part of the score.">
                  <TagInput value={form.target_roles} onChange={(v) => set('target_roles', v)} placeholder="Node.js Developer, Python Developer, AI Engineer" />
                </Field>
              </div>
            </div>
          </Card>

          <Card title="Preferences">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Current CTC">
                <input className="input" type="number" min={0} value={form.current_ctc ?? ''} onChange={(e) => set('current_ctc', e.target.value === '' ? null : Number(e.target.value))} />
              </Field>
              <Field label="Expected CTC">
                <input className="input" type="number" min={0} value={form.expected_ctc ?? ''} onChange={(e) => set('expected_ctc', e.target.value === '' ? null : Number(e.target.value))} />
              </Field>
              <Field label="Currency">
                <input className="input" value={form.ctc_currency} onChange={(e) => set('ctc_currency', e.target.value.toUpperCase())} maxLength={8} />
              </Field>
              <Field label="Notice period (days)">
                <input className="input" type="number" min={0} value={form.notice_period_days ?? ''} onChange={(e) => set('notice_period_days', e.target.value === '' ? null : Number(e.target.value))} />
              </Field>
              <Field label="Availability">
                <input className="input" value={form.availability} onChange={(e) => set('availability', e.target.value)} placeholder="Immediately / from 1 Dec" />
              </Field>
              <Field label="Preferred locations">
                <TagInput value={form.preferred_locations} onChange={(v) => set('preferred_locations', v)} placeholder="Pune, Bengaluru, Remote" />
              </Field>
              <div className="md:col-span-2">
                <span className="label">Work mode</span>
                <div className="flex gap-4">
                  {WORK_MODES.map((mode) => (
                    <label key={mode} className="flex items-center gap-2 text-sm capitalize">
                      <input
                        type="checkbox"
                        checked={form.work_modes.includes(mode)}
                        onChange={(e) => set('work_modes', e.target.checked ? [...form.work_modes, mode] : form.work_modes.filter((m) => m !== mode))}
                      />
                      {mode}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <Card title="Experience, education and projects" subtitle="Filled from an approved resume. Edit the text freely, one entry per line.">
            <div className="grid gap-4">
              <Field label="Experience (title @ company, start – end: what you did)">
                <textarea
                  className="input font-mono text-xs"
                  rows={5}
                  value={form.experience.map((e) => `${e.title ?? ''}${e.company ? ' @ ' + e.company : ''}${e.start ? ', ' + e.start : ''}${e.end ? ' – ' + e.end : ''}: ${e.text ?? ''}`).join('\n')}
                  onChange={(e) =>
                    set(
                      'experience',
                      e.target.value
                        .split('\n')
                        .filter((l) => l.trim())
                        .map((line) => {
                          const [head, ...rest] = line.split(':');
                          const [titleCompany, dates] = head.split(',');
                          const [title, company] = (titleCompany ?? '').split('@');
                          const [start, end] = (dates ?? '').split('–');
                          return { title: title?.trim(), company: company?.trim(), start: start?.trim(), end: end?.trim(), text: rest.join(':').trim() };
                        }),
                    )
                  }
                />
              </Field>
              <Field label="Education">
                <textarea className="input" rows={2} value={form.education.map((e) => e.text).join('\n')} onChange={(e) => set('education', e.target.value.split('\n').filter((l) => l.trim()).map((text) => ({ text })))} />
              </Field>
              <Field label="Projects">
                <textarea className="input" rows={3} value={form.projects.map((p) => p.text).join('\n')} onChange={(e) => set('projects', e.target.value.split('\n').filter((l) => l.trim()).map((text) => ({ text })))} />
              </Field>
            </div>
          </Card>

          <div className="flex items-center justify-between">
            <button type="button" className="btn-ghost text-rose-600" onClick={deleteAccount}>
              Delete my account and data
            </button>
            <button className="btn-primary">Save profile</button>
          </div>
        </form>

        <div className="space-y-6">
          <Card title="Resumes" subtitle="PDF or DOCX, up to 5 MB. Parsed on upload, you review before it touches the profile.">
            <label className="btn-secondary w-full cursor-pointer">
              {uploading ? 'Parsing…' : 'Upload a resume'}
              <input
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                disabled={uploading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload(file, prompt('Label for this version (e.g. Backend, AI, General)', 'General') ?? 'General');
                  e.target.value = '';
                }}
              />
            </label>
            <ul className="mt-4 space-y-2">
              {resumes.data?.length === 0 && <Empty title="No resume yet" />}
              {resumes.data?.map((r) => (
                <li key={r.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{r.label}</p>
                      <p className="truncate text-xs text-slate-500">
                        {r.filename} · {fmtDate(r.created_at)}
                      </p>
                    </div>
                    <Chip tone={r.status === 'approved' ? 'green' : 'amber'}>{r.status}</Chip>
                  </div>
                  <div className="mt-2 flex gap-2">
                    <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setReview(r)}>
                      Review
                    </button>
                    <a className="btn-ghost px-2 py-1 text-xs" href={`/api/resumes/${r.id}/file`} target="_blank" rel="noreferrer" onClick={(e) => { e.preventDefault(); downloadResume(r); }}>
                      Download
                    </a>
                    <button className="btn-ghost px-2 py-1 text-xs text-rose-600" onClick={() => remove(r)}>
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Account">
            <p className="text-sm">{user?.name}</p>
            <p className="text-sm text-slate-500">{user?.email}</p>
            <p className="mt-2 text-xs text-slate-500">Role: {user?.role}</p>
          </Card>
        </div>
      </div>

      {review && (
        <ResumeReview
          resume={review}
          onClose={() => setReview(null)}
          onSaved={(next) => {
            setReview(null);
            resumes.reload();
            if (next) profile.reload();
          }}
        />
      )}
    </div>
  );
}

async function downloadResume(resume: Resume) {
  const token = localStorage.getItem('jobagent.token');
  const res = await fetch(`/api/resumes/${resume.id}/file`, { headers: { Authorization: `Bearer ${token}` } });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = resume.filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ResumeReview({ resume, onClose, onSaved }: { resume: Resume; onClose: () => void; onSaved: (applied: boolean) => void }) {
  const [parsed, setParsed] = useState({ ...resume.parsed });
  const [label, setLabel] = useState(resume.label);
  const [apply, setApply] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setError(null);
    try {
      await api.patch(`/api/resumes/${resume.id}`, { parsed, label, approve: true, apply_to_profile: apply });
      onSaved(apply);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <Modal title={`Review parsed resume: ${resume.filename}`} onClose={onClose}>
      <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
        {error && <Alert>{error}</Alert>}
        <p className="text-sm text-slate-600">Check what the parser found and correct anything wrong. Only approved details are used for matching and drafts.</p>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Version label">
            <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} />
          </Field>
          <Field label="Name">
            <input className="input" value={parsed.name ?? ''} onChange={(e) => setParsed({ ...parsed, name: e.target.value })} />
          </Field>
          <Field label="Email">
            <input className="input" value={parsed.email ?? ''} onChange={(e) => setParsed({ ...parsed, email: e.target.value })} />
          </Field>
          <Field label="Years of experience">
            <input className="input" type="number" step="0.1" value={parsed.experience_years ?? ''} onChange={(e) => setParsed({ ...parsed, experience_years: e.target.value === '' ? null : Number(e.target.value) })} />
          </Field>
        </div>
        <Field label="Skills">
          <TagInput value={parsed.skills ?? []} onChange={(v) => setParsed({ ...parsed, skills: v })} />
        </Field>
        <Field label="Summary">
          <textarea className="input" rows={2} value={parsed.summary ?? ''} onChange={(e) => setParsed({ ...parsed, summary: e.target.value })} />
        </Field>
        <Field label="Experience (one per line)">
          <textarea
            className="input font-mono text-xs"
            rows={4}
            value={(parsed.experience ?? []).map((e) => `${e.title ?? ''} | ${e.start ?? ''} – ${e.end ?? ''} | ${e.text ?? ''}`).join('\n')}
            onChange={(e) =>
              setParsed({
                ...parsed,
                experience: e.target.value
                  .split('\n')
                  .filter((l) => l.trim())
                  .map((line) => {
                    const [title, dates, ...text] = line.split('|');
                    const [start, end] = (dates ?? '').split('–');
                    return { title: title?.trim(), start: start?.trim(), end: end?.trim(), text: text.join('|').trim() };
                  }),
              })
            }
          />
        </Field>
        <Field label="Education (one per line)">
          <textarea className="input" rows={2} value={(parsed.education ?? []).map((e) => e.text).join('\n')} onChange={(e) => setParsed({ ...parsed, education: e.target.value.split('\n').filter((l) => l.trim()).map((text) => ({ text })) })} />
        </Field>
        <Field label="Projects (one per line)">
          <textarea className="input" rows={3} value={(parsed.projects ?? []).map((p) => p.text).join('\n')} onChange={(e) => setParsed({ ...parsed, projects: e.target.value.split('\n').filter((l) => l.trim()).map((text) => ({ text })) })} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={apply} onChange={(e) => setApply(e.target.checked)} />
          Also update my profile with these details
        </label>
        <div className="flex justify-end gap-2">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={save}>
            Approve
          </button>
        </div>
      </div>
    </Modal>
  );
}
