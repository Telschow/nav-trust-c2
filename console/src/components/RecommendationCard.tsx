import clsx from "clsx";
import { AlertTriangle, Check, CheckCircle2, Hourglass, XCircle, X } from "lucide-react";
import { actionsOf, formatDuration, reasonText, titleOf, urgencyNote } from "../language";
import { TONE, vehicleColor } from "../tone";
import type { Decision, Recommendation } from "../types";

interface OpenProps {
  rec: Recommendation;
  now: number | null;
  disabled: boolean;
  onApprove: () => void;
  onDeny: () => void;
}

export function RecommendationCard({ rec, now, disabled, onApprove, onDeny }: OpenProps) {
  const remaining = now === null ? null : rec.expires_s - now;
  const total = rec.expires_s - rec.created_s;
  const expired = remaining !== null && remaining <= 0;
  const fraction = remaining === null ? 1 : Math.max(0, Math.min(1, remaining / total));
  const urgent = remaining !== null && remaining < 15 && !expired;
  return (
    <article
      className="panel relative overflow-hidden p-4"
      aria-label={`Recommendation: ${titleOf(rec)}`}
      style={{ borderColor: expired ? undefined : `${TONE.RED.hex}55` }}
    >
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: TONE.RED.hex }} aria-hidden />
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-bad">
            <AlertTriangle className="size-3.5" aria-hidden /> Needs your decision
          </div>
          <h3 className="mt-1.5 text-[17px] font-semibold leading-tight tracking-tight">{titleOf(rec)}</h3>
        </div>
        <span
          className="mt-0.5 inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-white/10"
          style={{ color: vehicleColor(rec.vehicle_id) }}
        >
          <span className="size-2 rounded-full" style={{ background: vehicleColor(rec.vehicle_id) }} aria-hidden />
          {rec.vehicle_id}
        </span>
      </div>

      <p className="mt-2 text-sm text-muted">
        <span className="text-text">Why:</span> {reasonText(rec.reason)}.
      </p>

      {urgencyNote(rec) && (
        <p className="mt-2 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm font-medium text-bad">
          {urgencyNote(rec)}
        </p>
      )}

      <div className="mt-3 rounded-lg bg-black/25 p-3">
        <div className="label mb-1.5">If you approve</div>
        <ul className="space-y-1 text-sm">
          {actionsOf(rec).map((a) => (
            <li key={a} className="flex items-start gap-2">
              <Check className="mt-0.5 size-3.5 shrink-0 text-accent" aria-hidden />
              {a}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between text-xs">
          <span className={clsx("flex items-center gap-1.5", expired ? "text-bad" : urgent ? "text-warn" : "text-muted")}>
            <Hourglass className="size-3.5" aria-hidden />
            {remaining === null ? "Expiry unknown" : expired ? "Expired, no longer actionable" : `Expires in ${formatDuration(remaining)}`}
          </span>
        </div>
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/8" aria-hidden>
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${fraction * 100}%`, background: urgent ? TONE.AMBER.hex : "#6ea8ff" }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2.5">
        <button
          type="button"
          onClick={onDeny}
          disabled={disabled || expired}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-white/4 px-3 py-2.5 text-sm font-medium text-text hover:bg-white/8 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <X className="size-4" aria-hidden /> Deny
        </button>
        <button
          type="button"
          onClick={onApprove}
          disabled={disabled || expired}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2.5 text-sm font-semibold text-[#06101f] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <Check className="size-4" aria-hidden /> Approve...
        </button>
      </div>
    </article>
  );
}

export function DecidedRow({ rec, decision }: { rec: Recommendation; decision: Decision }) {
  const approved = decision.outcome === "APPROVED";
  const expired = decision.outcome === "EXPIRED";
  const Icon = approved ? CheckCircle2 : expired ? Hourglass : XCircle;
  const failed = approved && decision.execution && !decision.execution.executed;
  return (
    <li className="rounded-xl border border-line-soft bg-black/15 px-3.5 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-sm font-medium">
          <Icon className={clsx("size-4", approved ? (failed ? "text-bad" : "text-ok") : "text-muted")} aria-hidden />
          {titleOf(rec)}
        </span>
        <span className="text-xs text-muted">
          {expired ? "Expired" : approved ? "Approved" : "Denied"}
          {!expired && ` by ${decision.operator}`}
        </span>
      </div>
      {approved && decision.execution && (
        <p className={clsx("mt-1.5 text-xs", failed ? "text-bad" : "text-muted")}>
          {failed
            ? `Not executed: ${decision.execution.reason ?? "unknown reason"}`
            : `Executed: ${decision.execution.actions.join("; ") || "nothing to send"}`}
        </p>
      )}
    </li>
  );
}
