import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import { Alert } from '../components/ui';

type Mode = 'login' | 'register' | 'forgot' | 'reset';

const TITLES: Record<Mode, string> = { login: 'Sign in', register: 'Create your account', forgot: 'Reset your password', reset: 'Choose a new password' };
const ACTIONS: Record<Mode, string> = { login: 'Sign in', register: 'Create account', forgot: 'Send reset link', reset: 'Update password' };
const HINTS: Record<Mode, string> = {
  login: 'Welcome back. Sign in to see what the agents found.',
  register: 'Takes a minute. You can upload your resume right after.',
  forgot: 'Enter the email you registered with.',
  reset: 'Use at least 8 characters.',
};

const POINTS = [
  ['Finds jobs from permitted sources', 'De-duplicated, with the source link and retrieval time on every listing.'],
  ['Scores every job against your profile', 'An explainable 0–100 match that says what fits, what is missing and what is unknown.'],
  ['Drafts, but never sends on its own', 'Every email waits for your explicit approval of the exact recipient and text.'],
];

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const resetToken = params.get('token');
  const [mode, setMode] = useState<Mode>(resetToken ? 'reset' : 'login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? '/';

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(email, password);
        navigate(from, { replace: true });
      } else if (mode === 'register') {
        await register(name, email, password);
        navigate('/profile', { replace: true });
      } else if (mode === 'forgot') {
        await api.post('/api/auth/password-reset/request', { email });
        setInfo('If that email exists, a reset link was issued. Without an email provider it is written to the server log.');
      } else {
        await api.post('/api/auth/password-reset/confirm', { token: resetToken, password });
        setInfo('Password updated. You can sign in now.');
        setMode('login');
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const switchTo = (next: Mode) => {
    setMode(next);
    setError(null);
    setInfo(null);
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-brand-950 p-10 text-slate-200 lg:flex">
        <div className="pointer-events-none absolute -top-32 -right-32 h-96 w-96 rounded-full bg-brand-700/40 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-accent-600/20 blur-3xl" aria-hidden />
        <div className="relative flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="h-10 w-10 rounded-lg shadow-lg" />
          <div>
            <p className="font-semibold text-white">JobAgent</p>
            <p className="text-xs text-slate-400">You decide, it prepares</p>
          </div>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-3xl leading-tight font-semibold text-white">The research is done for you. The decisions stay yours.</h2>
          <ul className="mt-8 space-y-5">
            {POINTS.map(([title, text]) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-500/20 text-accent-300">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                </span>
                <div>
                  <p className="font-medium text-white">{title}</p>
                  <p className="text-sm text-slate-400">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-slate-500">Resumes stay in your account. The model only sees skills, titles and project lines.</p>
      </aside>

      <main className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img src="/favicon.svg" alt="" className="h-9 w-9 rounded-lg" />
            <div>
              <p className="font-semibold">JobAgent</p>
              <p className="text-xs text-slate-500">It researches and drafts. You approve and send.</p>
            </div>
          </div>
          <h1 className="text-2xl font-semibold">{TITLES[mode]}</h1>
          <p className="mt-1 text-sm text-slate-500">{HINTS[mode]}</p>
          <form className="card mt-6 space-y-4" onSubmit={submit}>
            {error && <Alert>{error}</Alert>}
            {info && <Alert kind="info">{info}</Alert>}
            {mode === 'register' && (
              <label className="block">
                <span className="label">Name</span>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
              </label>
            )}
            {mode !== 'reset' && (
              <label className="block">
                <span className="label">Email</span>
                <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
              </label>
            )}
            {mode !== 'forgot' && (
              <label className="block">
                <span className="label">{mode === 'reset' ? 'New password' : 'Password'}</span>
                <input className="input" type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required />
              </label>
            )}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? 'Please wait…' : ACTIONS[mode]}
            </button>
          </form>
          <div className="mt-4 flex justify-between text-sm text-slate-600">
            {mode === 'login' ? (
              <>
                <button type="button" className="text-link" onClick={() => switchTo('register')}>
                  Create an account
                </button>
                <button type="button" className="hover:text-slate-900 hover:underline" onClick={() => switchTo('forgot')}>
                  Forgot password?
                </button>
              </>
            ) : (
              <button type="button" className="text-link" onClick={() => switchTo('login')}>
                Back to sign in
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
