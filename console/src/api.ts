import { ERROR_TEXT } from "./language";
import type { Calibration, Decision, Fleet, Outcome, ServerEvent } from "./types";

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws`;
}

/** Connects, and reconnects with a growing delay (1 s up to 10 s) until stopped. */
export function connectEvents(
  onEvent: (e: ServerEvent) => void,
  onConnection: (connected: boolean) => void,
): () => void {
  let socket: WebSocket | null = null;
  let timer: number | undefined;
  let delay = 1000;
  let stopped = false;

  const open = () => {
    socket = new WebSocket(wsUrl());
    socket.onopen = () => {
      delay = 1000;
      onConnection(true);
    };
    socket.onmessage = (m) => {
      try {
        onEvent(JSON.parse(m.data as string) as ServerEvent);
      } catch {
        /* ignore a malformed message rather than crash the console */
      }
    };
    socket.onclose = () => {
      onConnection(false);
      if (!stopped) {
        timer = window.setTimeout(open, delay);
        delay = Math.min(delay * 2, 10000);
      }
    };
    socket.onerror = () => socket?.close();
  };
  open();
  return () => {
    stopped = true;
    window.clearTimeout(timer);
    socket?.close();
  };
}

export async function fetchFleet(): Promise<{ fleet: Fleet; done: string[] }> {
  const r = await fetch("/fleet");
  if (!r.ok) throw new Error(`fleet ${r.status}`);
  const body = (await r.json()) as { assignment: Fleet; done?: string[] };
  return { fleet: body.assignment, done: body.done ?? [] };
}

export class DecisionError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function postDecision(
  recommendationId: string,
  outcome: Exclude<Outcome, "EXPIRED">,
  operator: string,
): Promise<Decision> {
  const r = await fetch("/decisions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recommendation_id: recommendationId, outcome, operator }),
  });
  if (!r.ok) throw new DecisionError(r.status, ERROR_TEXT[r.status] ?? `Request failed (${r.status}).`);
  return (await r.json()) as Decision;
}

export async function fetchCalibration(): Promise<Calibration> {
  const r = await fetch("/calibration");
  if (!r.ok) throw new Error(`calibration ${r.status}`);
  return (await r.json()) as Calibration;
}
