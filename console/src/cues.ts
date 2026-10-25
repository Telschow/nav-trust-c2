import type { Action, ConsoleState } from "./store";

/** A sound the console can make. Every one has an on-screen equivalent, so nothing depends on
 * sound alone: the decision band and the no-link badge. */
export type Cue = "decision-required" | "link-lost";

/** The only thing that makes sound, behind an interface so tests never need audio. */
export interface CuePlayer {
  play(cue: Cue): void;
}

/** Which sounds a change deserves, from the state before and after one action. Only a live event
 * can sound: a fresh snapshot is what was already there, and marking a decision seen is quiet. */
export function cuesFor(prev: ConsoleState, action: Action, next: ConsoleState): Cue[] {
  if (action.type !== "server") return [];
  const { event } = action;
  if (event.type === "recommendation") {
    const isNew = !(event.data.id in prev.recommendations);
    return isNew && !next.decisions[event.data.id] ? ["decision-required"] : [];
  }
  if (event.type === "link") {
    const before = prev.links[event.data.vehicle_id]?.state;
    return before !== undefined && before !== "NO_LINK" && event.data.state === "NO_LINK" ? ["link-lost"] : [];
  }
  return [];
}

/** Play cues, but only while the operator has turned sound on. */
export function announce(cues: Cue[], enabled: boolean, player: CuePlayer): void {
  if (!enabled) return;
  for (const cue of cues) player.play(cue);
}

/** Tones made in the browser, so there are no audio files. Decision required: two rising beeps.
 * Link lost: one long falling tone. They differ in shape as well as pitch. */
const NOTES: Record<Cue, { freq: number; at: number; length: number }[]> = {
  "decision-required": [
    { freq: 880, at: 0, length: 0.14 },
    { freq: 1175, at: 0.2, length: 0.2 },
  ],
  "link-lost": [
    { freq: 392, at: 0, length: 0.22 },
    { freq: 294, at: 0.24, length: 0.4 },
  ],
};

export function webAudioPlayer(): CuePlayer {
  let ctx: AudioContext | null = null;
  return {
    play(cue) {
      try {
        ctx ??= new AudioContext();
        void ctx.resume();
        const t0 = ctx.currentTime;
        for (const n of NOTES[cue]) {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.value = n.freq;
          gain.gain.setValueAtTime(0.0001, t0 + n.at);
          gain.gain.exponentialRampToValueAtTime(0.2, t0 + n.at + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, t0 + n.at + n.length);
          osc.connect(gain).connect(ctx.destination);
          osc.start(t0 + n.at);
          osc.stop(t0 + n.at + n.length + 0.05);
        }
      } catch {
        /* no audio in this browser: the screen still shows everything */
      }
    },
  };
}

const SOUND_KEY = "nav-trust-sound";

/** Sound starts off: browsers refuse automatic audio, and the operator's click is the permission.
 * The choice is remembered in this browser only; with no storage it lasts for the session. */
export function loadSoundChoice(storage: Pick<Storage, "getItem"> | undefined = safeStorage()): boolean {
  try {
    return storage?.getItem(SOUND_KEY) === "on";
  } catch {
    return false;
  }
}

export function saveSoundChoice(on: boolean, storage: Pick<Storage, "setItem"> | undefined = safeStorage()): void {
  try {
    storage?.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    /* private mode: the choice lasts for this session only */
  }
}

function safeStorage(): Storage | undefined {
  try {
    return localStorage;
  } catch {
    return undefined;
  }
}
