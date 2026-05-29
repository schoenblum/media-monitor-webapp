import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { UUID } from "../api/types";
import { Spinner } from "./Spinner";

/**
 * Emails the CSV of selected hits across `runIds` to an address. The address
 * is pre-filled with the user's login email (passed as `defaultEmail`) but can
 * be changed before sending. Shared by RunDetail and the Run History merge view.
 */
export function EmailExportDialog({
  open,
  onClose,
  runIds,
  defaultEmail,
}: {
  open: boolean;
  onClose: () => void;
  runIds: UUID[];
  defaultEmail: string;
}) {
  const [email, setEmail] = useState(defaultEmail);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setEmail(defaultEmail);
      setError(null);
      setSentTo(null);
    }
  }, [open, defaultEmail]);

  if (!open) return null;

  async function send() {
    setSending(true);
    setError(null);
    try {
      const r = await api.emailRuns(runIds, email.trim());
      setSentTo(r.email);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send the email.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="card w-full max-w-md p-5">
        <h2 className="text-lg font-semibold">Email selected hits</h2>
        {sentTo ? (
          <>
            <p className="mt-2 text-sm text-emerald-700">
              Sent to <strong>{sentTo}</strong>. The CSV is attached to the message.
            </p>
            <div className="mt-4 flex justify-end">
              <button className="btn-primary" onClick={onClose}>
                Done
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="mt-1 text-sm text-slate-600">
              Sends a CSV of the ticked results as an email attachment. Only ticked
              rows are included.
            </p>
            <label className="mt-3 flex flex-col gap-1 text-sm">
              <span className="text-xs text-slate-500">Deliver to</span>
              <input
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button className="btn-secondary" onClick={onClose} disabled={sending}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={send}
                disabled={sending || !email.trim()}
              >
                {sending && <Spinner />} Send email
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
