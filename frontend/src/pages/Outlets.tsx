import { useEffect, useMemo, useRef, useState } from "react";
import { api, downloadBlob } from "../api/client";
import type {
  Outlet,
  OutletCommitItem,
  OutletDuplicateRow,
  OutletPreviewResponse,
  OutletPreviewRow,
  UUID,
  UniversityLanguage,
} from "../api/types";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

type SortKey = "name" | "domain" | "category" | "is_active";

export default function Outlets() {
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [languages, setLanguages] = useState<UniversityLanguage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [filter, setFilter] = useState("");
  const [newOutlet, setNewOutlet] = useState<{
    name: string;
    domain: string;
    category: string;
    keyword_langs: string[];
  }>({ name: "", domain: "", category: "", keyword_langs: [] });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Outlet | null>(null);
  const [deleting, setDeleting] = useState<Outlet | null>(null);
  const [selected, setSelected] = useState<Set<UUID>>(new Set());
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);

  const [importMode, setImportMode] = useState<"add" | "replace">("add");
  const [importPreview, setImportPreview] = useState<OutletPreviewResponse | null>(null);
  const [confirmReplace, setConfirmReplace] = useState<File | null>(null);
  const [report, setReport] = useState<{ added: number; replaced: number; deleted: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      const [outs, langs] = await Promise.all([api.listOutlets(), api.listLanguages()]);
      setOutlets(outs);
      setLanguages(langs);
      setLoading(false);
    })();
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      setOutlets(await api.listOutlets());
    } finally {
      setLoading(false);
    }
  }

  const sorted = useMemo(() => {
    const f = filter.trim().toLowerCase();
    let rows = outlets;
    if (f) {
      rows = rows.filter(
        (o) =>
          o.name.toLowerCase().includes(f) ||
          o.domain.toLowerCase().includes(f) ||
          (o.category || "").toLowerCase().includes(f),
      );
    }
    return [...rows].sort((a, b) => {
      const av = (a[sortKey] ?? "") as string | boolean;
      const bv = (b[sortKey] ?? "") as string | boolean;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [outlets, sortKey, sortDir, filter]);

  function toggleSort(k: SortKey) {
    if (sortKey === k) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else {
      setSortKey(k);
      setSortDir("asc");
    }
  }

  async function addOutlet() {
    if (!newOutlet.name.trim() || !newOutlet.domain.trim()) return;
    try {
      const created = await api.createOutlet({
        name: newOutlet.name.trim(),
        domain: newOutlet.domain.trim(),
        category: newOutlet.category.trim() || null,
        keyword_langs: newOutlet.keyword_langs,
        is_active: true,
      });
      setOutlets((prev) => [...prev, created]);
      setNewOutlet({ name: "", domain: "", category: "", keyword_langs: [] });
    } catch (e) {
      alert(e instanceof Error ? e.message : "Add failed");
    }
  }

  async function saveEdit() {
    if (!editDraft) return;
    try {
      const updated = await api.updateOutlet(editDraft.id, {
        name: editDraft.name,
        domain: editDraft.domain,
        category: editDraft.category,
        keyword_langs: editDraft.keyword_langs,
        is_active: editDraft.is_active,
      });
      setOutlets((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
      setEditingId(null);
      setEditDraft(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function toggleActive(o: Outlet) {
    try {
      const updated = await api.updateOutlet(o.id, { is_active: !o.is_active });
      setOutlets((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Toggle failed");
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

  const allVisibleSelected = sorted.length > 0 && sorted.every((o) => selected.has(o.id));

  function toggleAllVisible() {
    if (allVisibleSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        sorted.forEach((o) => next.delete(o.id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        sorted.forEach((o) => next.add(o.id));
        return next;
      });
    }
  }

  async function bulkDelete() {
    const ids = [...selected];
    try {
      await api.bulkDeleteOutlets(ids);
      setOutlets((prev) => prev.filter((o) => !selected.has(o.id)));
      setSelected(new Set());
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    e.target.value = "";
    if (importMode === "replace") {
      setConfirmReplace(f);
    } else {
      runPreview(f);
    }
  }

  async function runPreview(file: File) {
    try {
      const preview = await api.previewOutletImport(file);
      setImportPreview(preview);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Preview failed");
    }
  }

  async function commitImport(items: OutletCommitItem[]) {
    try {
      const r = await api.commitOutletImport({ mode: importMode, items });
      setReport(r);
      setImportPreview(null);
      await refresh();
      setSelected(new Set());
    } catch (e) {
      alert(e instanceof Error ? e.message : "Import failed");
    }
  }

  async function downloadTemplate() {
    const blob = await api.downloadImportTemplate();
    downloadBlob(blob, "outlet_import_template.csv");
  }

  async function exportCsv() {
    const blob = await api.exportOutlets();
    downloadBlob(blob, "outlets_export.csv");
  }

  const selectedCount = selected.size;

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <h2 className="text-base font-semibold">Add outlet</h2>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1.2fr_1.4fr_1fr_1.4fr_auto]">
          <input
            className="input"
            placeholder="Name"
            value={newOutlet.name}
            onChange={(e) => setNewOutlet({ ...newOutlet, name: e.target.value })}
          />
          <input
            className="input"
            placeholder="Domain (e.g. nytimes.com)"
            value={newOutlet.domain}
            onChange={(e) => setNewOutlet({ ...newOutlet, domain: e.target.value })}
          />
          <input
            className="input"
            placeholder="Category"
            value={newOutlet.category}
            onChange={(e) => setNewOutlet({ ...newOutlet, category: e.target.value })}
          />
          <LangsPicker
            value={newOutlet.keyword_langs}
            languages={languages}
            onChange={(v) => setNewOutlet({ ...newOutlet, keyword_langs: v })}
          />
          <button className="btn-primary" onClick={addOutlet}>
            Add
          </button>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="flex-1 text-base font-semibold">Outlets</h2>
          <input
            className="input max-w-xs"
            placeholder="Filter…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <select
            className="input w-auto"
            value={importMode}
            onChange={(e) => setImportMode(e.target.value as "add" | "replace")}
          >
            <option value="add">Import — Add</option>
            <option value="replace">Import — Replace all</option>
          </select>
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={onPickFile} />
          <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
            Upload CSV
          </button>
          <button
            className="btn-secondary"
            onClick={exportCsv}
            title="Download your outlet library as a CSV (re-importable on another account)"
          >
            Download CSV
          </button>
          <button className="btn-ghost" onClick={downloadTemplate}>
            Template
          </button>
        </div>

        {/* Bulk action toolbar */}
        {selectedCount > 0 && (
          <div className="mt-3 flex items-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-sm">
            <span className="flex-1 text-slate-600">
              {selectedCount} outlet{selectedCount > 1 ? "s" : ""} selected
            </span>
            <button
              className="btn-ghost text-sm text-red-600 hover:text-red-700"
              onClick={() => setConfirmBulkDelete(true)}
            >
              Delete selected
            </button>
          </div>
        )}

        {report && (
          <div className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">
            Import complete: added <strong>{report.added}</strong>, replaced{" "}
            <strong>{report.replaced}</strong>, deleted <strong>{report.deleted}</strong>.{" "}
            <button className="ml-2 underline" onClick={() => setReport(null)}>
              Dismiss
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
                    onChange={toggleAllVisible}
                    title="Select all visible"
                  />
                </th>
                <Th label="Name" k="name" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                <Th label="Domain" k="domain" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                <Th label="Category" k="category" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                <th className="py-2">Languages</th>
                <Th label="Active" k="is_active" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500">
                    <Spinner className="h-5 w-5 text-brand inline-block" />
                  </td>
                </tr>
              )}
              {!loading && sorted.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-500">
                    No outlets.
                  </td>
                </tr>
              )}
              {sorted.map((o) => {
                const editing = editingId === o.id && editDraft;
                const noLang = (o.keyword_langs || []).length === 0;
                const isSelected = selected.has(o.id);
                return (
                  <tr
                    key={o.id}
                    className={`border-t border-slate-100 ${isSelected ? "bg-sky-50" : ""}`}
                  >
                    <td className="py-1.5 pr-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleOne(o.id)}
                      />
                    </td>
                    {editing ? (
                      <>
                        <td className="py-1 pr-2">
                          <input
                            className="input"
                            value={editDraft!.name}
                            onChange={(e) => setEditDraft({ ...editDraft!, name: e.target.value })}
                          />
                        </td>
                        <td className="py-1 pr-2">
                          <input
                            className="input"
                            value={editDraft!.domain}
                            onChange={(e) => setEditDraft({ ...editDraft!, domain: e.target.value })}
                          />
                        </td>
                        <td className="py-1 pr-2">
                          <input
                            className="input"
                            value={editDraft!.category ?? ""}
                            onChange={(e) => setEditDraft({ ...editDraft!, category: e.target.value })}
                          />
                        </td>
                        <td className="py-1 pr-2">
                          <LangsPicker
                            value={editDraft!.keyword_langs}
                            languages={languages}
                            onChange={(v) => setEditDraft({ ...editDraft!, keyword_langs: v })}
                          />
                        </td>
                        <td className="py-1 pr-2">
                          <input
                            type="checkbox"
                            checked={editDraft!.is_active}
                            onChange={(e) =>
                              setEditDraft({ ...editDraft!, is_active: e.target.checked })
                            }
                          />
                        </td>
                        <td className="py-1 text-right">
                          <button className="btn-primary mr-1" onClick={saveEdit}>
                            Save
                          </button>
                          <button
                            className="btn-secondary"
                            onClick={() => { setEditingId(null); setEditDraft(null); }}
                          >
                            Cancel
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-1.5 pr-2 font-medium">{o.name}</td>
                        <td className="py-1.5 pr-2 text-slate-600">{o.domain}</td>
                        <td className="py-1.5 pr-2 text-slate-600">{o.category}</td>
                        <td className="py-1.5 pr-2 text-xs text-slate-600">
                          {noLang ? (
                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700" title="No language set — included in all language queries">
                              all langs
                            </span>
                          ) : (
                            (o.keyword_langs || []).map((l) => l.toUpperCase()).join(", ")
                          )}
                        </td>
                        <td className="py-1.5 pr-2">
                          <button
                            onClick={() => toggleActive(o)}
                            className={o.is_active ? "pill-green" : "pill-slate"}
                          >
                            {o.is_active ? "active" : "inactive"}
                          </button>
                        </td>
                        <td className="py-1.5 text-right">
                          <button
                            className="btn-ghost mr-1"
                            onClick={() => { setEditingId(o.id); setEditDraft({ ...o }); }}
                          >
                            Edit
                          </button>
                          <button className="btn-ghost text-red-600" onClick={() => setDeleting(o)}>
                            Delete
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete "${deleting?.name}"?`}
        body="This outlet will be removed from your library and from all searches that include it."
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting) {
            try {
              await api.deleteOutlet(deleting.id);
              setOutlets((prev) => prev.filter((o) => o.id !== deleting.id));
            } catch (e) {
              alert(e instanceof Error ? e.message : "Delete failed");
            }
          }
          setDeleting(null);
        }}
      />

      <ConfirmDialog
        open={confirmBulkDelete}
        title={`Delete ${selectedCount} outlet${selectedCount > 1 ? "s" : ""}?`}
        body="The selected outlets will be permanently removed."
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirmBulkDelete(false)}
        onConfirm={() => {
          setConfirmBulkDelete(false);
          bulkDelete();
        }}
      />

      <ConfirmDialog
        open={confirmReplace !== null}
        title="Replace all outlets?"
        body={
          <span>
            This will <strong>delete every existing outlet</strong> in your library before importing
            the new file. You cannot undo this.
          </span>
        }
        confirmLabel="Continue"
        danger
        onCancel={() => setConfirmReplace(null)}
        onConfirm={() => {
          const f = confirmReplace;
          setConfirmReplace(null);
          if (f) runPreview(f);
        }}
      />

      {importPreview && (
        <OutletImportModal
          preview={importPreview}
          mode={importMode}
          onCancel={() => setImportPreview(null)}
          onCommit={commitImport}
        />
      )}
    </div>
  );
}

function Th({
  label,
  k,
  sortKey,
  sortDir,
  onSort,
}: {
  label: string;
  k: SortKey;
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (k: SortKey) => void;
}) {
  const active = sortKey === k;
  return (
    <th className="py-2">
      <button onClick={() => onSort(k)} className={`flex items-center gap-1 ${active ? "text-brand" : ""}`}>
        {label}
        {active && <span className="text-[0.6rem]">{sortDir === "asc" ? "▲" : "▼"}</span>}
      </button>
    </th>
  );
}

function LangsPicker({
  value,
  languages,
  onChange,
}: {
  value: string[];
  languages: UniversityLanguage[];
  onChange: (v: string[]) => void;
}) {
  const set = new Set(value);

  if (languages.length === 0) {
    return <div className="text-xs text-slate-400 italic py-1">No languages defined</div>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {languages.map((lang) => {
        const on = set.has(lang.iso_code);
        return (
          <button
            key={lang.id}
            type="button"
            onClick={() => {
              const next = new Set(value);
              if (on) next.delete(lang.iso_code);
              else next.add(lang.iso_code);
              onChange([...next]);
            }}
            title={lang.university_name}
            className={`rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${
              on ? "bg-brand text-white ring-brand" : "bg-white text-slate-700 ring-slate-300"
            }`}
          >
            {lang.iso_code.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Import resolution modal
// ---------------------------------------------------------------------------

function OutletImportModal({
  preview,
  mode,
  onCancel,
  onCommit,
}: {
  preview: OutletPreviewResponse;
  mode: "add" | "replace";
  onCancel: () => void;
  onCommit: (items: OutletCommitItem[]) => void;
}) {
  const [decisions, setDecisions] = useState<Record<number, "existing" | "new">>(() => {
    const o: Record<number, "existing" | "new"> = {};
    for (const r of preview.duplicate_rows) o[r.row_num] = "existing";
    return o;
  });

  function build(): OutletCommitItem[] {
    const items: OutletCommitItem[] = [];
    for (const r of preview.new_rows) {
      items.push({
        name: r.name,
        domain: r.domain,
        category: r.category,
        keyword_langs: r.keyword_langs,
      });
    }
    for (const r of preview.duplicate_rows) {
      const decision = decisions[r.row_num] ?? "existing";
      if (decision === "new") {
        items.push({
          name: r.new_name,
          domain: r.domain,
          category: r.new_category,
          keyword_langs: r.new_keyword_langs,
          replace_existing_id: r.existing_id,
        });
      } else if (mode === "replace") {
        items.push({
          name: r.existing_name,
          domain: r.domain,
          category: r.existing_category,
          keyword_langs: r.existing_keyword_langs,
        });
      }
    }
    return items;
  }

  const totalItems =
    preview.new_rows.length +
    preview.duplicate_rows.filter((r) => decisions[r.row_num] === "new").length;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/60 overflow-y-auto p-4">
      <div className="card w-full max-w-3xl my-8 p-5">
        <h2 className="text-lg font-semibold">
          Import preview ({mode === "replace" ? "replace all" : "add"})
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Review the parsed CSV. Resolve any duplicates below, then commit.
        </p>

        {preview.parse_errors.length > 0 && (
          <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Parse notices</p>
            <ul className="ml-4 mt-1 list-disc text-xs">
              {preview.parse_errors.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}

        {preview.duplicate_rows.length > 0 && (
          <section className="mt-4">
            <h3 className="text-sm font-semibold">
              Duplicates ({preview.duplicate_rows.length})
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              An outlet with this domain already exists. Pick which version to keep.
            </p>
            <ul className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200">
              {preview.duplicate_rows.map((r) => (
                <OutletDupItem
                  key={r.row_num}
                  row={r}
                  decision={decisions[r.row_num] ?? "existing"}
                  onChange={(d) => setDecisions((p) => ({ ...p, [r.row_num]: d }))}
                />
              ))}
            </ul>
          </section>
        )}

        {preview.new_rows.length > 0 && (
          <section className="mt-4">
            <h3 className="text-sm font-semibold">New ({preview.new_rows.length})</h3>
            <ul className="mt-2 max-h-40 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200">
              {preview.new_rows.map((r) => (
                <OutletNewItem key={r.row_num} row={r} />
              ))}
            </ul>
          </section>
        )}

        {preview.new_rows.length === 0 && preview.duplicate_rows.length === 0 && (
          <p className="mt-4 text-sm text-slate-500">No rows parsed from the file.</p>
        )}

        <div className="mt-5 flex items-center justify-end gap-2 border-t border-slate-200 pt-4">
          <span className="mr-auto text-xs text-slate-500">
            {totalItems} item{totalItems === 1 ? "" : "s"} will be committed.
          </span>
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn-primary" onClick={() => onCommit(build())}>
            Commit import
          </button>
        </div>
      </div>
    </div>
  );
}

function OutletNewItem({ row }: { row: OutletPreviewRow }) {
  return (
    <li className="flex items-center gap-2 px-3 py-1.5 text-sm">
      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-800">{row.domain}</span>
      <span className="flex-1 truncate">{row.name}</span>
      <span className="text-xs text-slate-500">{row.category || "—"}</span>
      <span className="text-xs text-slate-400">
        {(row.keyword_langs || []).map((l) => l.toUpperCase()).join(", ") || "all langs"}
      </span>
    </li>
  );
}

function OutletDupItem({
  row,
  decision,
  onChange,
}: {
  row: OutletDuplicateRow;
  decision: "existing" | "new";
  onChange: (d: "existing" | "new") => void;
}) {
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{row.domain}</span>
        <span className="ml-auto text-xs text-slate-500">Row {row.row_num}</span>
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-200 p-2 hover:bg-slate-50">
          <input
            type="radio"
            className="mt-0.5"
            checked={decision === "existing"}
            onChange={() => onChange("existing")}
          />
          <div className="min-w-0 flex-1 text-xs">
            <div className="font-medium text-slate-500">Keep existing</div>
            <div className="truncate text-sm">{row.existing_name}</div>
            <div className="text-slate-500">
              {row.existing_category || "—"} ·{" "}
              {(row.existing_keyword_langs || []).map((l) => l.toUpperCase()).join(", ") || "all langs"}
            </div>
          </div>
        </label>
        <label className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-200 p-2 hover:bg-slate-50">
          <input
            type="radio"
            className="mt-0.5"
            checked={decision === "new"}
            onChange={() => onChange("new")}
          />
          <div className="min-w-0 flex-1 text-xs">
            <div className="font-medium text-slate-500">Use new (from CSV)</div>
            <div className="truncate text-sm">{row.new_name}</div>
            <div className="text-slate-500">
              {row.new_category || "—"} ·{" "}
              {(row.new_keyword_langs || []).map((l) => l.toUpperCase()).join(", ") || "all langs"}
            </div>
          </div>
        </label>
      </div>
    </li>
  );
}
