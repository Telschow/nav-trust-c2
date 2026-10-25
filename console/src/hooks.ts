import { useCallback, useEffect, useRef, useState } from "react";
import { connectEvents, fetchCalibration, fetchFleet } from "./api";
import type { Cue } from "./cues";
import { cuesFor } from "./cues";
import { initialState, reducer, serverNow } from "./store";
import type { Action, ConsoleState } from "./store";

const seconds = () => performance.now() / 1000;

/** onCues: told which sounds each change deserves, computed from the state before and after it. */
export function useConsole(onCues: (cues: Cue[]) => void = () => undefined) {
  const [state, setState] = useState(initialState);
  const current = useRef(initialState);
  const cues = useRef(onCues);
  cues.current = onCues;
  const dispatch = useCallback((action: Action) => {
    const prev = current.current;
    const next = reducer(prev, action);
    current.current = next;
    setState(next);
    const sounds = cuesFor(prev, action, next);
    if (sounds.length > 0) cues.current(sounds);
  }, []);

  useEffect(
    () =>
      connectEvents(
        (event) => dispatch({ type: "server", event, clientNow: seconds() }),
        (connected) => dispatch({ type: "connection", connected }),
      ),
    [dispatch],
  );

  useEffect(() => {
    fetchCalibration()
      .then((calibration) => dispatch({ type: "calibration", calibration }))
      .catch(() => undefined); // the bound is still shown; only its explanation is missing
  }, [dispatch]);

  // The sector assignment changes only when an approved re-task runs and sectors are finished
  // slowly (minutes), so polling is enough.
  useEffect(() => {
    let alive = true;
    const poll = () =>
      fetchFleet()
        .then(({ fleet, done }) => alive && dispatch({ type: "fleet", fleet, done }))
        .catch(() => undefined);
    poll();
    const id = window.setInterval(poll, 2000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [dispatch]);

  return { state, dispatch };
}

/** The backend clock, advancing smoothly between messages. null until the first message. */
export function useServerNow(state: ConsoleState): number | null {
  const [tick, setTick] = useState(seconds());
  useEffect(() => {
    const id = window.setInterval(() => setTick(seconds()), 500);
    return () => window.clearInterval(id);
  }, []);
  return serverNow(state, tick);
}
