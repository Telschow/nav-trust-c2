import { Unlink } from "lucide-react";

/** The backend is not hearing this vehicle. Its own icon and words, and the accent colour rather
 * than a trust colour, so it does not read as a trust state. */
export function LinkBadge() {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[2px] border border-accent/60 px-2 py-0.5 text-xs font-medium text-accent"
      title="The backend has not heard from this vehicle recently. The trust state shown is the last one known."
    >
      <Unlink className="size-3" aria-hidden />
      <span>No link</span>
    </span>
  );
}
