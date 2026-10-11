import { useEffect, useReducer, useState } from "react";
import { connectEvents, fetchCalibration, fetchFleet } from "./api";
import { initialState, reducer, serverNow } from "./store";
import type { ConsoleState } from "./store";

const seconds = () => performance.now() / 1000;

export function useConsole() {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(
    () =>
      connectEvents(
        (event) => dispatch({ type: "server", event, clientNow: seconds() }),
        (connected) => dispatch({ type: "connection", connected }),
      ),
    [],
  );

  useEffect(() => {
    fetchCalibration()
      .then((calibration) => dispatch({ type: "calibration", calibration }))
      .catch(() => undefined); // the bound is still shown; only its explanation is missing
  }, []);

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
  }, []);

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
