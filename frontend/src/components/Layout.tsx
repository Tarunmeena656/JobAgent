import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import { fmtAgo } from '../format';
import type { Notification } from '../types';

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/jobs', label: 'Jobs' },
  { to: '/applications', label: 'Applications' },
  { to: '/profile', label: 'Profile & resume' },
  { to: '/activity', label: 'Agent activity' },
];

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

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 px-5 py-5">
          <img src="/favicon.svg" alt="" className="h-8 w-8" />
          <div>
            <p className="font-semibold">JobAgent</p>
            <p className="text-xs text-slate-500">You decide, it prepares</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`}
            >
              {item.label}
            </NavLink>
          ))}
          {user?.role === 'admin' && (
            <NavLink to="/admin" className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`}>
              Admin
            </NavLink>
          )}
        </nav>
        <div className="border-t border-slate-200 px-5 py-4 text-sm">
          <p className="font-medium">{user?.name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button className="btn-ghost mt-2 px-0" onClick={() => logout().then(() => navigate('/login'))}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:px-8">
          <nav className="flex gap-3 overflow-x-auto text-sm md:hidden">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'font-semibold text-indigo-700' : 'text-slate-600')}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="relative ml-auto">
            <button className="btn-secondary" onClick={() => setOpen((o) => !o)} aria-label="Notifications">
              Notifications{notes.length > 0 && <span className="rounded-full bg-indigo-600 px-1.5 text-xs text-white">{notes.length}</span>}
            </button>
            {open && (
              <div className="absolute right-0 z-20 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                {notes.length === 0 && <p className="p-3 text-sm text-slate-500">Nothing new.</p>}
                {notes.slice(0, 8).map((note) => (
                  <button key={note.id} className="block w-full rounded-lg px-3 py-2 text-left hover:bg-slate-50" onClick={() => openNote(note)}>
                    <p className="text-sm font-medium">{note.title}</p>
                    <p className="line-clamp-2 text-xs text-slate-500">{note.body}</p>
                    <p className="text-xs text-slate-400">{fmtAgo(note.created_at)}</p>
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
        <main className="flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
