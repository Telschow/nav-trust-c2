import { Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { actionsOf, titleOf } from "../language";
import type { Recommendation } from "../types";

/** How long the confirm control must be held to approve a landing (a proposal, to be tested with
 * operators). Landing is the one irreversible command, so approving it takes a deliberate act. */
export const HOLD_TO_CONFIRM_MS = 1500;

type HoldPhase = "idle" | "holding" | "released";

function useHold(durationMs: number, onComplete: () => void, enabled: boolean) {
  const [phase, setPhase] = useState<HoldPhase>("idle");
  const timer = useRef<number | null>(null);
  const done = useRef(onComplete);
  done.current = onComplete;
  const stillEnabled = useRef(enabled);
  stillEnabled.current = enabled;
  const stop = (next: HoldPhase) => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    const wasHolding = timer.current !== null;
    timer.current = null;
    setPhase(wasHolding ? next : "idle");
  };
  const release = () => stop("released");
  const start = () => {
    if (!enabled || timer.current !== null) return;
    setPhase("holding");
    timer.current = window.setTimeout(() => {
      timer.current = null;
      // the name may have been cleared, or the request sent, while the button was held
      if (!stillEnabled.current) return setPhase("released");
      setPhase("idle");
      done.current();
    }, durationMs);
  };
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);
  return { phase, holding: phase === "holding", start, release };
}

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
  const landing = rec.command === "LAND";
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const canConfirm = !busy && operator.trim() !== "";
  const hold = useHold(HOLD_TO_CONFIRM_MS, onConfirm, canConfirm);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  // Once, when the dialog opens. The console re-renders on every keystroke and live update with a
  // new onCancel; re-running this on each render pulled focus out of the name field onto
  // "Confirm approval", so a space typed in a name approved the command.
  useEffect(() => {
    // a landing does not open on its confirm control, so one stray key cannot start it
    (landing ? cancelButtonRef : confirmRef).current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && cancelRef.current();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onMouseDown={onCancel}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="panel w-full max-w-md p-6"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="label text-accent">Confirm approval</div>
        <h2 id="confirm-title" className="mt-2 text-xl font-semibold">
          {titleOf(rec)}
        </h2>

        <div className="mt-4 border-t border-line pt-3">
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

        <p className="mt-4 text-sm text-muted">
          {demo
            ? "Demo mode: no command is sent to any vehicle. The decision is still recorded."
            : "These commands are sent to the vehicles and the decision is recorded in the audit log."}
        </p>

        {landing && (
          <p id="hold-hint" className="mt-4 border border-bad/60 px-3 py-2 text-sm font-medium text-bad">
            Landing cannot be undone. Press and hold the button for {HOLD_TO_CONFIRM_MS / 1000} seconds to
            confirm; release early to cancel.
          </p>
        )}

        {landing && (
          <span role="status" className="sr-only">
            {hold.phase === "holding"
              ? "Holding. Keep holding to confirm the landing."
              : hold.phase === "released"
                ? "Released. Nothing was approved."
                : ""}
          </span>
        )}

        <label className="mt-4 block text-sm">
          <span className="label">Your name (recorded with the decision)</span>
          <input
            value={operator}
            onChange={(e) => onOperatorChange(e.target.value)}
            maxLength={40}
            className="mt-1.5 h-10 w-full rounded-[3px] border border-line bg-ink px-3 text-sm outline-none focus:border-accent"
          />
        </label>

        <div className="mt-5 grid grid-cols-2 gap-2">
          <button
            type="button"
            ref={cancelButtonRef}
            onClick={onCancel}
            className="h-10 rounded-[3px] border border-line text-sm font-medium hover:bg-panel-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Cancel
          </button>
          {landing ? (
            <button
              type="button"
              disabled={!canConfirm}
              aria-describedby="hold-hint"
              onPointerDown={(e) => {
                // keep the pointer on the button, so finger jitter at its edge does not cancel a touch hold
                e.currentTarget.setPointerCapture?.(e.pointerId);
                hold.start();
              }}
              onPointerUp={hold.release}
              onPointerCancel={hold.release}
              onContextMenu={(e) => e.preventDefault()}
              onBlur={hold.release}
              onKeyDown={(e) => {
                if ((e.key === " " || e.key === "Enter") && !e.repeat) {
                  e.preventDefault();
                  hold.start();
                }
              }}
              onKeyUp={(e) => {
                if (e.key === " " || e.key === "Enter") {
                  e.preventDefault();
                  hold.release();
                }
              }}
              data-holding={hold.holding}
              className="relative h-10 touch-none select-none overflow-hidden rounded-[3px] bg-accent text-sm font-semibold text-[#08121d] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              <span
                aria-hidden
                className="absolute inset-y-0 left-0 bg-white/45"
                style={{
                  width: hold.holding ? "100%" : "0%",
                  transition: hold.holding ? `width ${HOLD_TO_CONFIRM_MS}ms linear` : "none",
                }}
              />
              <span className="relative">
                {busy ? "Sending..." : hold.holding ? "Keep holding..." : "Hold to confirm landing"}
              </span>
            </button>
          ) : (
            <button
              ref={confirmRef}
              type="button"
              disabled={!canConfirm}
              onClick={onConfirm}
              className="h-10 rounded-[3px] bg-accent text-sm font-semibold text-[#08121d] hover:brightness-110 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              {busy ? "Sending..." : "Confirm approval"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
