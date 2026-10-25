import clsx from "clsx";
import { Unlink, Volume2, VolumeX, WifiOff } from "lucide-react";
import { formatDuration } from "../language";
import { TONE } from "../tone";
import type { FleetCounts } from "../store";

interface Props {
  connected: boolean;
  source: string;
  counts: FleetCounts;
  now: number | null;
  /** whether tones are on, and the control to change it; always shown, so it never has to be guessed */
  soundOn?: boolean;
  onToggleSound?: () => void;
}

export function Header({ connected, source, counts, now, soundOn = false, onToggleSound }: Props) {
  const live = source === "live";
  const total = counts.GREEN + counts.AMBER + counts.RED + counts.noLink;
  return (
    <header className="flex h-11 shrink-0 items-center justify-between gap-4 border-b border-line bg-panel px-4">
      <div className="flex items-baseline gap-3">
        <div className="text-[14px] font-semibold tracking-[0.01em]">Navigation Trust</div>
        <div className="hidden text-[12px] text-faint md:block">Human-on-the-loop fleet console</div>
      </div>

      <div className="flex items-center gap-4">
        {total > 0 && (
          <div className="hidden items-center gap-4 text-xs text-muted md:flex" aria-label="Fleet summary">
            <span>{total} vehicles</span>
            {(["GREEN", "AMBER", "RED"] as const).map(
              (s) =>
                counts[s] > 0 && (
                  <span key={s} className="flex items-center gap-1.5">
                    <span className="size-2 rounded-[1px]" style={{ background: TONE[s].hex }} aria-hidden />
                    {counts[s]} {s === "GREEN" ? "trusted" : s === "AMBER" ? "degraded" : "not trusted"}
                  </span>
                ),
            )}
            {counts.noLink > 0 && (
              <span className="flex items-center gap-1.5 text-accent">
                <Unlink className="size-3" aria-hidden />
                {counts.noLink} no link
              </span>
            )}
          </div>
        )}
        {onToggleSound && (
          <button
            type="button"
            onClick={onToggleSound}
            aria-pressed={soundOn}
            title={soundOn ? "Tones announce decisions and lost links. Click to turn off." : "Click to turn on tones for decisions and lost links."}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-[2px] border px-2 py-0.5 text-[11px] font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              soundOn ? "border-line text-text" : "border-warn/60 text-warn",
            )}
          >
            {soundOn ? <Volume2 className="size-3" aria-hidden /> : <VolumeX className="size-3" aria-hidden />}
            {soundOn ? "Sound on" : "Sound off"}
          </button>
        )}
        <span
          title={live ? "Live data" : "Recorded trust data replayed with synthetic positions. Not a live flight."}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-[2px] border px-2 py-0.5 font-mono text-[11px] font-medium",
            !connected ? "border-bad/60 text-bad" : live ? "border-ok/50 text-ok" : "border-warn/60 text-warn",
          )}
        >
          {!connected && <WifiOff className="size-3" aria-hidden />}
          {!connected ? "DISCONNECTED" : live ? "LIVE" : source}
        </span>
        <span className="w-[74px] text-right font-mono text-xs text-faint" title="Time since the backend started">
          {now === null ? "T+--:--" : `T+${formatDuration(now)}`}
        </span>
      </div>
    </header>
  );
}
