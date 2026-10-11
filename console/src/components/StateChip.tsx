import clsx from "clsx";
import { Circle, Square, Triangle } from "lucide-react";
import { STATE_LABEL } from "../language";
import { TONE } from "../tone";
import type { TrustState } from "../types";

// a different shape per state, so the state never depends on colour alone
const ICON = { GREEN: Circle, AMBER: Triangle, RED: Square } as const;

/** Shape, colour and words together. */
export function StateChip({ state, large = false }: { state: TrustState; large?: boolean }) {
  const Icon = ICON[state];
  const tone = TONE[state];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-[2px] border font-medium",
        tone.text,
        state === "GREEN" ? "border-ok/40" : state === "AMBER" ? "border-warn/55" : "border-bad/65 bg-bad/12",
        large ? "px-2.5 py-1 text-sm" : "px-2 py-0.5 text-xs",
      )}
    >
      <Icon className={large ? "size-3.5" : "size-3"} fill="currentColor" aria-hidden />
      <span>{STATE_LABEL[state]}</span>
      <span className="sr-only"> ({state})</span>
    </span>
  );
}
