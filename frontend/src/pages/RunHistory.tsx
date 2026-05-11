import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Run, Search } from "../api/types";
import { RunStatusPill } from "../components/RunStatusPill";
import { Spinner } from "../components/Spinner";

export default function RunHistory() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [searches, setSearches] = useState<Search[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [running, setRunning] = useState<string | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      const [r, s] = await Promise.all([api.listRuns(), api.listSearches()]);
      setRuns(r);
      setSearches(s);
      setLoading(false);
    })();
  }, []);

  const filtered = useMemo(() => {
    return runs.filter((r) => {
      if (searchFilter && r.search_id !== searchFilter) return false;
      if (statusFilter && r.status !== statusFilter) return false;
      return true;
    });
  }, [runs, searchFilter, statusFilter]);

  async function runDefault() {
    const target = searches.find((s) => s.is_default) ?? searches[0];
    if (!target) {
      alert("Create a search first.");
      return;
    }
    setRunning(target.id);
    try {
      const r = await api.triggerRun(target.id);
      nav(`/runs/${r.id}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setRunning(null);
    }
  }

  if (loading) return <Spinner className="h-6 w-6 text-brand" />;

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex-1 text-base font-semibold">Run history</h2>
        <select
          className="input w-auto"
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
        >
          <option value="">All searches</option>
          {searches.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          className="input w-auto"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="complete">Complete</option>
          <option value="failed">Failed</option>
        </select>
        <button className="btn-primary" disabled={!!running} onClick={runDefault}>
          {running && <Spinner />} Run default
        </button>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Started</th>
              <th className="py-2">Search</th>
              <th className="py-2">Trigger</th>
              <th className="py-2">Status</th>
              <th className="py-2 text-right">Hits</th>
              <th className="py-2 text-right">API calls</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={r.id}
                className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                onClick={() => nav(`/runs/${r.id}`)}
              >
                <td className="py-1.5">{new Date(r.started_at).toLocaleString()}</td>
                <td className="py-1.5">
                  <Link className="text-brand hover:underline" to={`/runs/${r.id}`}>
                    {r.search_name ?? "—"}
                  </Link>
                </td>
                <td className="py-1.5 text-slate-600">{r.triggered_by}</td>
                <td className="py-1.5">
                  <RunStatusPill status={r.status} />
                </td>
                <td className="py-1.5 text-right tabular-nums">{r.result_count}</td>
                <td className="py-1.5 text-right tabular-nums">{r.api_calls_used}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500">
                  No runs match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
