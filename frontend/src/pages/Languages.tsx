import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { UniversityLanguage } from "../api/types";
import { ALL_LANGUAGES } from "../api/types";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function Languages() {
  const [languages, setLanguages] = useState<UniversityLanguage[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEntry, setNewEntry] = useState({ iso_code: "", language_label: "", university_name: "" });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<UniversityLanguage | null>(null);
  const [deleting, setDeleting] = useState<UniversityLanguage | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  function isoLabel(code: string) {
    return ALL_LANGUAGES.find((l) => l.code === code)?.label ?? code;
  }

  async function addLanguage() {
    const { iso_code, language_label, university_name } = newEntry;
    if (!iso_code || !language_label.trim() || !university_name.trim()) return;
    setError(null);
    try {
      const created = await api.createLanguage({
        iso_code: iso_code.trim(),
        language_label: language_label.trim(),
        university_name: university_name.trim(),
      });
      setLanguages((prev) => [...prev, created]);
      setNewEntry({ iso_code: "", language_label: "", university_name: "" });
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
        language_label: editDraft.language_label,
        university_name: editDraft.university_name,
      });
      setLanguages((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
      setEditingId(null);
      setEditDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  function onIsoCodeSelect(code: string) {
    const label = ALL_LANGUAGES.find((l) => l.code === code)?.label ?? "";
    setNewEntry((prev) => ({ ...prev, iso_code: code, language_label: label }));
  }

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <h2 className="text-base font-semibold">Add language</h2>
        <p className="mt-1 text-xs text-slate-500">
          Define your university's name in each language you want to search. These entries are used
          by the University Name option in your searches.
        </p>
        {error && (
          <div className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1.2fr_1.2fr_1.8fr_auto]">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Language</label>
            <select
              className="input"
              value={newEntry.iso_code}
              onChange={(e) => onIsoCodeSelect(e.target.value)}
            >
              <option value="">Select language…</option>
              {ALL_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label} ({l.code})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Label</label>
            <input
              className="input"
              placeholder="e.g. English"
              value={newEntry.language_label}
              onChange={(e) => setNewEntry({ ...newEntry, language_label: e.target.value })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">University name in this language</label>
            <input
              className="input"
              placeholder="e.g. Kobe University"
              value={newEntry.university_name}
              onChange={(e) => setNewEntry({ ...newEntry, university_name: e.target.value })}
            />
          </div>
          <div className="flex items-end">
            <button
              className="btn-primary w-full"
              onClick={addLanguage}
              disabled={!newEntry.iso_code || !newEntry.language_label.trim() || !newEntry.university_name.trim()}
            >
              Add
            </button>
          </div>
        </div>
      </div>

      <div className="card p-4">
        <h2 className="text-base font-semibold">Defined languages</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-4">ISO code</th>
                <th className="py-2 pr-4">Label</th>
                <th className="py-2 pr-4">University name</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-500">
                    <Spinner className="inline-block h-5 w-5 text-brand" />
                  </td>
                </tr>
              )}
              {!loading && languages.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-500">
                    No languages defined yet.
                  </td>
                </tr>
              )}
              {languages.map((lang) => {
                const editing = editingId === lang.id && editDraft;
                return (
                  <tr key={lang.id} className="border-t border-slate-100">
                    {editing ? (
                      <>
                        <td className="py-1 pr-2">
                          <select
                            className="input"
                            value={editDraft!.iso_code}
                            onChange={(e) => {
                              const label = ALL_LANGUAGES.find((l) => l.code === e.target.value)?.label ?? editDraft!.language_label;
                              setEditDraft({ ...editDraft!, iso_code: e.target.value, language_label: label });
                            }}
                          >
                            {ALL_LANGUAGES.map((l) => (
                              <option key={l.code} value={l.code}>
                                {l.label} ({l.code})
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-1 pr-2">
                          <input
                            className="input"
                            value={editDraft!.language_label}
                            onChange={(e) => setEditDraft({ ...editDraft!, language_label: e.target.value })}
                          />
                        </td>
                        <td className="py-1 pr-2">
                          <input
                            className="input"
                            value={editDraft!.university_name}
                            onChange={(e) => setEditDraft({ ...editDraft!, university_name: e.target.value })}
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
                        <td className="py-1.5 pr-4 font-mono text-sm">
                          <span className="rounded bg-slate-100 px-1.5 py-0.5">{lang.iso_code}</span>
                        </td>
                        <td className="py-1.5 pr-4">{lang.language_label}</td>
                        <td className="py-1.5 pr-4">{lang.university_name}</td>
                        <td className="py-1.5 text-right">
                          <button
                            className="btn-ghost mr-1"
                            onClick={() => { setEditingId(lang.id); setEditDraft({ ...lang }); }}
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

      <ConfirmDialog
        open={!!deleting}
        title={`Delete "${deleting?.language_label}"?`}
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
    </div>
  );
}
