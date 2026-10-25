import clsx from "clsx";
import { Check, Hourglass, X } from "lucide-react";
import { STATE_LABEL, actionsOf, contextNote, formatDuration, ordinal, reasonText, titleOf, urgencyNote } from "../language";
import type { RaisedAgain } from "../store";
import { TONE, vehicleColor } from "../tone";
import type { Decision, NavTrust, Recommendation } from "../types";

interface OpenProps {
  rec: Recommendation;
  now: number | null;
  /** set when this repeats a recommendation that expired unanswered */
  raisedAgain?: RaisedAgain | null | undefined;
  disabled: boolean;
  /** the vehicle cannot be heard now, so a command to it may not arrive */
  noLink?: boolean;
  onApprove: () => void;
  onDeny: () => void;
}

export function RecommendationCard({ rec, now, raisedAgain, disabled, noLink = false, onApprove, onDeny }: OpenProps) {
  const remaining = now === null ? null : rec.expires_s - now;
  const total = rec.expires_s - rec.created_s;
  const expired = remaining !== null && remaining <= 0;
  const fraction = remaining === null ? 1 : Math.max(0, Math.min(1, remaining / total));
  const urgent = remaining !== null && remaining < 15 && !expired;
  return (
    <article
      id={`rec-${rec.id}`}
      className={clsx("panel overflow-hidden", expired ? "" : "border-bad/70")}
      aria-label={`Recommendation: ${titleOf(rec)}`}
    >
      <header className={clsx("flex items-center justify-between px-4 py-1.5", expired ? "bg-panel-2 text-muted" : "bg-bad text-[#1c0808]")}>
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]">Needs your decision</span>
        <span className="font-mono text-xs font-medium">{rec.vehicle_id}</span>
      </header>

      <div className="px-4 pb-4 pt-3">
        <h3 className="text-[17px] font-semibold leading-tight">{titleOf(rec)}</h3>
        {raisedAgain && (
          <p className="mt-2 border-l-2 border-warn pl-3 text-sm">
            {`Raised again, ${ordinal(raisedAgain.nth)} time. The previous one expired unanswered at T+${formatDuration(raisedAgain.previousExpiredAt_s)}.`}
          </p>
        )}
        <p className="mt-2 text-sm text-muted">
          <span className="text-text">Why:</span> {reasonText(rec.reason)}.
        </p>

        {noLink && rec.command !== null && (
          <p className="mt-2 text-sm text-accent">{rec.vehicle_id} has no link. A command may not reach it.</p>
        )}

        {contextNote(rec) && <p className="mt-2 text-sm text-muted">{contextNote(rec)}</p>}

        {urgencyNote(rec) && (
          <p className="mt-3 border border-bad/60 px-3 py-2 text-sm font-medium text-bad">{urgencyNote(rec)}</p>
        )}

        <div className="mt-4 border-t border-line pt-3">
          <div className="label mb-2">If you approve</div>
          <ul className="space-y-1.5 text-sm">
            {actionsOf(rec).map((a) => (
              <li key={a} className="flex items-start gap-2">
                <Check className="mt-0.5 size-3.5 shrink-0 text-accent" aria-hidden />
                {a}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-4">
          <div className={clsx("flex items-center gap-1.5 text-xs", expired ? "text-bad" : urgent ? "text-warn" : "text-muted")}>
            <Hourglass className="size-3.5" aria-hidden />
            {remaining === null ? "Expiry unknown" : expired ? "Expired, no longer actionable" : `Expires in ${formatDuration(remaining)}`}
          </div>
          <div className="mt-1.5 h-1 bg-line-soft" aria-hidden>
            <div
              className="h-full transition-[width] duration-500"
              style={{ width: `${fraction * 100}%`, background: urgent ? TONE.AMBER.hex : "#6aa9e9" }}
            />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onDeny}
            disabled={disabled || expired}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-[3px] border border-line text-sm font-medium text-text hover:bg-panel-2 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <X className="size-4" aria-hidden /> Deny
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={disabled || expired}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-[3px] bg-accent text-sm font-semibold text-[#08121d] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <Check className="size-4" aria-hidden /> Approve...
          </button>
        </div>
      </div>
    </article>
  );
}

/** An expired recommendation that stays in view until the operator marks it seen, so that an
 * expiry never slides quietly into the history. */
export function ExpiredNotice({
  rec,
  decision,
  trustNow,
  noLink = false,
  onSeen,
}: {
  rec: Recommendation;
  decision: Decision;
  trustNow: NavTrust | undefined;
  /** the vehicle could not be heard when this expired, so its trust state was only the last one known */
  noLink?: boolean;
  onSeen: () => void;
}) {
  return (
    <article className="panel border-warn/60 px-4 py-3" aria-label={`Expired: ${titleOf(rec)}`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-warn">Expired, nobody answered</span>
        <span className="font-mono text-xs text-muted">T+{formatDuration(decision.decided_s)}</span>
      </div>
      <p className="mt-1.5 text-sm font-medium">{titleOf(rec)}</p>
      <p className="mt-1 text-xs text-muted">
        Nothing was sent to the vehicle.{" "}
        {!trustNow
          ? `${rec.vehicle_id}: state not known.`
          : noLink
            ? `${rec.vehicle_id} had no link; its last known state was ${STATE_LABEL[trustNow.state]}.`
            : `${rec.vehicle_id} is now ${STATE_LABEL[trustNow.state]}.`}
      </p>
      <button
        type="button"
        onClick={onSeen}
        className="mt-2.5 h-8 rounded-[3px] border border-line px-3 text-xs font-medium hover:bg-panel-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        Seen
      </button>
    </article>
  );
}

export function DecidedRow({ rec, decision }: { rec: Recommendation; decision: Decision }) {
  const approved = decision.outcome === "APPROVED";
  const expired = decision.outcome === "EXPIRED";
  const failed = approved && decision.execution && !decision.execution.executed;
  return (
    <li className="border-b border-line-soft py-2.5 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-2 text-sm">
          <span
            className="size-1.5 shrink-0 rounded-[1px]"
            style={{ background: vehicleColor(rec.vehicle_id) }}
            aria-hidden
          />
          {titleOf(rec)}
        </span>
        <span className={clsx("shrink-0 text-xs", approved ? (failed ? "text-bad" : "text-ok") : "text-muted")}>
          {expired ? "Expired" : approved ? "Approved" : "Denied"}
          {!expired && ` by ${decision.operator}`}
        </span>
      </div>
      {approved && decision.execution && (
        <p className={clsx("mt-1 text-xs", failed ? "text-bad" : "text-muted")}>
          {failed
            ? `Not executed: ${decision.execution.reason ?? "unknown reason"}`
            : `Executed: ${decision.execution.actions.join("; ") || "nothing to send"}`}
        </p>
      )}
    </li>
  );
}
