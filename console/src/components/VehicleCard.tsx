import clsx from "clsx";
import { Clock, Crosshair, Layers } from "lucide-react";
import { formatBound, formatDuration, reasonText } from "../language";
import type { HistoryPoint } from "../store";
import { TONE, vehicleColor } from "../tone";
import type { NavTrust, Sector } from "../types";
import { StateChip } from "./StateChip";
import { TrustStrip } from "./TrustStrip";

interface Props {
  vehicleId: string;
  trust: NavTrust;
  since: number | undefined;
  now: number | null;
  sectors: Sector[];
  history: HistoryPoint[];
  onFocus: () => void;
}

export function VehicleCard({ vehicleId, trust, since, now, sectors, history, onFocus }: Props) {
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
        <Metric icon={<Crosshair className="size-3" />} label="Bound" value={formatBound(trust.horizontal_bound_m)} />
        <Metric icon={<Clock className="size-3" />} label="In state" value={inState} />
        <Metric
          icon={<Layers className="size-3" />}
          label="Sectors"
          value={sectors.length ? sectors.map((s) => s.id).join(" ") : "none"}
        />
      </dl>

      <div className="mt-3.5">
        <TrustStrip history={history} now={now} />
      </div>
    </button>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-lg bg-black/20 px-2.5 py-2">
      <dt className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-faint">
        {icon}
        {label}
      </dt>
      <dd className="mt-1 truncate font-mono text-[13px] text-text">{value}</dd>
    </div>
  );
}
