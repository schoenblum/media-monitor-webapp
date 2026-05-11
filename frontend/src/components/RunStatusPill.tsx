import type { RunStatus } from "../api/types";

export function RunStatusPill({ status }: { status: RunStatus }) {
  switch (status) {
    case "complete":
      return <span className="pill-green">Complete</span>;
    case "running":
      return <span className="pill-blue">Running…</span>;
    case "pending":
      return <span className="pill-slate">Pending</span>;
    case "failed":
      return <span className="pill-red">Failed</span>;
  }
}
