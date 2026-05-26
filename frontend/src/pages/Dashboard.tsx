import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Outlet, Run, Search, User } from "../api/types";
import { RunStatusPill } from "../components/RunStatusPill";
import { Spinner } from "../components/Spinner";
import { useAuth } from "../auth";

interface RunHits {
  byOutlet: Record<string, number>;
  byLang: Record<string, number>;
}

async function loadRunResults(runs: Run[]): Promise<RunHits> {
  const byOutlet: Record<string, number> = {};
  const byLang: Record<string, number> = {};
  for (const r of runs.slice(0, 25)) {
    if (r.result_count === 0) continue;
    try {
      const page = await api.getResults(r.id, { page: 1, page_size: 500 });
      for (const item of page.items) {
        byOutlet[item.outlet_name] = (byOutlet[item.outlet_name] || 0) + 1;
        const langKey = item.detected_lang_name || item.detected_lang || "?";
        byLang[langKey] = (byLang[langKey] || 0) + 1;
      }
    } catch {
      /* ignore */
    }
  }
  return { byOutlet, byLang };
}

export default function Dashboard() {
  const { user } = useAuth();
  const [searches, setSearches] = useState<Search[]>([]);
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [hits, setHits] = useState<RunHits>({ byOutlet: {}, byLang: {} });
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [s, o, r] = await Promise.all([api.listSearches(), api.listOutlets(), api.listRuns()]);
        setSearches(s);
        setOutlets(o);
        setRuns(r);
        setHits(await loadRunResults(r));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const defaultSearch = useMemo(
    () => searches.find((s) => s.is_default) ?? searches[0] ?? null,
    [searches],
  );

  async function runDefault() {
    if (!defaultSearch) return;
    setRunning(defaultSearch.id);
    try {
      const r = await api.triggerRun(defaultSearch.id);
      nav(`/runs/${r.id}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start run.");
    } finally {
      setRunning(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-6 w-6 text-brand" />
      </div>
    );
  }

  const lastRun = runs[0] ?? null;
  const activeOutlets = outlets.filter((o) => o.is_active).length;

  return (
    <div className="space-y-6">
      <CredentialsBanner user={user} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Stat
          label="Active outlets"
          value={activeOutlets}
          sub={`${outlets.length} total in your library`}
        />
        <Stat
          label="Last run — API calls"
          value={lastRun ? lastRun.api_calls_used : "—"}
          sub={lastRun ? `Status: ${lastRun.status}` : "No runs yet"}
        />
        <Stat
          label="Total searches"
          value={searches.length}
          sub={defaultSearch ? `Default: ${defaultSearch.name}` : "No default set"}
        />
      </div>

      <div className="card flex flex-wrap items-center gap-3 p-5">
        <div className="flex-1 min-w-0">
          <div className="text-xs uppercase tracking-wide text-slate-500">Default search</div>
          <div className="mt-0.5 text-base font-semibold truncate">
            {defaultSearch ? defaultSearch.name : "No default search configured"}
          </div>
        </div>
        <button
          disabled={!defaultSearch || running !== null}
          onClick={runDefault}
          className="btn-primary"
          title={defaultSearch ? `Run "${defaultSearch.name}"` : "Create a default search first"}
        >
          {running && <Spinner />} Run default search
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="text-base font-semibold">Last 5 runs</h2>
          <div className="mt-3 divide-y divide-slate-200">
            {runs.slice(0, 5).map((r) => (
              <Link
                key={r.id}
                to={`/runs/${r.id}`}
                className="flex items-center gap-2 py-2 text-sm hover:bg-slate-50"
              >
                <div className="flex-1">
                  <div className="font-medium">{r.search_name ?? "—"}</div>
                  <div className="text-xs text-slate-500">
                    {new Date(r.started_at).toLocaleString()} · {r.result_count} hit(s)
                  </div>
                </div>
                <RunStatusPill status={r.status} />
              </Link>
            ))}
            {runs.length === 0 && (
              <p className="py-2 text-sm text-slate-500">No runs yet. Trigger your first search.</p>
            )}
          </div>
        </div>

        <div className="card p-5">
          <h2 className="text-base font-semibold">Top outlets (across recent runs)</h2>
          <BarList data={hits.byOutlet} max={10} />
        </div>

        <div className="card p-5 lg:col-span-2">
          <h2 className="text-base font-semibold">Hits by detected language</h2>
          <BarList data={hits.byLang} max={20} />
        </div>
      </div>
    </div>
  );
}

function CredentialsBanner({ user }: { user: User | null }) {
  if (!user) return null;
  const ok = user.has_google_key && user.has_engine_id;
  if (ok) return null;
  return (
    <div className="flex items-center justify-between rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      <span>
        Google Custom Search credentials: <strong>not configured</strong>
      </span>
      <Link to="/settings" className="font-medium underline">
        Set up now
      </Link>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="card p-5">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

function BarList({ data, max }: { data: Record<string, number>; max: number }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, max);
  if (entries.length === 0) {
    return <p className="mt-3 text-sm text-slate-500">No data yet.</p>;
  }
  const peak = entries[0][1];
  return (
    <ul className="mt-3 space-y-2">
      {entries.map(([k, v]) => (
        <li key={k} className="text-sm">
          <div className="flex justify-between text-xs">
            <span className="truncate pr-2">{k}</span>
            <span className="tabular-nums text-slate-500">{v}</span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-slate-100">
            <div
              className="h-full bg-brand"
              style={{ width: `${peak ? (v / peak) * 100 : 0}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
