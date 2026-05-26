import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, downloadBlob } from "../api/client";
import type { Result, Run, Search, UUID } from "../api/types";
import { triggerLabel } from "../api/types";
import { RunStatusPill } from "../components/RunStatusPill";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { sourceHostFor } from "../utils/source";
import { useAuth } from "../auth";

export default function RunHistory() {
  const { user } = useAuth();
  const [runs, setRuns] = useState<Run[]>([]);
  const [searches, setSearches] = useState<Search[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [running, setRunning] = useState<string | null>(null);
  const [deduplicate, setDeduplicate] = useState(true);
  const [selected, setSelected] = useState<Set<UUID>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mergeRunIds, setMergeRunIds] = useState<UUID[] | null>(null);
  const nav = useNavigate();
  const showPerformedBy = !!user?.university_id;

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
      const r = await api.triggerRun(target.id, { deduplicate });
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

  // While merge view is open, hide the run history list to give a full-page feel
  if (mergeRunIds) {
    return (
      <MergeView
        runIds={mergeRunIds}
        runs={runs}
        onClose={() => setMergeRunIds(null)}
      />
    );
  }

  const selectedCount = selected.size;

  return (
    <div className="card p-4">
      {showPerformedBy && (
        <div className="mb-3 rounded-md bg-sky-50 px-3 py-2 text-xs text-sky-900">
          Showing <strong>shared</strong> run history for{" "}
          <strong>{user?.university_name ?? "your university"}</strong>. Any member
          can view (and toggle result selections on) any run; only the run's performer
          can delete it.
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex-1 text-base font-semibold">Run history</h2>
        <select
          className="input w-auto"
          value={searchFilter}
          onChange={(e) => { setSearchFilter(e.target.value); }}
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
          onChange={(e) => { setStatusFilter(e.target.value); }}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="complete">Complete</option>
          <option value="failed">Failed</option>
          <option value="skipped">Skipped</option>
        </select>
        <label
          className="flex items-center gap-2 text-xs text-slate-600"
          title="Skip URLs returned by previous runs of this search within the last couple of days."
        >
          <input
            type="checkbox"
            checked={deduplicate}
            onChange={(e) => setDeduplicate(e.target.checked)}
          />
          Deduplicate
        </label>
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
              if (ids.length === 0) return;
              setMergeRunIds(ids);
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
              {showPerformedBy && <th className="py-2">Performed by</th>}
              <th className="py-2">Trigger</th>
              <th className="py-2">Status</th>
              <th className="py-2 text-right">Hits</th>
              <th className="py-2 text-right">API calls</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
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
                {showPerformedBy && (
                  <td
                    className="py-1.5 text-xs text-slate-600 cursor-pointer"
                    onClick={() => nav(`/runs/${r.id}`)}
                  >
                    {r.user_id === user?.id ? (
                      <span className="text-slate-900">you</span>
                    ) : (
                      r.performed_by_email ?? "—"
                    )}
                  </td>
                )}
                <td className="py-1.5 text-slate-600 cursor-pointer" onClick={() => nav(`/runs/${r.id}`)}>
                  {triggerLabel(r.triggered_by)}
                </td>
                <td className="py-1.5 cursor-pointer" onClick={() => nav(`/runs/${r.id}`)}>
                  <RunStatusPill status={r.status} />
                  {(r.status === "failed" || r.status === "skipped") && r.error_message && (
                    <div className={`mt-0.5 text-[0.7rem] ${
                      r.status === "failed" ? "text-red-700" : "text-amber-700"
                    }`}>
                      {r.error_message}
                    </div>
                  )}
                </td>
                <td className="py-1.5 text-right tabular-nums cursor-pointer" onClick={() => nav(`/runs/${r.id}`)}>
                  {r.result_count}
                </td>
                <td className="py-1.5 text-right tabular-nums cursor-pointer" onClick={() => nav(`/runs/${r.id}`)}>
                  {r.api_calls_used}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={showPerformedBy ? 8 : 7}
                  className="py-6 text-center text-slate-500"
                >
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Merge view — RunDetail-style UI over the deduplicated merged result set.
// Not persisted as a run. Selection toggles update the underlying Result rows.
// ---------------------------------------------------------------------------

function MergeView({
  runIds,
  runs,
  onClose,
}: {
  runIds: UUID[];
  runs: Run[];
  onClose: () => void;
}) {
  const [items, setItems] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<UUID>>(new Set());

  const runLabels = runIds.map((id) => {
    const r = runs.find((x) => x.id === id);
    return r ? `${r.search_name ?? "—"} (${new Date(r.started_at).toLocaleDateString()})` : id;
  });

  useEffect(() => {
    (async () => {
      try {
        // Pull a big page so the whole merged set is in memory like RunDetail does.
        const page = await api.getMergedResults(runIds, { page: 1, page_size: 1000 });
        setItems(page.items);
        setSelected(new Set(page.items.filter((x) => x.is_selected).map((x) => x.id)));
      } finally {
        setLoading(false);
      }
    })();
  }, [runIds.join(",")]);

  const grouped = useMemo(() => {
    const m = new Map<string, Result[]>();
    for (const it of items) {
      const key = it.detected_lang_name || it.detected_lang || "?";
      const arr = m.get(key) ?? [];
      arr.push(it);
      m.set(key, arr);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [items]);

  async function toggle(targets: Result[], on: boolean) {
    // Batch by run_id since the selection endpoint is scoped per run.
    const byRun = new Map<UUID, UUID[]>();
    for (const r of targets) {
      const arr = byRun.get(r.run_id) ?? [];
      arr.push(r.id);
      byRun.set(r.run_id, arr);
    }
    await Promise.all(
      [...byRun.entries()].map(([runId, resultIds]) =>
        api.setResultsSelection(runId, resultIds, on),
      ),
    );
    setSelected((prev) => {
      const next = new Set(prev);
      for (const r of targets) {
        if (on) next.add(r.id);
        else next.delete(r.id);
      }
      return next;
    });
    setItems((prev) =>
      prev.map((r) =>
        targets.some((t) => t.id === r.id) ? { ...r, is_selected: on } : r,
      ),
    );
  }

  async function exportCsv() {
    const blob = await api.exportRuns(runIds);
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    downloadBlob(blob, `media_hits_merged_${today}.csv`);
  }

  if (loading) {
    return (
      <div className="card flex items-center justify-center p-10">
        <Spinner className="h-6 w-6 text-brand" />
      </div>
    );
  }

  const sel = selected.size;

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={onClose} className="text-sm text-slate-600 hover:text-brand">
            ← All runs
          </button>
          <h2 className="flex-1 text-base font-semibold">
            Merged view — {runIds.length} run{runIds.length > 1 ? "s" : ""}
          </h2>
          <button className="btn-primary" onClick={exportCsv}>
            Export CSV
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Deduplicated by URL · {items.length} unique hit{items.length === 1 ? "" : "s"}. Selection
          changes are saved to the underlying runs. This merged view is not stored as a new run.
        </p>
        <ul className="mt-2 space-y-0.5">
          {runLabels.map((l, i) => (
            <li key={i} className="text-xs text-slate-500">— {l}</li>
          ))}
        </ul>
      </div>

      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="flex-1 text-base font-semibold">Results</h3>
          <span className="text-xs text-slate-500">
            {sel} of {items.length} selected
          </span>
          <button
            className="btn-secondary"
            onClick={() => toggle(items, true)}
            disabled={items.length === 0}
          >
            Select all
          </button>
          <button
            className="btn-secondary"
            onClick={() => toggle(items, false)}
            disabled={items.length === 0}
          >
            Deselect all
          </button>
        </div>

        {items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No hits across the selected runs.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {grouped.map(([langName, list]) => {
              const allSel = list.every((r) => selected.has(r.id));
              return (
                <details key={langName} open className="rounded border border-slate-200">
                  <summary className="flex cursor-pointer items-center gap-2 bg-slate-50 px-3 py-2 text-sm font-semibold">
                    <span className="flex-1 text-brand">{langName}</span>
                    <span className="text-xs font-normal text-slate-500">
                      {list.length} hit{list.length === 1 ? "" : "s"}
                    </span>
                    <button
                      className="btn-ghost text-xs"
                      onClick={(e) => {
                        e.preventDefault();
                        toggle(list, !allSel);
                      }}
                    >
                      {allSel ? "Deselect all" : "Select all"}
                    </button>
                  </summary>
                  <ul className="divide-y divide-slate-100">
                    {list.map((r) => (
                      <li
                        key={r.id}
                        className={`flex items-start gap-2 px-3 py-2 ${
                          selected.has(r.id) ? "bg-sky-50" : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selected.has(r.id)}
                          onChange={(e) => toggle([r], e.target.checked)}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-slate-900">{r.title}</div>
                          {r.snippet && (
                            <div className="mt-0.5 line-clamp-2 text-xs text-slate-600">
                              {r.snippet}
                            </div>
                          )}
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {r.date_extracted && (
                              <span
                                className="pill-amber"
                                title="Publication date parsed from the result snippet — may be approximate or missing."
                              >
                                Published {r.date_extracted}
                              </span>
                            )}
                            {(() => {
                              const host = sourceHostFor(r.url);
                              return host ? <span className="pill-slate">{host}</span> : null;
                            })()}
                            {r.detected_lang && (
                              <span className="pill-green">{r.detected_lang.toUpperCase()}</span>
                            )}
                            <a
                              href={r.url}
                              target="_blank"
                              rel="noreferrer"
                              className="pill-blue hover:bg-sky-200"
                            >
                              ↗ open
                            </a>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </details>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
