import clsx from "clsx";
import { Radio, WifiOff } from "lucide-react";
import { formatDuration } from "../language";
import { TONE } from "../tone";
import type { TrustState } from "../types";

interface Props {
  connected: boolean;
  source: string;
  counts: Record<TrustState, number>;
  now: number | null;
}

export function Header({ connected, source, counts, now }: Props) {
  const live = source === "live";
  const total = counts.GREEN + counts.AMBER + counts.RED;
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 px-5">
      <div className="flex items-center gap-3">
        <Logo />
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">Navigation Trust</div>
          <div className="text-[11px] text-faint">Human-on-the-loop fleet console</div>
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        {total > 0 && (
          <div className="mr-1 hidden items-center gap-3 text-xs text-muted md:flex" aria-label="Fleet summary">
            <span>{total} vehicles</span>
            {(["GREEN", "AMBER", "RED"] as const).map(
              (s) =>
                counts[s] > 0 && (
                  <span key={s} className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full" style={{ background: TONE[s].hex }} aria-hidden />
                    {counts[s]} {s === "GREEN" ? "trusted" : s === "AMBER" ? "degraded" : "not trusted"}
                  </span>
                ),
            )}
          </div>
        )}
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1",
            !connected
              ? "bg-bad/14 text-bad ring-bad/40"
              : live
                ? "bg-ok/12 text-ok ring-ok/35"
                : "bg-warn/12 text-warn ring-warn/40",
          )}
        >
          {connected ? <Radio className="size-3.5" aria-hidden /> : <WifiOff className="size-3.5" aria-hidden />}
          {!connected ? "DISCONNECTED" : live ? "LIVE" : source}
        </span>
        <span className="w-20 text-right font-mono text-xs text-faint" title="Time since the backend started">
          {now === null ? "T+--:--" : `T+${formatDuration(now)}`}
        </span>
      </div>
    </header>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
      <defs>
        <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#6ea8ff" />
          <stop offset="1" stopColor="#34d399" />
        </linearGradient>
      </defs>
      <path d="M16 2.5 28 7v8.5c0 7-5 12.2-12 14-7-1.8-12-7-12-14V7z" fill="none" stroke="url(#g)" strokeWidth="2" />
      <circle cx="16" cy="15" r="4.2" fill="none" stroke="url(#g)" strokeWidth="2" />
      <path d="M16 6.5v4M16 19.5v4M7.5 15h4M20.5 15h4" stroke="url(#g)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
