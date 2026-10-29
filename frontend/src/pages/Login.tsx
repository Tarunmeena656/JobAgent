import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';
import { Alert } from '../components/ui';

type Mode = 'login' | 'register' | 'forgot' | 'reset';

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

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2">
          <img src="/favicon.svg" alt="" className="h-9 w-9" />
          <div>
            <p className="text-lg font-semibold">JobAgent</p>
            <p className="text-xs text-slate-500">It researches and drafts. You approve and send.</p>
          </div>
        </div>
        <form className="card space-y-4" onSubmit={submit}>
          <h1 className="text-lg font-semibold">
            {{ login: 'Sign in', register: 'Create your account', forgot: 'Reset your password', reset: 'Choose a new password' }[mode]}
          </h1>
          {error && <Alert>{error}</Alert>}
          {info && <Alert kind="info">{info}</Alert>}
          {mode === 'register' && (
            <label className="block">
              <span className="label">Name</span>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
          )}
          {mode !== 'reset' && (
            <label className="block">
              <span className="label">Email</span>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
          )}
          {mode !== 'forgot' && (
            <label className="block">
              <span className="label">{mode === 'reset' ? 'New password' : 'Password'}</span>
              <input className="input" type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
          )}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? 'Please wait…' : { login: 'Sign in', register: 'Create account', forgot: 'Send reset link', reset: 'Update password' }[mode]}
          </button>
          <div className="flex justify-between text-sm text-slate-600">
            {mode === 'login' ? (
              <>
                <button type="button" className="hover:underline" onClick={() => setMode('register')}>
                  New here? Create an account
                </button>
                <button type="button" className="hover:underline" onClick={() => setMode('forgot')}>
                  Forgot password
                </button>
              </>
            ) : (
              <button type="button" className="hover:underline" onClick={() => setMode('login')}>
                Back to sign in
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
