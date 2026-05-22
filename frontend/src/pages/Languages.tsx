import { useEffect, useMemo, useRef, useState } from "react";
import { api, downloadBlob } from "../api/client";
import type {
  LanguageCommitItem,
  LanguageDuplicateRow,
  LanguageInvalidIsoRow,
  LanguagePreviewResponse,
  LanguagePreviewRow,
  UniversityLanguage,
  UUID,
} from "../api/types";
import { ALL_LANGUAGES } from "../api/types";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../auth";

function labelFor(code: string): string {
  return ALL_LANGUAGES.find((l) => l.code === code)?.label ?? code;
}

export default function Languages() {
  const { user } = useAuth();
  const shared = !!user?.university_id;
  const [languages, setLanguages] = useState<UniversityLanguage[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEntry, setNewEntry] = useState({ iso_code: "", university_name: "" });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<UniversityLanguage | null>(null);
  const [deleting, setDeleting] = useState<UniversityLanguage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<UUID>>(new Set());
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);

  const [importMode, setImportMode] = useState<"add" | "replace">("add");
  const [importPreview, setImportPreview] = useState<LanguagePreviewResponse | null>(null);
  const [confirmReplace, setConfirmReplace] = useState<File | null>(null);
  const [report, setReport] = useState<{ added: number; replaced: number; deleted: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      setLanguages(await api.listLanguages());
    } finally {
      setLoading(false);
    }
  }

  const usedIsoSet = useMemo(() => new Set(languages.map((l) => l.iso_code)), [languages]);

  async function addLanguage() {
    const { iso_code, university_name } = newEntry;
    if (!iso_code || !university_name.trim()) return;
    setError(null);
    try {
      const created = await api.createLanguage({
        iso_code: iso_code.trim(),
        university_name: university_name.trim(),
      });
      setLanguages((prev) => [...prev, created]);
      setNewEntry({ iso_code: "", university_name: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Add failed");
    }
  }

  async function saveEdit() {
    if (!editDraft) return;
    setError(null);
    try {
      const updated = await api.updateLanguage(editDraft.id, {
        iso_code: editDraft.iso_code,
        university_name: editDraft.university_name,
      });
      setLanguages((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
      setEditingId(null);
      setEditDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
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

  function toggleAll() {
    if (languages.every((l) => selected.has(l.id))) {
      setSelected(new Set());
    } else {
      setSelected(new Set(languages.map((l) => l.id)));
    }
  }

  async function bulkDelete() {
    const ids = [...selected];
    if (ids.length === 0) return;
    try {
      await api.bulkDeleteLanguages(ids);
      setLanguages((prev) => prev.filter((l) => !selected.has(l.id)));
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  async function downloadTemplate() {
    const blob = await api.downloadLanguageTemplate();
    downloadBlob(blob, "language_import_template.csv");
  }

  async function exportCsv() {
    const blob = await api.exportLanguages();
    downloadBlob(blob, "languages_export.csv");
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    e.target.value = "";
    if (importMode === "replace") {
      setConfirmReplace(f);
      return;
    }
    runPreview(f);
  }

  async function runPreview(file: File) {
    setError(null);
    try {
      const preview = await api.previewLanguageImport(file);
      setImportPreview(preview);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    }
  }

  async function commitImport(items: LanguageCommitItem[]) {
    try {
      const r = await api.commitLanguageImport({ mode: importMode, items });
      setReport(r);
      setImportPreview(null);
      await refresh();
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    }
  }

  const selectedCount = selected.size;
  const isValidNew = newEntry.iso_code && newEntry.university_name.trim().length > 0;

  return (
    <div className="space-y-4">
      {shared && (
        <div className="rounded-md bg-sky-50 px-3 py-2 text-xs text-sky-900">
          You are editing the <strong>shared</strong> language list for{" "}
          <strong>{user?.university_name ?? "your university"}</strong>. Changes are
          immediately visible to every member; last write wins.
        </div>
      )}
      <div className="card p-4">
        <h2 className="text-base font-semibold">Add language</h2>
        <p className="mt-1 text-xs text-slate-500">
          Pick a language and define your university name in that language. Each language can only
          be added once.
        </p>
        {error && (
          <div className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1.4fr_2fr_auto]">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Language</label>
            <select
              className="input"
              value={newEntry.iso_code}
              onChange={(e) => setNewEntry({ ...newEntry, iso_code: e.target.value })}
            >
              <option value="">Select language…</option>
              {ALL_LANGUAGES.map((l) => {
                const taken = usedIsoSet.has(l.code);
                return (
                  <option key={l.code} value={l.code} disabled={taken}>
                    {l.label} ({l.code.toUpperCase()}){taken ? " — already added" : ""}
                  </option>
                );
              })}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">University name in this language</label>
            <input
              className="input"
              placeholder="e.g. Kobe University"
              value={newEntry.university_name}
              onChange={(e) => setNewEntry({ ...newEntry, university_name: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter" && isValidNew) addLanguage();
              }}
            />
          </div>
          <div className="flex items-end">
            <button className="btn-primary w-full" onClick={addLanguage} disabled={!isValidNew}>
              Add
            </button>
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="flex-1 text-base font-semibold">Defined languages</h2>
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
            title="Download your university-name language list as a CSV (re-importable on another account)"
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
              {selectedCount} language{selectedCount > 1 ? "s" : ""} selected
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
                    checked={languages.length > 0 && languages.every((l) => selected.has(l.id))}
                    onChange={toggleAll}
                    title="Select all"
                  />
                </th>
                <th className="py-2 pr-4">ISO code</th>
                <th className="py-2 pr-4">Language</th>
                <th className="py-2 pr-4">University name</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">
                    <Spinner className="inline-block h-5 w-5 text-brand" />
                  </td>
                </tr>
              )}
              {!loading && languages.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">
                    No languages defined yet.
                  </td>
                </tr>
              )}
              {languages.map((lang) => {
                const editing = editingId === lang.id && editDraft;
                const isSelected = selected.has(lang.id);
                return (
                  <tr
                    key={lang.id}
                    className={`border-t border-slate-100 ${isSelected ? "bg-sky-50" : ""}`}
                  >
                    <td className="py-1.5 pr-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleOne(lang.id)}
                      />
                    </td>
                    {editing ? (
                      <>
                        <td className="py-1 pr-2">
                          <select
                            className="input"
                            value={editDraft!.iso_code}
                            onChange={(e) =>
                              setEditDraft({ ...editDraft!, iso_code: e.target.value })
                            }
                          >
                            {ALL_LANGUAGES.map((l) => {
                              const takenByOther =
                                usedIsoSet.has(l.code) && l.code !== editDraft!.iso_code;
                              return (
                                <option key={l.code} value={l.code} disabled={takenByOther}>
                                  {l.label} ({l.code.toUpperCase()})
                                  {takenByOther ? " — already added" : ""}
                                </option>
                              );
                            })}
                          </select>
                        </td>
                        <td className="py-1 pr-2 text-xs text-slate-500">
                          {labelFor(editDraft!.iso_code)}
                        </td>
                        <td className="py-1 pr-2">
                          <input
                            className="input"
                            value={editDraft!.university_name}
                            onChange={(e) =>
                              setEditDraft({ ...editDraft!, university_name: e.target.value })
                            }
                          />
                        </td>
                        <td className="py-1 text-right">
                          <button className="btn-primary mr-1" onClick={saveEdit}>
                            Save
                          </button>
                          <button
                            className="btn-secondary"
                            onClick={() => {
                              setEditingId(null);
                              setEditDraft(null);
                            }}
                          >
                            Cancel
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-1.5 pr-4 font-mono text-sm">
                          <span className="rounded bg-slate-100 px-1.5 py-0.5">
                            {lang.iso_code.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-1.5 pr-4 text-slate-600">{labelFor(lang.iso_code)}</td>
                        <td className="py-1.5 pr-4">{lang.university_name}</td>
                        <td className="py-1.5 text-right">
                          <button
                            className="btn-ghost mr-1"
                            onClick={() => {
                              setEditingId(lang.id);
                              setEditDraft({ ...lang });
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="btn-ghost text-red-600"
                            onClick={() => setDeleting(lang)}
                          >
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

      {/* Delete-one confirmation */}
      <ConfirmDialog
        open={!!deleting}
        title={`Delete "${deleting ? labelFor(deleting.iso_code) : ""}"?`}
        body="This language will be removed. Any searches that use it in the University Name option will stop querying for it."
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting) {
            try {
              await api.deleteLanguage(deleting.id);
              setLanguages((prev) => prev.filter((l) => l.id !== deleting.id));
            } catch (e) {
              setError(e instanceof Error ? e.message : "Delete failed");
            }
          }
          setDeleting(null);
        }}
      />

      {/* Bulk-delete confirmation */}
      <ConfirmDialog
        open={confirmBulkDelete}
        title={`Delete ${selectedCount} language${selectedCount > 1 ? "s" : ""}?`}
        body="The selected languages will be removed. Any searches that use them in the University Name option will stop querying for those languages."
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirmBulkDelete(false)}
        onConfirm={() => {
          setConfirmBulkDelete(false);
          bulkDelete();
        }}
      />

      {/* Replace-mode confirmation */}
      <ConfirmDialog
        open={confirmReplace !== null}
        title="Replace all languages?"
        body={
          <span>
            This will <strong>delete every existing language</strong> in your account before
            importing the new file. Searches that depend on removed languages will stop querying for
            them.
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

      {/* Import preview / resolution modal */}
      {importPreview && (
        <LanguageImportModal
          preview={importPreview}
          mode={importMode}
          onCancel={() => setImportPreview(null)}
          onCommit={commitImport}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Import resolution modal
// ---------------------------------------------------------------------------

function LanguageImportModal({
  preview,
  mode,
  onCancel,
  onCommit,
}: {
  preview: LanguagePreviewResponse;
  mode: "add" | "replace";
  onCancel: () => void;
  onCommit: (items: LanguageCommitItem[]) => void;
}) {
  // ISO picks for invalid rows (raw_iso → chosen iso_code or "" if skipping)
  const [invalidPicks, setInvalidPicks] = useState<Record<number, string>>(() => {
    const o: Record<number, string> = {};
    for (const r of preview.invalid_iso_rows) o[r.row_num] = "";
    return o;
  });

  // Duplicate decisions: "existing" | "new"
  const [dupDecisions, setDupDecisions] = useState<Record<number, "existing" | "new">>(() => {
    const o: Record<number, "existing" | "new"> = {};
    for (const r of preview.duplicate_rows) o[r.row_num] = "existing";
    return o;
  });

  const hasUnresolvedInvalid = preview.invalid_iso_rows.some(
    (r) => !invalidPicks[r.row_num]
  );

  function build(): LanguageCommitItem[] {
    const items: LanguageCommitItem[] = [];
    // new rows always get added
    for (const r of preview.new_rows) {
      items.push({ iso_code: r.iso_code, university_name: r.university_name });
    }
    // duplicates: keep existing → skip; new → replace
    for (const r of preview.duplicate_rows) {
      const decision = dupDecisions[r.row_num] ?? "existing";
      if (decision === "new") {
        items.push({
          iso_code: r.iso_code,
          university_name: r.new_university_name,
          replace_existing_id: r.existing_id,
        });
      } else if (mode === "replace") {
        // In replace mode, we still need to keep the existing one (rebuild from scratch)
        items.push({ iso_code: r.iso_code, university_name: r.existing_university_name });
      }
    }
    // invalid rows: if user picked an ISO, treat as new
    for (const r of preview.invalid_iso_rows) {
      const iso = invalidPicks[r.row_num];
      if (iso) {
        items.push({ iso_code: iso, university_name: r.university_name });
      }
    }
    return items;
  }

  function setInvalidPick(row_num: number, iso: string) {
    setInvalidPicks((p) => ({ ...p, [row_num]: iso }));
  }

  function setDupDecision(row_num: number, d: "existing" | "new") {
    setDupDecisions((p) => ({ ...p, [row_num]: d }));
  }

  const totalItems =
    preview.new_rows.length +
    preview.duplicate_rows.filter((r) => dupDecisions[r.row_num] === "new").length +
    preview.invalid_iso_rows.filter((r) => invalidPicks[r.row_num]).length;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/60 overflow-y-auto p-4">
      <div className="card w-full max-w-3xl my-8 p-5">
        <h2 className="text-lg font-semibold">
          Import preview ({mode === "replace" ? "replace all" : "add"})
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Review the parsed CSV. Resolve any unknown ISO codes and duplicate entries below, then
          commit.
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

        {/* Invalid ISO section — must be resolved first */}
        {preview.invalid_iso_rows.length > 0 && (
          <section className="mt-4">
            <h3 className="text-sm font-semibold">Unknown ISO codes</h3>
            <p className="mt-0.5 text-xs text-slate-500">
              These codes were not in the supported list. Pick a language for each row, or leave
              blank to skip the row.
            </p>
            <ul className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200">
              {preview.invalid_iso_rows.map((r) => (
                <InvalidIsoRowItem
                  key={r.row_num}
                  row={r}
                  picked={invalidPicks[r.row_num] ?? ""}
                  onPick={(iso) => setInvalidPick(r.row_num, iso)}
                />
              ))}
            </ul>
          </section>
        )}

        {/* Duplicate section */}
        {preview.duplicate_rows.length > 0 && (
          <section className="mt-4">
            <h3 className="text-sm font-semibold">
              Duplicates ({preview.duplicate_rows.length})
            </h3>
            <p className="mt-0.5 text-xs text-slate-500">
              An entry for this language already exists. Choose which value to keep.
            </p>
            <ul className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200">
              {preview.duplicate_rows.map((r) => (
                <DuplicateRowItem
                  key={r.row_num}
                  row={r}
                  decision={dupDecisions[r.row_num] ?? "existing"}
                  onChange={(d) => setDupDecision(r.row_num, d)}
                />
              ))}
            </ul>
          </section>
        )}

        {/* New rows — informational */}
        {preview.new_rows.length > 0 && (
          <section className="mt-4">
            <h3 className="text-sm font-semibold">New ({preview.new_rows.length})</h3>
            <ul className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200 max-h-40 overflow-y-auto">
              {preview.new_rows.map((r) => (
                <NewRowItem key={r.row_num} row={r} />
              ))}
            </ul>
          </section>
        )}

        {preview.new_rows.length === 0 &&
          preview.duplicate_rows.length === 0 &&
          preview.invalid_iso_rows.length === 0 && (
            <p className="mt-4 text-sm text-slate-500">No rows parsed from the file.</p>
          )}

        <div className="mt-5 flex items-center justify-end gap-2 border-t border-slate-200 pt-4">
          <span className="mr-auto text-xs text-slate-500">
            {totalItems} item{totalItems === 1 ? "" : "s"} will be committed.
          </span>
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={hasUnresolvedInvalid && preview.invalid_iso_rows.length === 0}
            onClick={() => onCommit(build())}
            title={
              hasUnresolvedInvalid
                ? "Unresolved rows will be skipped"
                : undefined
            }
          >
            Commit import
          </button>
        </div>
      </div>
    </div>
  );
}

function NewRowItem({ row }: { row: LanguagePreviewRow }) {
  return (
    <li className="flex items-center gap-3 px-3 py-1.5 text-sm">
      <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-xs text-emerald-800">
        {row.iso_code.toUpperCase()}
      </span>
      <span className="text-xs text-slate-500">{labelFor(row.iso_code)}</span>
      <span className="flex-1 truncate">{row.university_name}</span>
    </li>
  );
}

function InvalidIsoRowItem({
  row,
  picked,
  onPick,
}: {
  row: LanguageInvalidIsoRow;
  picked: string;
  onPick: (iso: string) => void;
}) {
  return (
    <li className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
      <span className="rounded bg-red-100 px-1.5 py-0.5 font-mono text-xs text-red-800">
        {row.raw_iso || "(blank)"}
      </span>
      <span className="text-xs text-slate-500">Row {row.row_num}</span>
      <span className="flex-1 truncate">{row.university_name}</span>
      <select className="input w-auto text-xs" value={picked} onChange={(e) => onPick(e.target.value)}>
        <option value="">— Skip this row —</option>
        {ALL_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label} ({l.code.toUpperCase()})
          </option>
        ))}
      </select>
    </li>
  );
}

function DuplicateRowItem({
  row,
  decision,
  onChange,
}: {
  row: LanguageDuplicateRow;
  decision: "existing" | "new";
  onChange: (d: "existing" | "new") => void;
}) {
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
          {row.iso_code.toUpperCase()}
        </span>
        <span className="text-xs text-slate-500">{labelFor(row.iso_code)}</span>
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
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-slate-500">Keep existing</div>
            <div className="truncate text-sm">{row.existing_university_name}</div>
          </div>
        </label>
        <label className="flex cursor-pointer items-start gap-2 rounded-md border border-slate-200 p-2 hover:bg-slate-50">
          <input
            type="radio"
            className="mt-0.5"
            checked={decision === "new"}
            onChange={() => onChange("new")}
          />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-slate-500">Use new (from CSV)</div>
            <div className="truncate text-sm">{row.new_university_name}</div>
          </div>
        </label>
      </div>
    </li>
  );
}
