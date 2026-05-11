import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Spinner } from "../components/Spinner";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={submit} className="card w-full max-w-sm p-6">
        <h1 className="text-xl font-semibold">Forgot password</h1>
        <p className="mt-1 text-sm text-slate-600">
          Enter your account email. If it is registered, a reset link will be issued.
        </p>
        {sent ? (
          <div className="mt-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            If that email is registered, a reset link has been sent. (In Phase 1 the link is logged
            on the server.)
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            <input
              type="email"
              className="input"
              placeholder="you@example.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {err && <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading && <Spinner />} Send reset link
            </button>
          </div>
        )}
        <div className="mt-4 text-center text-xs text-slate-500">
          <Link to="/login" className="hover:text-brand">Back to sign in</Link>
        </div>
      </form>
    </div>
  );
}
