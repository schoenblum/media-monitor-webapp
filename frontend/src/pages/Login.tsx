import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Spinner } from "../components/Spinner";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const r = await login(email, password);
      nav(r.force_password_change ? "/change-password" : "/", { replace: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={submit} className="card w-full max-w-sm p-6">
        <h1 className="text-xl font-semibold">Media Monitor</h1>
        <p className="mt-1 text-sm text-slate-600">Sign in to your account.</p>
        <div className="mt-4 space-y-3">
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input
              id="email"
              className="input mt-1"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input
              id="password"
              className="input mt-1"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {err && <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading && <Spinner />}
            Sign in
          </button>
          <div className="text-center text-xs text-slate-500">
            <Link to="/forgot-password" className="hover:text-brand">
              Forgot your password?
            </Link>
          </div>
        </div>
      </form>
    </div>
  );
}
