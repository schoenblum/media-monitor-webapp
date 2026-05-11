import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, downloadBlob } from "../api/client";
import type { Result, Run } from "../api/types";
import { RunStatusPill } from "../components/RunStatusPill";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [run, setRun] = useState<Run | null>(null);
  const [items, setItems] = useState<Result[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exportOpen, setExportOpen] = useState(false);
  const [exportRunIds, setExportRunIds] = useState<string[]>([]);
  const [availableRuns, setAvailableRuns] = useState<Run[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!id) return;
    let pollTimer: number | null = null;
    const load = async (refreshOnly = false) => {
      try {
        const r = await api.getRun(id);
        setRun(r);
        if (!refreshOnly || r.status === "complete" || r.status === "failed") {
          const page = await api.getResults(id, { page: 1, page_size: 1000 });
          setItems(page.items);
          setTotal(page.total);
          setSelected(new Set(page.items.filter((x) => x.is_selected).map((x) => x.id)));
        }
        if (r.status === "pending" || r.status === "running") {
          pollTimer = window.setTimeout(() => load(true), 2500);
        }
      } finally {
        setLoading(false);
      }
    };
    load();
    return () => {
      if (pollTimer) window.clearTimeout(pollTimer);
    };
  }, [id]);

  useEffect(() => {
    api.listRuns().then(setAvailableRuns).catch(() => undefined);
  }, []);

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

  async function toggle(ids: string[], on: boolean) {
    if (!id) return;
    await api.setResultsSelection(id, ids, on);
    setSelected((prev) => {
      const next = new Set(prev);
      for (const i of ids) {
        if (on) next.add(i);
        else next.delete(i);
      }
      return next;
    });
    setItems((prev) => prev.map((r) => (ids.includes(r.id) ? { ...r, is_selected: on } : r)));
  }

  async function doExport(extraIds: string[]) {
    if (!id) return;
    const ids = [id, ...extraIds];
    const blob = await api.exportRuns(ids);
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    downloadBlob(blob, `media_hits_${today}.csv`);
    setExportOpen(false);
  }

  if (loading)
    return (
      <div className="card flex items-center justify-center p-10">
        <Spinner className="h-6 w-6 text-brand" />
      </div>
    );
  if (!run) return <div className="card p-6 text-sm text-slate-500">Run not found.</div>;

  const sel = selected.size;

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Link to="/runs" className="text-sm text-slate-600 hover:text-brand">
            ← All runs
          </Link>
          <h2 className="flex-1 text-base font-semibold">{run.search_name}</h2>
          <RunStatusPill status={run.status} />
          {(run.status === "complete" || run.status === "failed") && (
            <>
              <button className="btn-primary" onClick={() => setExportOpen(true)}>
                Export CSV
              </button>
              <button className="btn-danger" onClick={() => setConfirmDelete(true)}>
                Delete run
              </button>
            </>
          )}
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600 sm:grid-cols-5">
          <Field label="Triggered by" value={run.triggered_by} />
          <Field label="Started" value={new Date(run.started_at).toLocaleString()} />
          <Field
            label="Completed"
            value={run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}
          />
          <Field label="API calls" value={String(run.api_calls_used)} />
          <Field label="Hits" value={String(total)} />
        </div>
        {run.error_message && (
          <div className="mt-2 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
            {run.error_message}
          </div>
        )}
      </div>

      {(run.status === "pending" || run.status === "running") && (
        <div className="card flex items-center gap-3 p-4 text-sm text-slate-600">
          <Spinner className="h-5 w-5 text-brand" />
          Searching… this page will refresh as new results come in.
        </div>
      )}

      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="flex-1 text-base font-semibold">Results</h3>
          <span className="text-xs text-slate-500">
            {sel} of {items.length} selected
          </span>
          <button
            className="btn-secondary"
            onClick={() => toggle(items.map((i) => i.id), true)}
            disabled={items.length === 0}
          >
            Select all
          </button>
          <button
            className="btn-secondary"
            onClick={() => toggle(items.map((i) => i.id), false)}
            disabled={items.length === 0}
          >
            Deselect all
          </button>
        </div>

        {items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No hits to review.</p>
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
                        toggle(list.map((r) => r.id), !allSel);
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
                          onChange={(e) => toggle([r.id], e.target.checked)}
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
                              <span className="pill-amber">{r.date_extracted}</span>
                            )}
                            <span className="pill-slate">{r.outlet_name}</span>
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

      <ExportDialog
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        currentRunId={id!}
        availableRuns={availableRuns.filter((r) => r.id !== id && r.status === "complete")}
        selected={exportRunIds}
        setSelected={setExportRunIds}
        onExport={doExport}
        selectedCountInCurrentRun={selected.size}
      />

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this run?"
        body="All results from this run will be permanently deleted."
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          if (id) await api.deleteRun(id);
          nav("/runs", { replace: true });
        }}
      />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[0.65rem] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="font-medium text-slate-700">{value}</div>
    </div>
  );
}

function ExportDialog(props: {
  open: boolean;
  onClose: () => void;
  currentRunId: string;
  availableRuns: Run[];
  selected: string[];
  setSelected: (ids: string[]) => void;
  onExport: (extraIds: string[]) => void;
  selectedCountInCurrentRun: number;
}) {
  if (!props.open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="card w-full max-w-lg p-5">
        <h2 className="text-lg font-semibold">Export selected hits</h2>
        <p className="mt-1 text-sm text-slate-600">
          Exports all results you have ticked in the current run, plus any additional runs you
          choose below. Only ticked rows are exported.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Currently selected in this run: {props.selectedCountInCurrentRun}.
        </p>
        <div className="mt-3 max-h-60 overflow-y-auto rounded border border-slate-200">
          {props.availableRuns.length === 0 ? (
            <p className="px-3 py-3 text-sm text-slate-500">No other completed runs.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {props.availableRuns.map((r) => (
                <li key={r.id} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={props.selected.includes(r.id)}
                    onChange={(e) => {
                      const set = new Set(props.selected);
                      if (e.target.checked) set.add(r.id);
                      else set.delete(r.id);
                      props.setSelected([...set]);
                    }}
                  />
                  <span className="flex-1 truncate">{r.search_name}</span>
                  <span className="text-xs text-slate-500">
                    {new Date(r.started_at).toLocaleDateString()} · {r.result_count} hits
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-secondary" onClick={props.onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={() => props.onExport(props.selected)}>
            Download CSV
          </button>
        </div>
      </div>
    </div>
  );
}
