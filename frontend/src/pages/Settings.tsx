import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Search } from "../api/types";
import { useAuth } from "../auth";
import { Spinner } from "../components/Spinner";
import { ConfirmDialog } from "../components/ConfirmDialog";

export default function Settings() {
  const { user, refresh } = useAuth();
  const [email, setEmail] = useState(user?.email ?? "");
  const [backupEmail, setBackupEmail] = useState(user?.backup_email ?? "");
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [engineId, setEngineId] = useState("");
  const [searches, setSearches] = useState<Search[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [newWebhookKey, setNewWebhookKey] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  useEffect(() => {
    setEmail(user?.email ?? "");
    setBackupEmail(user?.backup_email ?? "");
  }, [user]);

  useEffect(() => {
    api.listSearches().then(setSearches);
  }, []);

  async function saveProfile() {
    setBusy("profile");
    try {
      await api.updateMe({
        email: email !== user?.email ? email : undefined,
        backup_email: backupEmail !== user?.backup_email ? backupEmail : undefined,
      });
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function changePw() {
    if (newPw.length < 8) return alert("New password must be at least 8 characters.");
    if (newPw !== confirmPw) return alert("Passwords do not match.");
    setBusy("pw");
    try {
      await api.changePassword(currentPw, newPw);
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      alert("Password changed.");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Change failed");
    } finally {
      setBusy(null);
    }
  }

  async function saveCreds() {
    if (!googleKey.trim() || !engineId.trim()) return;
    setBusy("creds");
    try {
      await api.updateCredentials(googleKey.trim(), engineId.trim());
      setGoogleKey("");
      setEngineId("");
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function removeCreds() {
    setBusy("creds-rm");
    try {
      await api.deleteCredentials();
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  async function genWebhook() {
    setBusy("hook");
    try {
      const r = await api.generateWebhookKey();
      setNewWebhookKey(r.api_key);
      await refresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Generate failed");
    } finally {
      setBusy(null);
    }
  }

  async function revokeWebhook() {
    setBusy("hook-rm");
    try {
      await api.revokeWebhookKey();
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  async function setDefaultSearch(id: string) {
    await api.updateSearch(id, { is_default: true });
    setSearches(await api.listSearches());
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Section title="Account email">
        <label className="label">Login email</label>
        <input className="input mt-1" value={email} onChange={(e) => setEmail(e.target.value)} />
        <label className="label mt-3">Backup email (optional)</label>
        <input
          className="input mt-1"
          value={backupEmail}
          onChange={(e) => setBackupEmail(e.target.value)}
        />
        <div className="mt-3">
          <button className="btn-primary" disabled={busy !== null} onClick={saveProfile}>
            {busy === "profile" && <Spinner />} Save
          </button>
        </div>
      </Section>

      <Section title="Change password">
        <label className="label">Current password</label>
        <input
          type="password"
          className="input mt-1"
          value={currentPw}
          onChange={(e) => setCurrentPw(e.target.value)}
        />
        <label className="label mt-3">New password</label>
        <input
          type="password"
          className="input mt-1"
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
        />
        <label className="label mt-3">Confirm new password</label>
        <input
          type="password"
          className="input mt-1"
          value={confirmPw}
          onChange={(e) => setConfirmPw(e.target.value)}
        />
        <div className="mt-3">
          <button className="btn-primary" disabled={busy !== null} onClick={changePw}>
            {busy === "pw" && <Spinner />} Update password
          </button>
        </div>
      </Section>

      <Section title="Google Custom Search credentials">
        <p className="text-sm text-slate-600">
          Status:{" "}
          {user?.has_google_key && user?.has_engine_id ? (
            <span className="pill-green">configured</span>
          ) : (
            <span className="pill-amber">not configured</span>
          )}
        </p>
        <label className="label mt-3">API Key</label>
        <input
          type="password"
          className="input mt-1"
          placeholder={user?.has_google_key ? "••••••••" : "AIza…"}
          value={googleKey}
          onChange={(e) => setGoogleKey(e.target.value)}
        />
        <label className="label mt-3">Search Engine ID</label>
        <input
          type="password"
          className="input mt-1"
          placeholder={user?.has_engine_id ? "••••••••" : "a12b3c4d…"}
          value={engineId}
          onChange={(e) => setEngineId(e.target.value)}
        />
        <div className="mt-3 flex gap-2">
          <button className="btn-primary" disabled={busy !== null} onClick={saveCreds}>
            {busy === "creds" && <Spinner />} Save credentials
          </button>
          {(user?.has_google_key || user?.has_engine_id) && (
            <button className="btn-secondary" disabled={busy !== null} onClick={removeCreds}>
              Remove
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Stored encrypted at rest. The Manual page has step-by-step instructions for obtaining
          these.
        </p>
      </Section>

      <Section title="Webhook API key">
        <p className="text-sm text-slate-600">
          Status:{" "}
          {user?.has_webhook_key ? (
            <span className="pill-green">configured</span>
          ) : (
            <span className="pill-slate">not configured</span>
          )}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Use this to trigger searches from external systems. The key is shown <strong>once</strong>{" "}
          on generation; if lost, revoke and regenerate.
        </p>
        <div className="mt-3 flex gap-2">
          <button className="btn-primary" disabled={busy !== null} onClick={genWebhook}>
            {busy === "hook" && <Spinner />}{" "}
            {user?.has_webhook_key ? "Regenerate" : "Generate"} key
          </button>
          {user?.has_webhook_key && (
            <button
              className="btn-secondary"
              disabled={busy !== null}
              onClick={() => setConfirmRevoke(true)}
            >
              Revoke
            </button>
          )}
        </div>
      </Section>

      <Section title="Default search">
        {searches.length === 0 ? (
          <p className="text-sm text-slate-500">Create a search first.</p>
        ) : (
          <ul className="space-y-1">
            {searches.map((s) => (
              <li key={s.id} className="flex items-center justify-between">
                <span className="text-sm">{s.name}</span>
                {s.is_default ? (
                  <span className="pill-blue">default</span>
                ) : (
                  <button className="btn-ghost text-xs" onClick={() => setDefaultSearch(s.id)}>
                    Make default
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <NewKeyModal
        apiKey={newWebhookKey}
        onClose={() => setNewWebhookKey(null)}
      />

      <ConfirmDialog
        open={confirmRevoke}
        title="Revoke webhook key?"
        body="Any external system using the existing key will stop working immediately."
        confirmLabel="Revoke"
        danger
        onCancel={() => setConfirmRevoke(false)}
        onConfirm={async () => {
          await revokeWebhook();
          setConfirmRevoke(false);
        }}
      />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <h2 className="text-base font-semibold">{title}</h2>
      <div className="mt-3 space-y-1">{children}</div>
    </div>
  );
}

function NewKeyModal({ apiKey, onClose }: { apiKey: string | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  if (!apiKey) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="card w-full max-w-md p-5">
        <h2 className="text-lg font-semibold">Webhook key created</h2>
        <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Copy this key now — you will not be able to see it again. If you lose it, you must
          revoke and regenerate.
        </p>
        <pre className="mt-3 select-all overflow-x-auto rounded bg-slate-900 p-3 text-xs text-emerald-200">
          {apiKey}
        </pre>
        <div className="mt-4 flex justify-end gap-2">
          <button
            className="btn-secondary"
            onClick={async () => {
              await navigator.clipboard.writeText(apiKey);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? "Copied!" : "Copy"}
          </button>
          <button className="btn-primary" onClick={onClose}>
            I have saved it
          </button>
        </div>
      </div>
    </div>
  );
}
