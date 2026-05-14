import { useEffect, useMemo, useRef, useState } from "react";
import { api, downloadBlob } from "../api/client";
import type { ImportReport, Outlet, UniversityLanguage } from "../api/types";
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
  const [report, setReport] = useState<ImportReport | null>(null);
  const [importMode, setImportMode] = useState<"add" | "replace">("add");
  const [importPending, setImportPending] = useState<File | null>(null);
  const [confirmReplaceOpen, setConfirmReplaceOpen] = useState(false);
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

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setImportPending(f);
    if (importMode === "replace") {
      setConfirmReplaceOpen(true);
    } else {
      doImport(f, "add");
    }
    e.target.value = "";
  }

  async function doImport(file: File, mode: "add" | "replace") {
    try {
      const r = await api.importOutlets(file, mode);
      setReport(r);
      await refresh();
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
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={onPickFile}
          />
          <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
            Upload CSV
          </button>
          <button className="btn-ghost" onClick={downloadTemplate}>
            Template
          </button>
          <button className="btn-ghost" onClick={exportCsv}>
            Export
          </button>
        </div>

        {report && (
          <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm">
            <p>
              Imported <strong>{report.imported}</strong>; skipped{" "}
              <strong>{report.skipped.length}</strong>.
            </p>
            {report.skipped.length > 0 && (
              <ul className="mt-1 max-h-32 overflow-y-auto text-xs text-slate-600">
                {report.skipped.map((s, i) => (
                  <li key={i}>
                    Row {s.row}: {s.reason}
                  </li>
                ))}
              </ul>
            )}
            <button className="btn-ghost mt-2" onClick={() => setReport(null)}>
              Dismiss
            </button>
          </div>
        )}

        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
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
                  <td colSpan={6} className="py-6 text-center text-slate-500">
                    <Spinner className="h-5 w-5 text-brand inline-block" />
                  </td>
                </tr>
              )}
              {!loading && sorted.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-500">
                    No outlets.
                  </td>
                </tr>
              )}
              {sorted.map((o) => {
                const editing = editingId === o.id && editDraft;
                const noLang = (o.keyword_langs || []).length === 0;
                return (
                  <tr key={o.id} className="border-t border-slate-100">
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
        open={confirmReplaceOpen}
        title="Replace all outlets?"
        body={
          <span>
            This will <strong>delete every existing outlet</strong> in your library before importing
            the new file. You cannot undo this.
          </span>
        }
        confirmLabel="Replace all"
        danger
        onCancel={() => { setConfirmReplaceOpen(false); setImportPending(null); }}
        onConfirm={() => {
          if (importPending) doImport(importPending, "replace");
          setConfirmReplaceOpen(false);
          setImportPending(null);
        }}
      />
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
    return (
      <div className="text-xs text-slate-400 italic py-1">
        No languages defined
      </div>
    );
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
            title={lang.language_label}
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
