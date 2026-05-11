import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Spinner } from "../components/Spinner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const token = params.get("token") || "";
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (next.length < 8) {
      setErr("Password must be at least 8 characters long.");
      return;
    }
    if (next !== confirm) {
      setErr("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(token, next);
      nav("/login", { replace: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Reset failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={submit} className="card w-full max-w-sm p-6">
        <h1 className="text-xl font-semibold">Reset password</h1>
        {!token && (
          <div className="mt-2 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            Missing reset token.
          </div>
        )}
        <div className="mt-4 space-y-3">
          <input
            type="password"
            className="input"
            placeholder="New password"
            required
            minLength={8}
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <input
            type="password"
            className="input"
            placeholder="Confirm new password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
          {err && <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
          <button disabled={loading || !token} className="btn-primary w-full">
            {loading && <Spinner />} Set new password
          </button>
        </div>
        <div className="mt-4 text-center text-xs text-slate-500">
          <Link to="/login" className="hover:text-brand">Back to sign in</Link>
        </div>
      </form>
    </div>
  );
}
