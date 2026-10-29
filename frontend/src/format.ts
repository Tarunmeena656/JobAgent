export const fmtDate = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '–');

export const fmtDateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '–';

export function fmtAgo(iso: string | null | undefined) {
  if (!iso) return '–';
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export const statusLabel = (status: string | null | undefined) => (status ? status.replace(/_/g, ' ') : '–');

export const money = (value: number | null | undefined, currency = '') =>
  value == null ? '–' : `${currency ? currency + ' ' : ''}${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export const toLocalInput = (iso: string | null | undefined) => (iso ? new Date(iso).toISOString().slice(0, 16) : '');
export const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null);
