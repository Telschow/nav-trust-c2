import clsx from "clsx";
import { ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { STATE_LABEL } from "../language";
import { TONE } from "../tone";
import type { TrustState } from "../types";

const ICON = { GREEN: ShieldCheck, AMBER: ShieldAlert, RED: ShieldX } as const;

/** Colour, icon and words together, so the state never depends on colour alone. */
export function StateChip({ state, large = false }: { state: TrustState; large?: boolean }) {
  const Icon = ICON[state];
  const tone = TONE[state];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full font-semibold ring-1",
        tone.bg,
        tone.text,
        tone.ring,
        large ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs",
      )}
    >
      <Icon className={large ? "size-4" : "size-3.5"} aria-hidden />
      <span>{STATE_LABEL[state]}</span>
      <span className="sr-only"> ({state})</span>
    </span>
  );
}
