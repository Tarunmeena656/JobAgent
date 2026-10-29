import type { ReactNode } from 'react';

export function Card({ title, subtitle, action, children, className = '' }: { title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, tone = 'default' }: { label: string; value: string | number; hint?: string; tone?: 'default' | 'good' | 'warn' | 'bad' }) {
  const color = { default: 'text-slate-900', good: 'text-emerald-600', warn: 'text-amber-600', bad: 'text-rose-600' }[tone];
  return (
    <div className="card">
      <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${color}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function Chip({ children, tone = 'slate' }: { children: ReactNode; tone?: 'slate' | 'indigo' | 'green' | 'amber' | 'rose' | 'sky' }) {
  const styles = {
    slate: 'bg-slate-100 text-slate-700',
    indigo: 'bg-indigo-50 text-indigo-700',
    green: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-amber-50 text-amber-700',
    rose: 'bg-rose-50 text-rose-700',
    sky: 'bg-sky-50 text-sky-700',
  }[tone];
  return <span className={`chip ${styles}`}>{children}</span>;
}

export function Score({ value }: { value: number | null | undefined }) {
  if (value == null) return <Chip>not scored</Chip>;
  const tone = value >= 70 ? 'bg-emerald-600' : value >= 50 ? 'bg-amber-500' : 'bg-slate-400';
  return (
    <span className={`inline-flex min-w-12 items-center justify-center rounded-lg px-2 py-1 text-sm font-semibold text-white ${tone}`} title="Match score out of 100">
      {value}
    </span>
  );
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'info' | 'success'; children: ReactNode }) {
  const styles = {
    error: 'border-rose-200 bg-rose-50 text-rose-800',
    info: 'border-sky-200 bg-sky-50 text-sky-800',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  }[kind];
  return <div className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>{children}</div>;
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <p className="p-6 text-center text-sm text-slate-500">{label}</p>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function TagInput({ value, onChange, placeholder }: { value: string[]; onChange: (next: string[]) => void; placeholder?: string }) {
  return (
    <input
      className="input"
      value={value.join(', ')}
      placeholder={placeholder ?? 'Comma separated'}
      onChange={(e) =>
        onChange(
          e.target.value
            .split(',')
            .map((s) => s.trim())
            .filter((s, i, arr) => s && arr.indexOf(s) === i),
        )
      }
    />
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button className="btn-ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
