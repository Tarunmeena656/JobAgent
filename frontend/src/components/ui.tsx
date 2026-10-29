import type { ReactNode } from 'react';

export function Card({ title, subtitle, action, children, className = '' }: { title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold">{title}</h2>}
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
  const color = { default: 'text-slate-900', good: 'text-emerald-700', warn: 'text-amber-600', bad: 'text-rose-600' }[tone];
  const bar = { default: 'bg-brand-600', good: 'bg-emerald-500', warn: 'bg-amber-500', bad: 'bg-rose-500' }[tone];
  return (
    <div className="card relative overflow-hidden">
      <span className={`absolute inset-y-0 left-0 w-1 ${bar}`} aria-hidden />
      <p className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">{label}</p>
      <p className={`mt-2 text-3xl font-semibold tracking-tight tabular-nums ${color}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export type ChipTone = 'slate' | 'brand' | 'green' | 'amber' | 'rose' | 'sky';

export function Chip({ children, tone = 'slate' }: { children: ReactNode; tone?: ChipTone }) {
  const styles = {
    slate: 'bg-slate-50 text-slate-700 ring-slate-500/20',
    brand: 'bg-brand-50 text-brand-700 ring-brand-600/20',
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    amber: 'bg-amber-50 text-amber-700 ring-amber-600/25',
    rose: 'bg-rose-50 text-rose-700 ring-rose-600/20',
    sky: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  }[tone];
  return <span className={`chip ${styles}`}>{children}</span>;
}

export function Score({ value }: { value: number | null | undefined }) {
  if (value == null) return <Chip>not scored</Chip>;
  const tone = value >= 70 ? 'bg-emerald-600' : value >= 50 ? 'bg-amber-500' : 'bg-slate-500';
  return (
    <span className={`inline-flex min-w-11 items-center justify-center rounded-md px-2 py-1 text-sm font-semibold text-white tabular-nums shadow-xs ${tone}`} title="Match score out of 100">
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
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`rounded-md border px-3 py-2 text-sm ${styles}`}>
      {children}
    </div>
  );
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-8 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <p className="flex items-center justify-center gap-2 p-6 text-sm text-slate-500">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" aria-hidden />
      {label}
    </p>
  );
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
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-2xl ring-1 ring-slate-900/5" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button className="btn-ghost px-2" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
