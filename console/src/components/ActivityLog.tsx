import clsx from "clsx";
import { formatDuration } from "../language";
import type { LogEntry } from "../store";

const DOT = { info: "bg-faint", good: "bg-ok", warn: "bg-warn", bad: "bg-bad" } as const;

export function ActivityLog({ entries }: { entries: LogEntry[] }) {
  if (entries.length === 0) {
    return <p className="px-1 text-sm text-faint">Nothing has happened yet.</p>;
  }
  return (
    <ol className="space-y-2.5" aria-live="polite">
      {entries.map((e) => (
        <li key={e.id} className="flex gap-3 text-[13px] leading-snug">
          <span className="mt-1.5 size-2 shrink-0 rounded-full">
            <span className={clsx("block size-2 rounded-full", DOT[e.tone])} />
          </span>
          <span className="flex-1 text-muted">{e.text}</span>
          <time className="shrink-0 font-mono text-[11px] text-faint">{formatDuration(e.server_s)}</time>
        </li>
      ))}
    </ol>
  );
}
