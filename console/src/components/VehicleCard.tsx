import clsx from "clsx";
import { Clock, Crosshair, Layers } from "lucide-react";
import {
  calibrationText,
  formatBound,
  formatDuration,
  formatPercent,
  headroomLevel,
  reasonText,
} from "../language";
import type { HistoryPoint } from "../store";
import { TONE, vehicleColor } from "../tone";
import type { Calibration, NavTrust, Sector } from "../types";
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
  onFocus: () => void;
}

export function VehicleCard({
  vehicleId,
  trust,
  since,
  now,
  sectors,
  doneSectors,
  history,
  calibration,
  onFocus,
}: Props) {
  const tone = TONE[trust.state];
  const inState = since !== undefined && now !== null ? formatDuration(now - since) : "-";
  return (
    <button
      type="button"
      onClick={onFocus}
      className={clsx(
        "panel group relative w-full overflow-hidden p-4 text-left transition",
        "hover:border-[#2c3b61] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
      )}
      aria-label={`${vehicleId}, ${trust.state}. Show on map`}
    >
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: tone.hex }} aria-hidden />
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className="size-3 rounded-full ring-2 ring-white/10"
            style={{ background: vehicleColor(vehicleId) }}
            aria-hidden
          />
          <span className="text-base font-semibold tracking-tight">{vehicleId}</span>
        </div>
        <StateChip state={trust.state} />
      </div>

      <p className={clsx("mt-3 text-sm leading-snug", trust.state === "GREEN" ? "text-muted" : "text-text")}>
        {reasonText(trust.reason)}
      </p>

      <dl className="mt-3.5 grid grid-cols-3 gap-2 text-xs">
        <Metric
          icon={<Crosshair className="size-3" />}
          label="Position error"
          value={formatBound(trust.horizontal_bound_m)}
          note={trust.horizontal_bound_m === null ? undefined : `${formatPercent(trust.confidence)} of reports`}
          title={calibration ? calibrationText(calibration) : undefined}
        />
        <Metric icon={<Clock className="size-3" />} label="In state" value={inState} />
        <Metric
          icon={<Layers className="size-3" />}
          label="Sectors"
          value={sectors.length ? sectors.map((s) => (doneSectors.includes(s.id) ? `${s.id} ✓` : s.id)).join(" ") : "none"}
          title={doneSectors.length ? "A check mark means the sector has been flown" : undefined}
        />
      </dl>

      <div className="mt-3.5">
        <Headroom trust={trust} />
      </div>

      <div className="mt-3.5">
        <TrustStrip history={history} now={now} />
      </div>
    </button>
  );
}

function Metric({
  icon,
  label,
  value,
  note,
  title,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  note?: string | undefined;
  title?: string | undefined;
}) {
  return (
    <div className="rounded-lg bg-black/20 px-2.5 py-2" title={title}>
      <dt className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-faint">
        {icon}
        {label}
      </dt>
      <dd className="mt-1 truncate font-mono text-[13px] text-text">{value}</dd>
      {note && <dd className="truncate text-[10px] text-faint">{note}</dd>}
    </div>
  );
}

const HEADROOM_STYLE = {
  ample: { bar: "#34d399", text: "text-ok", word: "Comfortable" },
  shrinking: { bar: "#fbbf24", text: "text-warn", word: "Shrinking" },
  low: { bar: "#f87171", text: "text-bad", word: "Close to an alert" },
} as const;

/** How far a GREEN vehicle is from being flagged. Outside GREEN there is nothing left to measure. */
function Headroom({ trust }: { trust: NavTrust }) {
  if (trust.state !== "GREEN") {
    return <p className="text-xs text-faint">Margin to alert: none, already flagged</p>;
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
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/8"
        role="meter"
        aria-label="Margin to alert"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(trust.headroom * 100)}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${trust.headroom * 100}%`, background: style.bar }}
        />
      </div>
    </div>
  );
}
