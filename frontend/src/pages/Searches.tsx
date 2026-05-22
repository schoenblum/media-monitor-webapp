import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Outlet, Search, SearchConfig, SearchTermConfig, UniversityLanguage, UUID } from "../api/types";
import { ALL_LANGUAGES, defaultSearchConfig } from "../api/types";

function labelFor(code: string): string {
  return ALL_LANGUAGES.find((l) => l.code === code)?.label ?? code;
}
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function Searches() {
  const [searches, setSearches] = useState<Search[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<UUID | null>(null);
  const [newName, setNewName] = useState("");
  const [deleting, setDeleting] = useState<Search | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    refresh().then((list) => {
      if (list.length > 0) setEditing(list[0].id);
    });
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      const list = await api.listSearches();
      setSearches(list);
      return list;
    } finally {
      setLoading(false);
    }
  }

  async function createSearch() {
    if (!newName.trim()) return;
    const s = await api.createSearch(newName.trim(), searches.length === 0);
    setSearches((prev) => [...prev, s]);
    setEditing(s.id);
    setNewName("");
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
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <div className="card p-3">
        <div className="flex items-center gap-2">
          <input
            className="input"
            placeholder="New search name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") createSearch(); }}
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
                    <span className={`pill ${editing === s.id ? "bg-white/20 text-white" : "pill-blue"}`}>
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
            key={editing}
            searchId={editing}
            onChanged={() => refresh()}
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

// ---------------------------------------------------------------------------
// Search editor
// ---------------------------------------------------------------------------

function SearchEditor({
  searchId,
  onChanged,
  onDelete,
  onRun,
}: {
  searchId: UUID;
  onChanged: () => void;
  onDelete: (s: Search) => void;
  onRun: (id: UUID) => void;
}) {
  const [search, setSearch] = useState<Search | null>(null);
  const [name, setName] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [config, setConfig] = useState<SearchConfig>(defaultSearchConfig());
  const [languages, setLanguages] = useState<UniversityLanguage[]>([]);
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [s, langs, outs] = await Promise.all([
        api.getSearch(searchId),
        api.listLanguages(),
        api.listOutlets(),
      ]);
      setSearch(s);
      setName(s.name);
      setIsDefault(s.is_default);
      setConfig(s.config ?? defaultSearchConfig());
      setLanguages(langs);
      setOutlets(outs);
    })();
  }, [searchId]);

  const isValid = useMemo(() => {
    const hasTerms = config.terms.some((t) => t.text.trim());
    const hasDoi = config.doi.text.trim().length > 0;
    const hasUniName = config.university_name.enabled && config.university_name.language_ids.length > 0;
    return hasTerms || hasDoi || hasUniName;
  }, [config]);

  async function save() {
    if (!search) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.updateSearch(search.id, {
        name: name.trim(),
        is_default: isDefault,
        config,
      });
      setSearch(updated);
      setSavedAt(Date.now());
      onChanged();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
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

  const groupedOutlets = outlets.reduce<Record<string, Outlet[]>>((acc, o) => {
    const key = o.category || "Uncategorised";
    (acc[key] ??= []).push(o);
    return acc;
  }, {});

  return (
    <div className="card p-5 space-y-6">
      {/* Header */}
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
          <button
            className="btn-primary"
            disabled={!isValid}
            title={isValid ? undefined : "Add at least one term, DOI, or university name language"}
            onClick={() => onRun(search.id)}
          >
            Run now
          </button>
          <button className="btn-danger" onClick={() => onDelete(search)}>
            Delete
          </button>
        </div>
      </div>

      {/* §1 Search window */}
      <Section title="Search from">
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name={`sw-${searchId}`}
              checked={config.search_window === "last"}
              onChange={() => setConfig({ ...config, search_window: "last" })}
            />
            Last successful run
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name={`sw-${searchId}`}
              checked={config.search_window === "hours"}
              onChange={() => setConfig({ ...config, search_window: "hours" })}
            />
            Previous hours
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name={`sw-${searchId}`}
              checked={config.search_window === "range"}
              onChange={() => setConfig({ ...config, search_window: "range" })}
            />
            Date range
          </label>
        </div>
        {config.search_window === "range" ? (
          <div className="mt-2 flex flex-wrap items-end gap-3 text-sm">
            <div>
              <label className="mb-1 block text-xs text-slate-500">From</label>
              <input
                type="date"
                className="input w-44"
                value={config.date_from}
                onChange={(e) => setConfig({ ...config, date_from: e.target.value })}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">To (optional)</label>
              <input
                type="date"
                className="input w-44"
                value={config.date_to}
                onChange={(e) => setConfig({ ...config, date_to: e.target.value })}
              />
              <p className="mt-1 text-xs text-slate-500">Leave blank for up to today.</p>
            </div>
          </div>
        ) : (
          <div className="mt-2 flex items-center gap-2 text-sm">
            <label className="text-slate-600">
              {config.search_window === "last" ? "Fallback hours:" : "Hours to look back:"}
            </label>
            <input
              type="number"
              min={1}
              max={8760}
              className="input w-24"
              value={config.fallback_hours}
              onChange={(e) =>
                setConfig({ ...config, fallback_hours: Math.max(1, parseInt(e.target.value || "1", 10)) })
              }
            />
          </div>
        )}
      </Section>

      {/* §2 Terms */}
      <Section title="Search terms">
        <div className="space-y-2">
          {config.terms.map((term, idx) => (
            <TermRow
              key={term.id}
              term={term}
              index={idx}
              onChange={(updated) => {
                const next = [...config.terms];
                next[idx] = updated;
                setConfig({ ...config, terms: next });
              }}
              onRemove={() => {
                const next = config.terms.filter((_, i) => i !== idx);
                // Reset first term's operator to null
                if (next.length > 0) next[0] = { ...next[0], operator: null };
                setConfig({ ...config, terms: next });
              }}
            />
          ))}
          {config.terms.length === 0 && (
            <p className="text-sm text-slate-500">No terms yet. Add one below.</p>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            className="btn-ghost text-sm"
            onClick={() => {
              const newTerm: SearchTermConfig = {
                id: crypto.randomUUID(),
                text: "",
                operator: config.terms.length === 0 ? null : "OR",
              };
              setConfig({ ...config, terms: [...config.terms, newTerm] });
            }}
          >
            + Add term
          </button>
          <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
            <label className="whitespace-nowrap">Pages</label>
            <input
              type="number"
              min={1}
              max={10}
              className="input w-16"
              value={config.terms_pages}
              onChange={(e) =>
                setConfig({
                  ...config,
                  terms_pages: Math.max(1, Math.min(10, parseInt(e.target.value || "1", 10))),
                })
              }
            />
            <span
              className="text-slate-400"
              title="Page count applied to the combined search-terms query (10 results per page)."
            >
              ⓘ
            </span>
          </div>
        </div>
      </Section>

      {/* §3 DOI */}
      <Section title="DOI (optional)">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="mb-1 block text-xs text-slate-500">DOI string</label>
            <input
              className="input"
              placeholder="e.g. 10.1038/s41586-021-03819-2"
              value={config.doi.text}
              onChange={(e) => setConfig({ ...config, doi: { ...config.doi, text: e.target.value } })}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Pages</label>
            <input
              type="number"
              min={1}
              max={10}
              className="input w-20"
              value={config.doi.pages}
              onChange={(e) =>
                setConfig({
                  ...config,
                  doi: { ...config.doi, pages: Math.max(1, Math.min(10, parseInt(e.target.value || "1", 10))) },
                })
              }
            />
          </div>
        </div>
      </Section>

      {/* §4 University name */}
      <Section
        title="University name"
        toggle
        enabled={config.university_name.enabled}
        onToggle={(v) => setConfig({ ...config, university_name: { ...config.university_name, enabled: v } })}
      >
        {config.university_name.enabled && (
          <>
            {languages.length === 0 ? (
              <p className="text-sm text-amber-700 bg-amber-50 rounded-md px-3 py-2">
                No languages defined. Go to the{" "}
                <a href="/languages" className="underline font-medium">Languages page</a>{" "}
                to add them first.
              </p>
            ) : (
              <>
                <div className="mb-2 flex gap-2 text-xs">
                  <button
                    className="btn-ghost"
                    onClick={() =>
                      setConfig({
                        ...config,
                        university_name: {
                          ...config.university_name,
                          language_ids: languages.map((l) => l.id),
                        },
                      })
                    }
                  >
                    Select all
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() =>
                      setConfig({
                        ...config,
                        university_name: { ...config.university_name, language_ids: [] },
                      })
                    }
                  >
                    Clear all
                  </button>
                </div>
                <div className="max-h-80 overflow-y-auto rounded-md border border-slate-200">
                  <ul className="divide-y divide-slate-100">
                    {languages.map((lang) => {
                      const selected = config.university_name.language_ids.includes(lang.id);
                      return (
                        <li key={lang.id} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(e) => {
                              const ids = new Set(config.university_name.language_ids);
                              if (e.target.checked) ids.add(lang.id);
                              else ids.delete(lang.id);
                              setConfig({
                                ...config,
                                university_name: {
                                  ...config.university_name,
                                  language_ids: [...ids],
                                },
                              });
                            }}
                          />
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">
                            {lang.iso_code.toUpperCase()}
                          </span>
                          <span className="text-xs text-slate-500">{labelFor(lang.iso_code)}</span>
                          <span className="flex-1 truncate">{lang.university_name}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className="flex-1">
                    {config.university_name.language_ids.length} of {languages.length} languages
                    selected.
                  </span>
                  <label className="whitespace-nowrap">Pages per language</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    className="input w-16"
                    value={config.university_name.pages}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        university_name: {
                          ...config.university_name,
                          pages: Math.max(
                            1,
                            Math.min(10, parseInt(e.target.value || "1", 10)),
                          ),
                        },
                      })
                    }
                  />
                  <span
                    className="text-slate-400"
                    title="Page count applied to each per-language university-name query (10 results per page)."
                  >
                    ⓘ
                  </span>
                </div>
              </>
            )}
          </>
        )}
      </Section>

      {/* §5 Outlets */}
      <Section
        title="Outlets"
        toggle
        enabled={config.outlets.enabled}
        onToggle={(v) => setConfig({ ...config, outlets: { ...config.outlets, enabled: v } })}
      >
        {config.outlets.enabled && (
          <>
            <div className="flex gap-2 text-xs mb-2">
              <button
                className="btn-ghost"
                onClick={() =>
                  setConfig({
                    ...config,
                    outlets: {
                      ...config.outlets,
                      outlet_ids: outlets.filter((o) => o.is_active).map((o) => o.id),
                    },
                  })
                }
              >
                Select all active
              </button>
              <button
                className="btn-ghost"
                onClick={() => setConfig({ ...config, outlets: { ...config.outlets, outlet_ids: [] } })}
              >
                Clear
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto rounded-md border border-slate-200">
              {outlets.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-slate-500">
                  No outlets in your library yet.
                </p>
              ) : (
                Object.entries(groupedOutlets).map(([cat, list]) => {
                  const allSelected = list.every((o) => config.outlets.outlet_ids.includes(o.id));
                  return (
                    <details key={cat} open className="border-b border-slate-100 last:border-b-0">
                      <summary className="cursor-pointer bg-slate-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={(e) => {
                            const ids = new Set(config.outlets.outlet_ids);
                            list.forEach((o) => (e.target.checked ? ids.add(o.id) : ids.delete(o.id)));
                            setConfig({ ...config, outlets: { ...config.outlets, outlet_ids: [...ids] } });
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                        {cat} <span className="text-slate-400 font-normal">({list.length})</span>
                      </summary>
                      <ul className="divide-y divide-slate-100">
                        {list.map((o) => (
                          <li key={o.id} className="flex items-center gap-2 px-3 py-1.5">
                            <input
                              type="checkbox"
                              checked={config.outlets.outlet_ids.includes(o.id)}
                              onChange={(e) => {
                                const ids = new Set(config.outlets.outlet_ids);
                                if (e.target.checked) ids.add(o.id);
                                else ids.delete(o.id);
                                setConfig({ ...config, outlets: { ...config.outlets, outlet_ids: [...ids] } });
                              }}
                            />
                            <span className="flex-1 text-sm">{o.name}</span>
                            <span className="text-xs text-slate-500">{o.domain}</span>
                            {(o.keyword_langs || []).length > 0 && (
                              <span className="text-xs text-slate-400">
                                {o.keyword_langs.join(",").toUpperCase()}
                              </span>
                            )}
                            {(o.keyword_langs || []).length === 0 && (
                              <span className="text-xs text-amber-500" title="No language set — included in all queries">
                                all langs
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </details>
                  );
                })
              )}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {config.outlets.outlet_ids.length} of {outlets.length} outlets selected.
            </p>
          </>
        )}
      </Section>

      {/* Validation notice */}
      {!isValid && (
        <p className="text-sm text-amber-700 bg-amber-50 rounded-md px-3 py-2">
          Add at least one non-empty search term, a DOI, or enable University Name with at least one language before running.
        </p>
      )}

      {/* Footer actions */}
      <div className="flex items-center gap-3">
        <button className="btn-primary" disabled={saving} onClick={save}>
          {saving && <Spinner />} Save changes
        </button>
        {savedAt && (
          <span className="text-xs text-emerald-600">
            Saved {new Date(savedAt).toLocaleTimeString()}.
          </span>
        )}
        {saveError && <span className="text-xs text-red-600">{saveError}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({
  title,
  toggle,
  enabled,
  onToggle,
  children,
}: {
  title: string;
  toggle?: boolean;
  enabled?: boolean;
  onToggle?: (v: boolean) => void;
  children?: ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
        {toggle && (
          <button
            type="button"
            onClick={() => onToggle?.(!enabled)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
              enabled ? "bg-brand" : "bg-slate-200"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                enabled ? "translate-x-4" : "translate-x-1"
              }`}
            />
          </button>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Term row
// ---------------------------------------------------------------------------

function TermRow({
  term,
  index,
  onChange,
  onRemove,
}: {
  term: SearchTermConfig;
  index: number;
  onChange: (t: SearchTermConfig) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      {index > 0 ? (
        <select
          className="input w-20 text-xs"
          value={term.operator ?? "OR"}
          onChange={(e) => onChange({ ...term, operator: e.target.value as "AND" | "OR" | "NOT" })}
        >
          <option value="OR">OR</option>
          <option value="AND">AND</option>
          <option value="NOT">NOT</option>
        </select>
      ) : (
        <span className="w-20 text-center text-xs text-slate-400 italic">—</span>
      )}
      <input
        className="input flex-1"
        placeholder="Search term…"
        value={term.text}
        onChange={(e) => onChange({ ...term, text: e.target.value })}
      />
      <button
        className="text-slate-400 hover:text-red-600 transition-colors px-1"
        onClick={onRemove}
        title="Remove term"
      >
        ✕
      </button>
    </div>
  );
}
