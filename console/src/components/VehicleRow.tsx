import clsx from "clsx";
import {
  calibrationText,
  formatBound,
  formatDuration,
  formatPercent,
  headroomLevel,
  reasonText,
} from "../language";
import type { HistoryPoint, LinkInfo } from "../store";
import { vehicleColor } from "../tone";
import type { Calibration, NavTrust, Sector } from "../types";
import { LinkBadge } from "./LinkBadge";
import { StateChip } from "./StateChip";
import { TrustStrip } from "./TrustStrip";

interface Props {
  vehicleId: string;
  trust: NavTrust;
  since: number | undefined;
  now: number | null;
  sectors: Sector[];
  doneSectors: string[];
  history: HistoryPoint[];
  calibration: Calibration | null;
  /** undefined: the backend says nothing about the link, so none is shown */
  link?: LinkInfo | undefined;
  onFocus: () => void;
}

export function VehicleRow({
  vehicleId,
  trust,
  since,
  now,
  sectors,
  doneSectors,
  history,
  calibration,
  link,
  onFocus,
}: Props) {
  const noLink = link?.state === "NO_LINK";
  const inState = since !== undefined && now !== null ? formatDuration(now - since) : "-";
  return (
    <button
      type="button"
      onClick={onFocus}
      className={clsx(
        "block w-full border-b border-line-soft px-4 py-3 text-left hover:bg-panel-2",
        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent",
        trust.state === "RED" && "bg-bad/10 hover:bg-bad/14",
      )}
      aria-label={`${vehicleId}, ${trust.state}${noLink ? ", no link, last known state" : ""}. Show on map`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2.5">
          <span
            className="size-2.5 rounded-[1px]"
            style={{ background: vehicleColor(vehicleId) }}
            aria-hidden
          />
          <span className="font-mono text-[15px] font-medium">{vehicleId}</span>
        </span>
        <span className="flex items-center gap-1.5">
          {noLink && <LinkBadge />}
          <StateChip state={trust.state} lastKnown={noLink} />
        </span>
      </div>

      {noLink && link && (
        <p className="mt-1 text-xs text-accent">
          {now !== null ? `Last heard ${formatDuration(now - link.lastHeard_s)} ago` : "Last heard: unknown"}
        </p>
      )}

      <p className={clsx("mt-1 text-[13px] leading-snug", trust.state === "GREEN" ? "text-muted" : "text-text")}>
        {reasonText(trust.reason)}
      </p>

      <dl className="mt-2 grid grid-cols-[1.25fr_0.75fr_1fr] divide-x divide-line-soft border-y border-line-soft text-xs">
        <Metric
          label="Position error"
          value={noLink ? "not current" : formatBound(trust.horizontal_bound_m)}
          note={
            noLink || trust.horizontal_bound_m === null
              ? undefined
              : `${formatPercent(trust.confidence)} of reports`
          }
          title={calibration && !noLink ? calibrationText(calibration) : undefined}
          first
        />
        <Metric label="In state" value={inState} />
        <Metric
          label="Sectors"
          value={sectors.length ? sectors.map((s) => (doneSectors.includes(s.id) ? `${s.id} ✓` : s.id)).join(" ") : "none"}
          title={doneSectors.length ? "A check mark means the sector has been flown" : undefined}
        />
      </dl>

      <div className="mt-2">
        {noLink ? (
          <p className="text-xs text-faint">Margin to alert: not current, no link.</p>
        ) : (
          <Headroom trust={trust} />
        )}
      </div>

      <div className="mt-2">
        <TrustStrip history={history} now={now} />
      </div>
    </button>
  );
}

function Metric({
  label,
  value,
  note,
  title,
  first = false,
}: {
  label: string;
  value: string;
  note?: string | undefined;
  title?: string | undefined;
  first?: boolean;
}) {
  return (
    <div className={clsx("py-1.5", first ? "pr-3" : "px-3")} title={title}>
      <dt className="label">{label}</dt>
      <dd className="mt-0.5 truncate font-mono text-[13px] text-text">{value}</dd>
      {note && <dd className="truncate text-[11px] text-faint">{note}</dd>}
    </div>
  );
}

const HEADROOM_STYLE = {
  ample: { bar: "#52c28a", text: "text-ok", word: "Comfortable" },
  shrinking: { bar: "#e3b341", text: "text-warn", word: "Shrinking" },
  low: { bar: "#f06262", text: "text-bad", word: "Close to an alert" },
} as const;

/** How far a GREEN vehicle is from being flagged. Outside GREEN there is nothing left to measure. */
function Headroom({ trust }: { trust: NavTrust }) {
  if (trust.state !== "GREEN") {
    return (
      <p className="text-xs text-faint">
        Margin to alert: none, already flagged.
        {trust.state === "AMBER" && " No action is recommended unless it turns RED."}
      </p>
    );
  }
  const level = headroomLevel(trust.headroom);
  const style = HEADROOM_STYLE[level];
  return (
    <div title="How far this vehicle is from being flagged: the worst recent sensor-consistency ratio against the estimator's own limit, and how long its data has been quiet. It is not a probability.">
      <div className="flex items-center justify-between text-xs">
        <span className="text-faint">Margin to alert</span>
        <span className={clsx("font-medium", style.text)}>
          {style.word} ({formatPercent(trust.headroom)})
        </span>
      </div>
      <div
        className="mt-1.5 h-1 bg-line-soft"
        role="meter"
        aria-label="Margin to alert"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(trust.headroom * 100)}
      >
        <div className="h-full transition-[width] duration-500" style={{ width: `${trust.headroom * 100}%`, background: style.bar }} />
      </div>
    </div>
  );
}
