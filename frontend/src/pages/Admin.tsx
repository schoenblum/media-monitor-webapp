import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { User } from "../api/types";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function Admin() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "user">("user");
  const [created, setCreated] = useState<{ email: string; password: string } | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      setUsers(await api.listUsers());
    } finally {
      setLoading(false);
    }
  }

  async function createUser() {
    if (!newEmail.trim()) return;
    try {
      const r = await api.createUser(newEmail.trim(), newRole);
      setCreated({ email: r.user.email, password: r.initial_password });
      setNewEmail("");
      setNewRole("user");
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Create failed");
    }
  }

  async function toggleActive(u: User) {
    await api.updateUser(u.id, { is_active: !u.is_active });
    await refresh();
  }

  async function toggleRole(u: User) {
    await api.updateUser(u.id, { role: u.role === "admin" ? "user" : "admin" });
    await refresh();
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
                <th className="py-2">Credentials</th>
                <th className="py-2">Last login</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="py-1.5 font-medium">{u.email}</td>
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
                  <td className="py-1.5 text-xs text-slate-600">
                    {u.has_google_key && u.has_engine_id ? "Google ✓" : "—"}
                    {u.has_webhook_key ? " · Webhook ✓" : ""}
                  </td>
                  <td className="py-1.5 text-xs text-slate-600">
                    {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                  </td>
                  <td className="py-1.5 text-right">
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

      {created && <CreatedModal info={created} onClose={() => setCreated(null)} />}

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
    </div>
  );
}

function CreatedModal({ info, onClose }: { info: { email: string; password: string }; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="card w-full max-w-md p-5">
        <h2 className="text-lg font-semibold">User created</h2>
        <p className="mt-2 text-sm text-slate-600">
          Give this user their initial credentials below. They will be required to change the
          password on first login.
        </p>
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
