import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { Spinner } from "../components/Spinner";

export default function ChangePassword() {
  const { user, refresh, logout } = useAuth();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (next.length < 8) {
      setErr("New password must be at least 8 characters long.");
      return;
    }
    if (next !== confirm) {
      setErr("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api.changePassword(current, next);
      setOk(true);
      await refresh();
      setTimeout(() => nav("/", { replace: true }), 800);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Change failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={submit} className="card w-full max-w-md p-6">
        <h1 className="text-xl font-semibold">Change your password</h1>
        {user?.force_password_change && (
          <p className="mt-1 rounded bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This is your first login. Please choose a new password before continuing.
          </p>
        )}
        <div className="mt-4 space-y-3">
          <div>
            <label className="label">Current password</label>
            <input type="password" className="input mt-1" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div>
            <label className="label">New password</label>
            <input type="password" className="input mt-1" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <input type="password" className="input mt-1" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          {err && <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
          {ok && <div className="rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Password updated.</div>}
          <div className="flex gap-2">
            <button type="submit" disabled={loading} className="btn-primary flex-1">
              {loading && <Spinner />} Save new password
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                logout();
                nav("/login");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
