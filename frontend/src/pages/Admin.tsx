import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { University, User, UUID } from "../api/types";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../auth";

type CreatedInfo = { email: string; password: string; email_sent: boolean };

export default function Admin() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "user">("user");
  const [created, setCreated] = useState<CreatedInfo | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);
  const [duplicating, setDuplicating] = useState<User | null>(null);
  const [dupEmail, setDupEmail] = useState("");
  const [dupLoading, setDupLoading] = useState(false);

  // University CRUD state
  const [newUniName, setNewUniName] = useState("");
  const [renameUni, setRenameUni] = useState<University | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [deletingUni, setDeletingUni] = useState<University | null>(null);

  // Assign-to-university dialog state
  const [assigning, setAssigning] = useState<User | null>(null);
  const [assignChoice, setAssignChoice] = useState<UUID | "">("");
  const [assignDupRuns, setAssignDupRuns] = useState(false);
  const [assignLoading, setAssignLoading] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      const [u, unis] = await Promise.all([api.listUsers(), api.listUniversities()]);
      setUsers(u);
      setUniversities(unis);
    } finally {
      setLoading(false);
    }
  }

  async function createUser() {
    if (!newEmail.trim()) return;
    try {
      const r = await api.createUser(newEmail.trim(), newRole);
      setCreated({ email: r.user.email, password: r.initial_password, email_sent: r.email_sent });
      setNewEmail("");
      setNewRole("user");
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Create failed");
    }
  }

  async function toggleActive(u: User) {
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Update failed");
    }
  }

  async function toggleRole(u: User) {
    if (u.id === currentUser?.id && u.role === "admin") {
      if (!confirm("Demoting yourself will remove your admin access immediately. Continue?")) return;
    }
    try {
      await api.updateUser(u.id, { role: u.role === "admin" ? "user" : "admin" });
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Update failed");
    }
  }

  async function startDuplicate(u: User) {
    setDuplicating(u);
    setDupEmail("");
  }

  async function confirmDuplicate() {
    if (!duplicating || !dupEmail.trim()) return;
    setDupLoading(true);
    try {
      const r = await api.duplicateUser(duplicating.id, dupEmail.trim());
      setCreated({ email: r.user.email, password: r.initial_password, email_sent: r.email_sent });
      setDuplicating(null);
      setDupEmail("");
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Duplicate failed");
    } finally {
      setDupLoading(false);
    }
  }

  // --- University CRUD ---

  async function createUniversity() {
    if (!newUniName.trim()) return;
    try {
      await api.createUniversity(newUniName.trim());
      setNewUniName("");
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Create failed");
    }
  }

  async function commitRename() {
    if (!renameUni || !renameDraft.trim()) return;
    try {
      await api.renameUniversity(renameUni.id, renameDraft.trim());
      setRenameUni(null);
      setRenameDraft("");
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Rename failed");
    }
  }

  // --- Assign user to university ---

  function startAssign(u: User) {
    setAssigning(u);
    setAssignChoice(u.university_id ?? "");
    setAssignDupRuns(false);
  }

  async function commitAssign() {
    if (!assigning) return;
    setAssignLoading(true);
    try {
      const target = assignChoice === "" ? null : (assignChoice as UUID);
      await api.updateUser(assigning.id, {
        set_university: true,
        university_id: target,
      });
      // Optional history-duplication step (§8.3) — copies the user's
      // personal runs into the new university's pool. The originals stay
      // where they were (snapshot rule).
      if (assignDupRuns && target) {
        const rep = await api.duplicateRunsIntoUniversity(assigning.id, target);
        alert(
          `Duplicated ${rep.runs_copied} runs (${rep.results_copied} results) into the target university.`,
        );
      }
      setAssigning(null);
      setAssignChoice("");
      setAssignDupRuns(false);
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Assignment failed");
    } finally {
      setAssignLoading(false);
    }
  }

  if (loading) return <Spinner className="h-6 w-6 text-brand" />;

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <h2 className="text-base font-semibold">Create user</h2>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1.5fr_1fr_auto]">
          <input
            className="input"
            type="email"
            placeholder="email@example.com"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") createUser(); }}
          />
          <select
            className="input"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value as "admin" | "user")}
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
          <button className="btn-primary" onClick={createUser}>
            Create
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          The new user will be forced to change password on first login. The initial password is
          generated and shown <strong>once</strong>.
        </p>
      </div>

      <div className="card p-4">
        <h2 className="text-base font-semibold">Users</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2">Email</th>
                <th className="py-2">Role</th>
                <th className="py-2">Status</th>
                <th className="py-2">University</th>
                <th className="py-2">Credentials</th>
                <th className="py-2">Last login</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="py-1.5 font-medium">
                    {u.email}
                    {u.id === currentUser?.id && (
                      <span className="ml-2 text-xs text-slate-400">(you)</span>
                    )}
                  </td>
                  <td className="py-1.5">
                    <button
                      className={u.role === "admin" ? "pill-blue" : "pill-slate"}
                      onClick={() => toggleRole(u)}
                      title="Toggle role"
                    >
                      {u.role}
                    </button>
                  </td>
                  <td className="py-1.5">
                    <button
                      className={u.is_active ? "pill-green" : "pill-red"}
                      onClick={() => toggleActive(u)}
                    >
                      {u.is_active ? "active" : "disabled"}
                    </button>
                  </td>
                  <td className="py-1.5 text-xs">
                    {u.university_name ? (
                      <span className="pill-blue">{u.university_name}</span>
                    ) : (
                      <span className="text-slate-400">— unaffiliated —</span>
                    )}
                  </td>
                  <td className="py-1.5 text-xs text-slate-600">
                    {u.has_google_key && u.has_engine_id ? "Google ✓" : "—"}
                    {u.has_webhook_key ? " · Webhook ✓" : ""}
                  </td>
                  <td className="py-1.5 text-xs text-slate-600">
                    {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                  </td>
                  <td className="py-1.5 text-right">
                    <button
                      className="btn-ghost mr-1"
                      onClick={() => startAssign(u)}
                      title="Assign / move / unaffiliate"
                    >
                      Affiliation
                    </button>
                    <button
                      className="btn-ghost mr-1"
                      onClick={() => startDuplicate(u)}
                      title="Duplicate user — copies searches, outlets, languages, and run history"
                    >
                      Duplicate
                    </button>
                    <button className="btn-ghost text-red-600" onClick={() => setDeleting(u)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Universities CRUD */}
      <div className="card p-4">
        <h2 className="text-base font-semibold">Universities</h2>
        <p className="mt-1 text-xs text-slate-500">
          Members of a university <strong>share</strong> their Languages and Outlets and see each
          other's run history. Login and Google API credentials always stay per-user.
        </p>
        <div className="mt-3 flex gap-2">
          <input
            className="input max-w-md"
            placeholder="New university name…"
            value={newUniName}
            onChange={(e) => setNewUniName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") createUniversity(); }}
          />
          <button className="btn-primary" onClick={createUniversity} disabled={!newUniName.trim()}>
            Add
          </button>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2">Name</th>
                <th className="py-2 text-right">Members</th>
                <th className="py-2">Created</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {universities.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-500">
                    No universities yet.
                  </td>
                </tr>
              )}
              {universities.map((uni) => (
                <tr key={uni.id} className="border-t border-slate-100">
                  <td className="py-1.5 font-medium">{uni.name}</td>
                  <td className="py-1.5 text-right tabular-nums">{uni.member_count}</td>
                  <td className="py-1.5 text-xs text-slate-600">
                    {new Date(uni.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-1.5 text-right">
                    <button
                      className="btn-ghost mr-1"
                      onClick={() => { setRenameUni(uni); setRenameDraft(uni.name); }}
                    >
                      Rename
                    </button>
                    <button
                      className="btn-ghost text-red-600"
                      onClick={() => setDeletingUni(uni)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {created && <CreatedModal info={created} onClose={() => setCreated(null)} />}

      {/* Duplicate user dialog */}
      {duplicating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="card w-full max-w-md p-5">
            <h2 className="text-lg font-semibold">Duplicate user</h2>
            <p className="mt-2 text-sm text-slate-600">
              Create a new account with all the data from{" "}
              <strong>{duplicating.email}</strong> (searches, languages, outlets, run history).
              Enter the new account's email address:
            </p>
            <input
              className="input mt-3 w-full"
              type="email"
              placeholder="new-user@example.com"
              value={dupEmail}
              onChange={(e) => setDupEmail(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirmDuplicate(); }}
              autoFocus
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                className="btn-secondary"
                onClick={() => { setDuplicating(null); setDupEmail(""); }}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!dupEmail.trim() || dupLoading}
                onClick={confirmDuplicate}
              >
                {dupLoading && <Spinner />} Duplicate
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Affiliation assign / move / unaffiliate */}
      {assigning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="card w-full max-w-md p-5">
            <h2 className="text-lg font-semibold">Affiliation for {assigning.email}</h2>
            <p className="mt-2 text-sm text-slate-600">
              Pick a university to add this user to a shared pool of Languages, Outlets, and run
              history. Choose <em>— unaffiliated —</em> to return them to single-tenant mode.
            </p>
            <select
              className="input mt-3 w-full"
              value={assignChoice}
              onChange={(e) => setAssignChoice(e.target.value as UUID | "")}
            >
              <option value="">— unaffiliated —</option>
              {universities.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.member_count} member{u.member_count === 1 ? "" : "s"})
                </option>
              ))}
            </select>
            {assignChoice && assignChoice !== assigning.university_id && (
              <label className="mt-3 flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={assignDupRuns}
                  onChange={(e) => setAssignDupRuns(e.target.checked)}
                />
                <span>
                  Also <strong>duplicate this user's personal run history</strong> into the new
                  university's pool. Originals stay where they were (snapshot rule).
                </span>
              </label>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                className="btn-secondary"
                onClick={() => { setAssigning(null); setAssignChoice(""); setAssignDupRuns(false); }}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={assignLoading}
                onClick={commitAssign}
              >
                {assignLoading && <Spinner />} Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename university */}
      {renameUni && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="card w-full max-w-md p-5">
            <h2 className="text-lg font-semibold">Rename university</h2>
            <input
              className="input mt-3 w-full"
              value={renameDraft}
              onChange={(e) => setRenameDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") commitRename(); }}
              autoFocus
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                className="btn-secondary"
                onClick={() => { setRenameUni(null); setRenameDraft(""); }}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!renameDraft.trim() || renameDraft.trim() === renameUni.name}
                onClick={commitRename}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleting}
        title={`Delete ${deleting?.email}?`}
        body="This permanently removes the user and all of their searches, outlets, and runs."
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting) await api.deleteUser(deleting.id);
          setDeleting(null);
          await refresh();
        }}
      />

      <ConfirmDialog
        open={!!deletingUni}
        title={`Delete ${deletingUni?.name}?`}
        body={
          <span>
            The university will be removed and all of its <strong>{deletingUni?.member_count ?? 0}</strong>{" "}
            members will become unaffiliated. Their shared Languages, Outlets, and runs revert to
            personal ownership (the rows are not deleted).
          </span>
        }
        confirmLabel="Delete"
        danger
        onCancel={() => setDeletingUni(null)}
        onConfirm={async () => {
          if (deletingUni) await api.deleteUniversity(deletingUni.id);
          setDeletingUni(null);
          await refresh();
        }}
      />
    </div>
  );
}

function CreatedModal({
  info,
  onClose,
}: {
  info: CreatedInfo;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="card w-full max-w-md p-5">
        <h2 className="text-lg font-semibold">User created</h2>
        <p className="mt-2 text-sm text-slate-600">
          Give this user their initial credentials below. They will be required to change the
          password on first login.
        </p>
        {info.email_sent ? (
          <p className="mt-2 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            A welcome email will be sent to <strong>{info.email}</strong>. The password below is
            shown only once — keep it handy in case delivery fails.
          </p>
        ) : (
          <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700">
            No SMTP configured — share the credentials below with the user manually.
          </p>
        )}
        <div className="mt-3 space-y-2 text-sm">
          <div>
            <div className="text-xs uppercase text-slate-400">Email</div>
            <div className="font-mono">{info.email}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-slate-400">Initial password</div>
            <code className="block select-all rounded bg-slate-900 px-3 py-2 text-emerald-200">
              {info.password}
            </code>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            className="btn-secondary"
            onClick={() => navigator.clipboard.writeText(info.password)}
          >
            Copy password
          </button>
          <button className="btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
