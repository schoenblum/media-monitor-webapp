import type { ReactNode } from "react";

export function ConfirmDialog(props: {
  open: boolean;
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!props.open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="card w-full max-w-md p-5">
        <h2 className="text-lg font-semibold">{props.title}</h2>
        {props.body && <div className="mt-2 text-sm text-slate-600">{props.body}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-secondary" onClick={props.onCancel}>
            {props.cancelLabel ?? "Cancel"}
          </button>
          <button
            className={props.danger ? "btn-danger" : "btn-primary"}
            onClick={props.onConfirm}
          >
            {props.confirmLabel ?? "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
