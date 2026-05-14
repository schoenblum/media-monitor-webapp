import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Result, ResultsPage, Run, Search, UUID } from "../api/types";
import { RunStatusPill } from "../components/RunStatusPill";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function RunHistory() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [searches, setSearches] = useState<Search[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [running, setRunning] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<UUID>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mergeView, setMergeView] = useState<UUID[] | null>(null);
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

  const allVisibleSelected =
    filtered.length > 0 && filtered.every((r) => selected.has(r.id));

  function toggleAll() {
    if (allVisibleSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        filtered.forEach((r) => next.delete(r.id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        filtered.forEach((r) => next.add(r.id));
        return next;
      });
    }
  }

  function toggleOne(id: UUID) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

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

  async function bulkDelete() {
    const ids = [...selected];
    try {
      await api.bulkDeleteRuns(ids);
      setRuns((prev) => prev.filter((r) => !selected.has(r.id)));
      setSelected(new Set());
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  if (loading) return <Spinner className="h-6 w-6 text-brand" />;

  const selectedCount = selected.size;

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex-1 text-base font-semibold">Run history</h2>
        <select
          className="input w-auto"
          value={searchFilter}
          onChange={(e) => { setSearchFilter(e.target.value); setSelected(new Set()); }}
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
          onChange={(e) => { setStatusFilter(e.target.value); setSelected(new Set()); }}
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

      {/* Bulk action toolbar */}
      {selectedCount > 0 && (
        <div className="mt-3 flex items-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-sm">
          <span className="flex-1 text-slate-600">{selectedCount} run{selectedCount > 1 ? "s" : ""} selected</span>
          <button
            className="btn-ghost text-sm"
            onClick={() => {
              const ids = [...selected].filter((id) => filtered.some((r) => r.id === id));
              setMergeView(ids);
            }}
          >
            Merge &amp; open
          </button>
          <button
            className="btn-ghost text-sm text-red-600 hover:text-red-700"
            onClick={() => setConfirmDelete(true)}
          >
            Delete selected
          </button>
        </div>
      )}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2 pr-2 w-8">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleAll}
                  title="Select all visible"
                />
              </th>
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
                className="border-t border-slate-100 hover:bg-slate-50"
              >
                <td className="py-1.5 pr-2" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(r.id)}
                    onChange={() => toggleOne(r.id)}
                  />
                </td>
                <td
                  className="py-1.5 cursor-pointer"
                  onClick={() => nav(`/runs/${r.id}`)}
                >
                  {new Date(r.started_at).toLocaleString()}
                </td>
                <td className="py-1.5">
                  <Link className="text-brand hover:underline" to={`/runs/${r.id}`}>
                    {r.search_name ?? "—"}
                  </Link>
                </td>
                <td
                  className="py-1.5 text-slate-600 cursor-pointer"
                  onClick={() => nav(`/runs/${r.id}`)}
                >
                  {r.triggered_by}
                </td>
                <td
                  className="py-1.5 cursor-pointer"
                  onClick={() => nav(`/runs/${r.id}`)}
                >
                  <RunStatusPill status={r.status} />
                </td>
                <td
                  className="py-1.5 text-right tabular-nums cursor-pointer"
                  onClick={() => nav(`/runs/${r.id}`)}
                >
                  {r.result_count}
                </td>
                <td
                  className="py-1.5 text-right tabular-nums cursor-pointer"
                  onClick={() => nav(`/runs/${r.id}`)}
                >
                  {r.api_calls_used}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-slate-500">
                  No runs match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title={`Delete ${selectedCount} run${selectedCount > 1 ? "s" : ""}?`}
        body="This permanently removes the selected runs and all their results. You cannot undo this."
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => { setConfirmDelete(false); bulkDelete(); }}
      />

      {mergeView && (
        <MergeModal
          runIds={mergeView}
          runs={runs}
          onClose={() => setMergeView(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Merge modal
// ---------------------------------------------------------------------------

function MergeModal({
  runIds,
  runs,
  onClose,
}: {
  runIds: UUID[];
  runs: Run[];
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ResultsPage | null>(null);
  const [loading, setLoading] = useState(false);
  const PAGE_SIZE = 50;

  const runLabels = runIds.map((id) => {
    const r = runs.find((x) => x.id === id);
    return r ? `${r.search_name ?? "—"} (${new Date(r.started_at).toLocaleDateString()})` : id;
  });

  useEffect(() => {
    load(1);
  }, []);

  async function load(p: number) {
    setLoading(true);
    try {
      const result = await api.getMergedResults(runIds, { page: p, page_size: PAGE_SIZE });
      setData(result);
      setPage(p);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to load merged results");
    } finally {
      setLoading(false);
    }
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  async function exportCsv() {
    const blob = await api.exportRuns(runIds);
    const label = `merged_${runIds.length}_runs.csv`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = label;
    a.click();
    URL.revokeObjectURL(url);
  }

  const items: Result[] = data?.items ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/60 overflow-y-auto p-4">
      <div className="card w-full max-w-5xl my-8 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Merged results</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {runIds.length} run{runIds.length > 1 ? "s" : ""} · deduplicated by URL ·{" "}
              {data?.total ?? "…"} total
            </p>
            <ul className="mt-1 space-y-0.5">
              {runLabels.map((l, i) => (
                <li key={i} className="text-xs text-slate-500">— {l}</li>
              ))}
            </ul>
          </div>
          <div className="flex gap-2 shrink-0">
            <button className="btn-secondary text-sm" onClick={exportCsv}>
              Export CSV
            </button>
            <button className="btn-ghost text-sm" onClick={onClose}>
              Close
            </button>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center">
            <Spinner className="inline-block h-6 w-6 text-brand" />
          </div>
        ) : (
          <>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Outlet</th>
                    <th className="py-2 pr-3">Language</th>
                    <th className="py-2">Title / URL</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="py-1.5 pr-3 text-xs text-slate-500 whitespace-nowrap">
                        {r.date_extracted || "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-xs text-slate-600 whitespace-nowrap">
                        {r.outlet_name || r.display_source}
                      </td>
                      <td className="py-1.5 pr-3 text-xs text-slate-600 whitespace-nowrap">
                        {r.detected_lang_name || r.detected_lang}
                      </td>
                      <td className="py-1.5">
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-brand hover:underline"
                        >
                          {r.title}
                        </a>
                        <div className="text-xs text-slate-500 truncate max-w-sm">{r.snippet}</div>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-slate-500">
                        No results.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="mt-3 flex items-center justify-center gap-2 text-sm">
                <button
                  className="btn-ghost"
                  disabled={page <= 1}
                  onClick={() => load(page - 1)}
                >
                  Previous
                </button>
                <span className="text-slate-500">
                  Page {page} of {totalPages}
                </span>
                <button
                  className="btn-ghost"
                  disabled={page >= totalPages}
                  onClick={() => load(page + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
