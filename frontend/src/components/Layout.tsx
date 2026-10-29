import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import { fmtAgo } from '../format';
import type { Notification } from '../types';

type Item = { to: string; label: string; end?: boolean; icon: ReactNode };

const Icon = ({ d }: { d: string }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d={d} />
  </svg>
);

const NAV: Item[] = [
  { to: '/', label: 'Dashboard', end: true, icon: <Icon d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z" /> },
  { to: '/jobs', label: 'Jobs', icon: <Icon d="M2 9a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2zM16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2M2 13h20" /> },
  { to: '/applications', label: 'Applications', icon: <Icon d="M22 2 11 13M22 2l-7 20-4-9-9-4z" /> },
  { to: '/profile', label: 'Profile & resume', icon: <Icon d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0z" /> },
  { to: '/activity', label: 'Agent activity', icon: <Icon d="M22 12h-4l-3 9L9 3l-3 9H2" /> },
];
const ADMIN: Item = { to: '/admin', label: 'Admin', icon: <Icon d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /> };

function initials(name?: string) {
  return (name ?? '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [notes, setNotes] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);

  const load = () => api.get<Notification[]>('/api/notifications?unread_only=true').then(setNotes).catch(() => undefined);

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const openNote = async (note: Notification) => {
    await api.post(`/api/notifications/${note.id}/read`);
    setNotes((n) => n.filter((x) => x.id !== note.id));
    setOpen(false);
    if (note.link) navigate(note.link);
  };

  const items = user?.role === 'admin' ? [...NAV, ADMIN] : NAV;
  const sideLink = ({ isActive }: { isActive: boolean }) =>
    `group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-white/10 text-white shadow-[inset_3px_0_0_0_var(--color-accent-400)]' : 'text-slate-300 hover:bg-white/5 hover:text-white'}`;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col overflow-y-auto bg-brand-950 text-slate-200 md:sticky md:top-0 md:flex md:h-screen">
        <div className="flex items-center gap-3 px-5 pt-6 pb-5">
          <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-lg shadow-md" />
          <div>
            <p className="text-[15px] font-semibold text-white">JobAgent</p>
            <p className="text-xs text-slate-400">You decide, it prepares</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          <p className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Workspace</p>
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={sideLink}>
              {({ isActive }) => (
                <>
                  <span className={isActive ? 'text-accent-300' : 'text-slate-400 group-hover:text-slate-200'}>{item.icon}</span>
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-lg bg-white/5 p-3 text-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white ring-2 ring-brand-800">{initials(user?.name)}</span>
            <div className="min-w-0">
              <p className="truncate font-medium text-white">{user?.name}</p>
              <p className="truncate text-xs text-slate-400">{user?.email}</p>
            </div>
          </div>
          <button className="mt-3 w-full rounded-md border border-white/10 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white" onClick={() => logout().then(() => navigate('/login'))}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur md:px-8">
          <div className="flex items-center gap-3 md:hidden">
            <img src="/favicon.svg" alt="" className="h-7 w-7 rounded-md" />
            <nav className="flex gap-4 overflow-x-auto text-sm whitespace-nowrap">
              {items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'font-semibold text-brand-700' : 'text-slate-600')}>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="relative ml-auto flex items-center gap-2">
            <button className="btn-secondary relative px-2.5" onClick={() => setOpen((o) => !o)} aria-label="Notifications" title="Notifications">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {notes.length > 0 && <span className="absolute -top-1.5 -right-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-600 px-1 text-[11px] font-semibold text-white ring-2 ring-white">{notes.length}</span>}
            </button>
            <button className="btn-ghost md:hidden" onClick={() => logout().then(() => navigate('/login'))}>
              Sign out
            </button>
            {open && (
              <div className="absolute top-full right-0 z-20 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-xl ring-1 ring-slate-900/5">
                <p className="px-3 pt-2 pb-1 text-xs font-semibold tracking-wider text-slate-500 uppercase">Notifications</p>
                {notes.length === 0 && <p className="p-3 text-sm text-slate-500">Nothing new.</p>}
                {notes.slice(0, 8).map((note) => (
                  <button key={note.id} className="block w-full rounded-lg px-3 py-2 text-left hover:bg-slate-50" onClick={() => openNote(note)}>
                    <p className="text-sm font-medium text-slate-900">{note.title}</p>
                    <p className="line-clamp-2 text-xs text-slate-500">{note.body}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{fmtAgo(note.created_at)}</p>
                  </button>
                ))}
                {notes.length > 0 && (
                  <button className="btn-ghost w-full text-xs" onClick={() => api.post('/api/notifications/read-all').then(() => setNotes([]))}>
                    Mark all read
                  </button>
                )}
              </div>
            )}
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
