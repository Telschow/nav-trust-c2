import { Check, ShieldAlert } from "lucide-react";
import { useEffect, useRef } from "react";
import { actionsOf, titleOf } from "../language";
import type { Recommendation } from "../types";

interface Props {
  rec: Recommendation;
  operator: string;
  demo: boolean;
  busy: boolean;
  onOperatorChange: (name: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({ rec, operator, demo, busy, onOperatorChange, onCancel, onConfirm }: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/65 p-4 backdrop-blur-sm" onMouseDown={onCancel}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="panel w-full max-w-md p-6 shadow-2xl shadow-black/60"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent">
          <ShieldAlert className="size-4" aria-hidden /> Confirm approval
        </div>
        <h2 id="confirm-title" className="mt-2 text-xl font-semibold tracking-tight">
          {titleOf(rec)}
        </h2>

        <div className="mt-4 rounded-lg bg-black/30 p-3.5">
          <div className="label mb-2">This will</div>
          <ul className="space-y-1.5 text-sm">
            {actionsOf(rec).map((a) => (
              <li key={a} className="flex items-start gap-2">
                <Check className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
                {a}
              </li>
            ))}
          </ul>
        </div>

        <p className="mt-3 text-sm text-muted">
          {demo
            ? "Demo mode: no command is sent to any vehicle. The decision is still recorded."
            : "These commands are sent to the vehicles and the decision is recorded in the audit log."}
        </p>

        <label className="mt-4 block text-sm">
          <span className="label">Your name (recorded with the decision)</span>
          <input
            value={operator}
            onChange={(e) => onOperatorChange(e.target.value)}
            maxLength={40}
            className="mt-1.5 w-full rounded-lg border border-line bg-black/30 px-3 py-2.5 text-sm outline-none focus:border-accent"
          />
        </label>

        <div className="mt-5 grid grid-cols-2 gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-line bg-white/4 px-3 py-2.5 text-sm font-medium hover:bg-white/8 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            disabled={busy || operator.trim() === ""}
            onClick={onConfirm}
            className="rounded-lg bg-accent px-3 py-2.5 text-sm font-semibold text-[#06101f] hover:brightness-110 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            {busy ? "Sending..." : "Confirm approval"}
          </button>
        </div>
      </div>
    </div>
  );
}
