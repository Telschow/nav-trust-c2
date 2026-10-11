import { formatDuration, titleOf, urgencyNote } from "../language";
import type { Recommendation } from "../types";

interface Props {
  open: Recommendation[]; // most urgent first
  now: number | null;
  onReview: () => void;
}

/** A solid band across the whole screen while any decision waits, so it cannot be missed
 * while looking at the map. It names the most urgent one and how long is left. */
export function DecisionBanner({ open, now, onReview }: Props) {
  const first = open[0];
  if (!first) return null;
  const remaining = now === null ? null : Math.max(0, first.expires_s - now);
  const rest = open.length - 1;
  return (
    <div className="flex shrink-0 items-center gap-4 bg-bad px-4 py-2 text-[#1c0808]">
      {/* only this part is announced; the countdown changes twice a second and would be read out each time */}
      <span role="alert" className="flex min-w-0 flex-1 items-center gap-4">
        <span className="font-semibold uppercase tracking-[0.08em]">Decision required</span>
        <span className="min-w-0 flex-1 truncate">
          <span className="font-semibold">{titleOf(first)}</span>
          {urgencyNote(first) && <span className="hidden lg:inline"> · {urgencyNote(first)}</span>}
          {rest > 0 && <span> · {rest} more waiting</span>}
        </span>
      </span>
      {remaining !== null && <span className="font-mono text-[13px] font-medium">expires in {formatDuration(remaining)}</span>}
      <button
        type="button"
        onClick={onReview}
        className="rounded-[2px] border border-[#1c0808] bg-[#1c0808] px-3 py-1 text-xs font-semibold text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      >
        Review
      </button>
    </div>
  );
}
