import type { HistoryPoint } from "../store";
import { TONE } from "../tone";

const BUCKETS = 48;
const WINDOW_S = 120;

/** The last two minutes of a vehicle's trust state as a row of small blocks. */
export function TrustStrip({ history, now }: { history: HistoryPoint[]; now: number | null }) {
  const end = now ?? history[history.length - 1]?.server_s ?? 0;
  const start = end - WINDOW_S;
  const cells: (keyof typeof TONE | null)[] = Array.from({ length: BUCKETS }, () => null);
  for (const p of history) {
    if (p.server_s < start || p.server_s > end) continue;
    const i = Math.min(BUCKETS - 1, Math.floor(((p.server_s - start) / WINDOW_S) * BUCKETS));
    const worse = cells[i];
    // keep the worst state seen in a bucket so a short dip is never hidden
    const rank = { GREEN: 0, AMBER: 1, RED: 2 } as const;
    cells[i] = worse === null || rank[p.state] > rank[worse] ? p.state : worse;
  }
  // carry the last known state forward across empty buckets after the first sample
  let last: keyof typeof TONE | null = null;
  const filled = cells.map((c) => {
    if (c !== null) last = c;
    return c ?? last;
  });
  return (
    <div>
      <div className="flex h-2 gap-[2px]" role="img" aria-label="Trust state over the last two minutes">
        {filled.map((c, i) => (
          <span
            key={i}
            className="h-full flex-1 rounded-[2px]"
            style={{ background: c ? TONE[c].hex : "#1b2540", opacity: c ? 0.9 : 1 }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-faint">
        <span>2 min ago</span>
        <span>now</span>
      </div>
    </div>
  );
}
