import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Outlet, Search, SearchTerm, UUID, Lang } from "../api/types";
import { LANG_LABELS, SUPPORTED_LANGS } from "../api/types";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function Searches() {
  const [searches, setSearches] = useState<Search[]>([]);
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<UUID | null>(null);
  const [newName, setNewName] = useState("");
  const [deleting, setDeleting] = useState<Search | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const [s, o] = await Promise.all([api.listSearches(), api.listOutlets()]);
        setSearches(s);
        setOutlets(o);
        if (s.length > 0) setEditing(s[0].id);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function createSearch() {
    if (!newName.trim()) return;
    const s = await api.createSearch(newName.trim(), searches.length === 0);
    setSearches((prev) => [...prev, s]);
    setEditing(s.id);
    setNewName("");
  }

  async function refresh() {
    setSearches(await api.listSearches());
  }

  async function runNow(id: UUID) {
    try {
      const r = await api.triggerRun(id);
      nav(`/runs/${r.id}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to start run");
    }
  }

  if (loading) return <Spinner className="h-6 w-6 text-brand" />;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <div className="card p-3">
        <div className="flex items-center gap-2">
          <input
            className="input"
            placeholder="New search name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") createSearch();
            }}
          />
          <button className="btn-primary" onClick={createSearch}>
            Add
          </button>
        </div>
        <ul className="mt-3 space-y-1">
          {searches.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => setEditing(s.id)}
                className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                  editing === s.id ? "bg-brand text-white" : "hover:bg-slate-100"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate">{s.name}</span>
                  {s.is_default && (
                    <span
                      className={`pill ${
                        editing === s.id ? "bg-white/20 text-white" : "pill-blue"
                      }`}
                    >
                      default
                    </span>
                  )}
                </div>
              </button>
            </li>
          ))}
          {searches.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-slate-500">
              No searches yet. Create one above.
            </li>
          )}
        </ul>
      </div>

      <div>
        {editing ? (
          <SearchEditor
            searchId={editing}
            outlets={outlets}
            onChanged={refresh}
            onDelete={(s) => setDeleting(s)}
            onRun={runNow}
          />
        ) : (
          <div className="card p-6 text-sm text-slate-500">Select or create a search.</div>
        )}
      </div>

      <ConfirmDialog
        open={deleting !== null}
        title={`Delete "${deleting?.name}"?`}
        body="This will also delete all runs and results for this search."
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting) {
            await api.deleteSearch(deleting.id);
            const remaining = searches.filter((s) => s.id !== deleting.id);
            setSearches(remaining);
            setEditing(remaining[0]?.id ?? null);
          }
          setDeleting(null);
        }}
      />
    </div>
  );
}

function SearchEditor({
  searchId,
  outlets,
  onChanged,
  onDelete,
  onRun,
}: {
  searchId: UUID;
  outlets: Outlet[];
  onChanged: () => void;
  onDelete: (s: Search) => void;
  onRun: (id: UUID) => void;
}) {
  const [search, setSearch] = useState<Search | null>(null);
  const [name, setName] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [terms, setTerms] = useState<SearchTerm[]>([]);
  const [linkedIds, setLinkedIds] = useState<Set<UUID>>(new Set());
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      const s = await api.getSearch(searchId);
      setSearch(s);
      setName(s.name);
      setIsDefault(s.is_default);
      // Ensure one row per supported language.
      const byLang: Record<string, SearchTerm> = {};
      for (const t of s.terms) byLang[t.language_code] = t;
      const full: SearchTerm[] = SUPPORTED_LANGS.map((l) => {
        const existing = byLang[l];
        return existing ?? { language_code: l, term: "", pages: 3, is_enabled: false };
      });
      setTerms(full);
      setLinkedIds(new Set(s.outlet_ids));
    })();
  }, [searchId]);

  const enabledCount = useMemo(() => terms.filter((t) => t.is_enabled && t.term.trim()).length, [terms]);
  const linkedCount = linkedIds.size;

  async function save() {
    if (!search) return;
    setSaving(true);
    try {
      await api.updateSearch(search.id, { name: name.trim(), is_default: isDefault });
      const filteredTerms = terms.filter((t) => t.term.trim().length > 0 || t.is_enabled);
      await api.replaceTerms(search.id, filteredTerms.map((t) => ({ ...t, term: t.term.trim() })));
      await api.linkOutlets(search.id, [...linkedIds]);
      setSavedAt(Date.now());
      onChanged();
      const updated = await api.getSearch(search.id);
      setSearch(updated);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!search) {
    return (
      <div className="card p-6">
        <Spinner className="h-5 w-5 text-brand" />
      </div>
    );
  }

  const grouped = outlets.reduce<Record<string, Outlet[]>>((acc, o) => {
    const key = o.category || "Uncategorised";
    (acc[key] ??= []).push(o);
    return acc;
  }, {});

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center gap-3">
        <input
          className="input max-w-md text-base font-semibold"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
          />
          Default search
        </label>
        <div className="ml-auto flex gap-2">
          <button className="btn-primary" onClick={() => onRun(search.id)}>
            Run now
          </button>
          <button className="btn-danger" onClick={() => onDelete(search)}>
            Delete
          </button>
        </div>
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Search terms ({enabledCount} active)
      </h3>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1">On</th>
              <th className="py-1">Language</th>
              <th className="py-1">Term</th>
              <th className="py-1">Pages</th>
            </tr>
          </thead>
          <tbody>
            {terms.map((t, idx) => (
              <tr key={t.language_code} className="border-t border-slate-100">
                <td className="py-1.5">
                  <input
                    type="checkbox"
                    checked={t.is_enabled}
                    onChange={(e) => {
                      const next = [...terms];
                      next[idx] = { ...t, is_enabled: e.target.checked };
                      setTerms(next);
                    }}
                  />
                </td>
                <td className="py-1.5 pr-3 font-medium">
                  {LANG_LABELS[t.language_code as Lang]} <span className="text-slate-400">{t.language_code.toUpperCase()}</span>
                </td>
                <td className="py-1.5 pr-3">
                  <input
                    className="input"
                    placeholder={`Search term in ${LANG_LABELS[t.language_code as Lang]}`}
                    value={t.term}
                    onChange={(e) => {
                      const next = [...terms];
                      next[idx] = { ...t, term: e.target.value };
                      setTerms(next);
                    }}
                  />
                </td>
                <td className="py-1.5 w-20">
                  <input
                    type="number"
                    min={1}
                    max={10}
                    className="input"
                    value={t.pages}
                    onChange={(e) => {
                      const next = [...terms];
                      const p = Math.max(1, Math.min(10, parseInt(e.target.value || "1", 10)));
                      next[idx] = { ...t, pages: p };
                      setTerms(next);
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Linked outlets ({linkedCount} of {outlets.length})
      </h3>
      <div className="mt-2 flex gap-2 text-xs">
        <button
          className="btn-ghost"
          onClick={() => setLinkedIds(new Set(outlets.filter((o) => o.is_active).map((o) => o.id)))}
        >
          Select all active
        </button>
        <button className="btn-ghost" onClick={() => setLinkedIds(new Set())}>
          Clear
        </button>
      </div>
      <div className="mt-2 max-h-96 overflow-y-auto rounded-md border border-slate-200">
        {Object.entries(grouped).map(([cat, list]) => (
          <details key={cat} open className="border-b border-slate-100 last:border-b-0">
            <summary className="cursor-pointer bg-slate-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
              {cat} <span className="text-slate-400">({list.length})</span>
            </summary>
            <ul className="divide-y divide-slate-100">
              {list.map((o) => (
                <li key={o.id} className="flex items-center gap-2 px-3 py-1.5">
                  <input
                    type="checkbox"
                    checked={linkedIds.has(o.id)}
                    onChange={(e) => {
                      const next = new Set(linkedIds);
                      if (e.target.checked) next.add(o.id);
                      else next.delete(o.id);
                      setLinkedIds(next);
                    }}
                  />
                  <span className="flex-1 text-sm">{o.name}</span>
                  <span className="text-xs text-slate-500">{o.domain}</span>
                  <span className="text-xs text-slate-400">
                    {(o.keyword_langs || []).join(",").toUpperCase()}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ))}
        {outlets.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-slate-500">
            You have no outlets yet. Add some on the Outlets page.
          </p>
        )}
      </div>

      <div className="mt-6 flex items-center gap-3">
        <button className="btn-primary" disabled={saving} onClick={save}>
          {saving && <Spinner />} Save changes
        </button>
        {savedAt && (
          <span className="text-xs text-emerald-600">Saved {new Date(savedAt).toLocaleTimeString()}.</span>
        )}
      </div>
    </div>
  );
}
