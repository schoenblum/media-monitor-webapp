import { Spinner } from "./Spinner";
import type { RunStatus } from "../api/types";

/**
 * Attention-only run status indicator (v2.4 item 5).
 *
 * - `complete` → renders nothing. The row already carries the hit count, which
 *   says "ran fine" without a redundant green pill.
 * - `failed`   → loud red badge. The caller is expected to also show the
 *   error_message inline (see RunHistoryRow / Dashboard list).
 * - `skipped`  → calm amber/grey badge — distinct from `failed` because a
 *   skip is informative, not a crash.
 * - `running` / `pending` → transient indicator with a spinner, signalling
 *   "still in flight" rather than acting like a permanent column value.
 */
export function RunStatusPill({ status }: { status: RunStatus }) {
  switch (status) {
    case "complete":
      return null;
    case "running":
      return (
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Spinner className="h-3 w-3 text-brand" /> Running…
        </span>
      );
    case "pending":
      return (
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Spinner className="h-3 w-3 text-slate-400" /> Queued…
        </span>
      );
    case "failed":
      return <span className="pill-red">Failed</span>;
    case "skipped":
      return <span className="pill-amber">Skipped</span>;
  }
}
