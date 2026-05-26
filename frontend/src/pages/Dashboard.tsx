import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Outlet, Run, Search, User } from "../api/types";
import { RunStatusPill } from "../components/RunStatusPill";
import { Spinner } from "../components/Spinner";
import { useAuth } from "../auth";
import { sourceHostFor } from "../utils/source";

interface RunHits {
  bySource: Record<string, number>;
  byLang: Record<string, number>;
  truncated: boolean;
}

const DASHBOARD_WINDOW_KEY = "mm_dashboard_window_days";
const DEFAULT_WINDOW_DAYS = 7;
// Cap the number of runs we fan out into getResults calls per refresh so a
// very busy window can't make the Dashboard spin forever.
const MAX_RUNS_PER_WINDOW = 50;

function loadStoredWindowDays(): number {
  try {
    const raw = localStorage.getItem(DASHBOARD_WINDOW_KEY);
    if (!raw) return DEFAULT_WINDOW_DAYS;
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n) || n < 1) return DEFAULT_WINDOW_DAYS;
    return Math.min(n, 365);
  } catch {
    return DEFAULT_WINDOW_DAYS;
  }
}

async function loadRunResults(runs: Run[], windowDays: number): Promise<RunHits> {
  const bySource: Record<string, number> = {};
  const byLang: Record<string, number> = {};
  const cutoff = Date.now() - windowDays * 24 * 60 * 60 * 1000;
  const inWindow = runs.filter((r) => {
    const t = Date.parse(r.started_at);
    return Number.isFinite(t) && t >= cutoff;
  });
  const truncated = inWindow.length > MAX_RUNS_PER_WINDOW;
  for (const r of inWindow.slice(0, MAX_RUNS_PER_WINDOW)) {
    if (r.result_count === 0) continue;
    try {
      const page = await api.getResults(r.id, { page: 1, page_size: 500 });
      for (const item of page.items) {
        const host = sourceHostFor(item.url);
        if (host) {
          bySource[host] = (bySource[host] || 0) + 1;
        }
        const langKey = item.detected_lang_name || item.detected_lang || "?";
        byLang[langKey] = (byLang[langKey] || 0) + 1;
      }
    } catch {
      /* ignore */
    }
  }
  return { bySource, byLang, truncated };
}

export default function Dashboard() {
  const { user } = useAuth();
  const [searches, setSearches] = useState<Search[]>([]);
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [hits, setHits] = useState<RunHits>({ bySource: {}, byLang: {}, truncated: false });
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const [deduplicate, setDeduplicate] = useState(true);
  const [windowDays, setWindowDays] = useState<number>(loadStoredWindowDays);
  const [windowInput, setWindowInput] = useState<string>(() => String(loadStoredWindowDays()));
  const [refreshingHits, setRefreshingHits] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [s, o, r] = await Promise.all([api.listSearches(), api.listOutlets(), api.listRuns()]);
        setSearches(s);
        setOutlets(o);
        setRuns(r);
        setHits(await loadRunResults(r, windowDays));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (loading) return;
    let cancelled = false;
    setRefreshingHits(true);
    (async () => {
      try {
        const h = await loadRunResults(runs, windowDays);
        if (!cancelled) setHits(h);
      } finally {
        if (!cancelled) setRefreshingHits(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [windowDays, runs, loading]);

  function commitWindow(raw: string) {
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n) || n < 1) {
      setWindowInput(String(windowDays));
      return;
    }
    const clamped = Math.min(n, 365);
    setWindowInput(String(clamped));
    if (clamped === windowDays) return;
    setWindowDays(clamped);
    try {
      localStorage.setItem(DASHBOARD_WINDOW_KEY, String(clamped));
    } catch {
      /* ignore */
    }
  }

  const defaultSearch = useMemo(
    () => searches.find((s) => s.is_default) ?? searches[0] ?? null,
    [searches],
  );

  async function runDefault() {
    if (!defaultSearch) return;
    setRunning(defaultSearch.id);
    try {
      const r = await api.triggerRun(defaultSearch.id, { deduplicate });
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
        <label
          className="flex items-center gap-2 text-xs text-slate-600"
          title="Skip URLs returned by previous runs of this search within the last couple of days."
        >
          <input
            type="checkbox"
            checked={deduplicate}
            onChange={(e) => setDeduplicate(e.target.checked)}
          />
          Deduplicate results
        </label>
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
                className="flex items-start gap-2 py-2 text-sm hover:bg-slate-50"
              >
                <div className="flex-1">
                  <div className="font-medium">{r.search_name ?? "—"}</div>
                  <div className="text-xs text-slate-500">
                    {new Date(r.started_at).toLocaleString()} · {r.result_count} hit(s)
                  </div>
                  {(r.status === "failed" || r.status === "skipped") && r.error_message && (
                    <div className={`mt-0.5 text-[0.7rem] ${
                      r.status === "failed" ? "text-red-700" : "text-amber-700"
                    }`}>
                      {r.error_message}
                    </div>
                  )}
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold">
              Top sources (last {windowDays} day{windowDays === 1 ? "" : "s"})
            </h2>
            <label className="flex items-center gap-2 text-xs text-slate-500">
              Window (days)
              <input
                type="number"
                min={1}
                max={365}
                value={windowInput}
                onChange={(e) => setWindowInput(e.target.value)}
                onBlur={(e) => commitWindow(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
                className="w-16 rounded border border-slate-300 px-2 py-1 text-right text-sm tabular-nums"
              />
              {refreshingHits && <Spinner className="h-3 w-3 text-slate-400" />}
            </label>
          </div>
          <BarList data={hits.bySource} max={10} />
          {hits.truncated && (
            <p className="mt-2 text-xs text-slate-500">
              Showing the {MAX_RUNS_PER_WINDOW} most recent runs in this window.
            </p>
          )}
        </div>

        <div className="card p-5 lg:col-span-2">
          <h2 className="text-base font-semibold">
            Hits by detected language (last {windowDays} day{windowDays === 1 ? "" : "s"})
          </h2>
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
