import clsx from "clsx";
import { formatDuration } from "../language";
import type { LogEntry } from "../store";

const MARK = { info: "text-faint", good: "text-ok", warn: "text-warn", bad: "text-bad" } as const;

export function ActivityLog({ entries }: { entries: LogEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-faint">Nothing has happened yet.</p>;
  }
  return (
    <ol className="divide-y divide-line-soft" aria-live="polite">
      {entries.map((e) => (
        <li key={e.id} className="flex gap-3 py-2 text-[13px] leading-snug first:pt-0 last:pb-0">
          <time className="w-10 shrink-0 font-mono text-[11px] leading-[18px] text-faint">{formatDuration(e.server_s)}</time>
          <span className={clsx("mt-[7px] size-1.5 shrink-0 rounded-[1px] bg-current", MARK[e.tone])} aria-hidden />
          <span className="flex-1 text-muted">{e.text}</span>
        </li>
      ))}
    </ol>
  );
}
