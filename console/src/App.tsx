import { WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DecisionError, postDecision } from "./api";
import { ActivityLog } from "./components/ActivityLog";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { DecisionBanner } from "./components/DecisionBanner";
import { Header } from "./components/Header";
import { MapView } from "./components/MapView";
import { DecidedRow, ExpiredNotice, RecommendationCard } from "./components/RecommendationCard";
import { VehicleRow } from "./components/VehicleRow";
import { announce, loadSoundChoice, saveSoundChoice, webAudioPlayer } from "./cues";
import { useConsole, useServerNow } from "./hooks";
import { decidedHistory, expiredWithoutLink, isNoLink, isSeen, openRecommendations, pinnedExpired, raisedAgain, trustCounts } from "./store";
import type { Recommendation } from "./types";

const OPERATOR_KEY = "nav-trust-operator";

function storedOperator(): string {
  try {
    return localStorage.getItem(OPERATOR_KEY) ?? "operator";
  } catch {
    return "operator";
  }
}

interface Toast {
  tone: "good" | "bad";
  text: string;
}

export function App() {
  const [soundOn, setSoundOn] = useState(loadSoundChoice);
  const soundRef = useRef(soundOn);
  soundRef.current = soundOn;
  const player = useMemo(webAudioPlayer, []);
  const { state, dispatch } = useConsole((cues) => announce(cues, soundRef.current, player));
  const now = useServerNow(state);
  const [operator, setOperator] = useState(storedOperator);
  const [confirming, setConfirming] = useState<Recommendation | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [focus, setFocus] = useState<{ vehicleId: string; n: number } | null>(null);

  const open = openRecommendations(state);
  const decided = decidedHistory(state).slice(0, 4);
  const vehicleIds = Object.keys(state.vehicles).sort();
  const demo = state.source !== "live";

  const counts = useMemo(() => trustCounts(state), [state]);

  const toggleSound = () => {
    const on = !soundOn;
    setSoundOn(on);
    saveSoundChoice(on);
    // the click is the browser's permission for audio: confirm with the decision tone
    if (on) player.play("decision-required");
  };

  const changeOperator = (name: string) => {
    setOperator(name);
    try {
      localStorage.setItem(OPERATOR_KEY, name);
    } catch {
      /* private mode: keep it in memory only */
    }
  };

  const decide = useCallback(
    async (rec: Recommendation, outcome: "APPROVED" | "DENIED") => {
      setBusy(true);
      try {
        const decision = await postDecision(rec.id, outcome, operator.trim() || "operator");
        dispatch({ type: "decided", decision });
        setConfirming(null);
        const failed = decision.execution && !decision.execution.executed;
        setToast(
          outcome === "DENIED"
            ? { tone: "good", text: "Denied. Nothing was sent to any vehicle." }
            : failed
              ? { tone: "bad", text: `Approved, but not executed: ${decision.execution?.reason ?? "unknown"}` }
              : { tone: "good", text: "Approved and recorded." },
        );
      } catch (e) {
        setConfirming(null);
        setToast({ tone: "bad", text: e instanceof DecisionError ? e.message : "Could not reach the backend." });
      } finally {
        setBusy(false);
        window.setTimeout(() => setToast(null), 6000);
      }
    },
    [dispatch, operator],
  );

  // a decision waiting is visible in the tab title too, for when the console is behind another window
  useEffect(() => {
    document.title = open.length > 0 ? `(${open.length}) Decision required | Navigation Trust` : "Navigation Trust";
  }, [open.length]);

  const review = () => {
    const first = open[0];
    if (!first) return;
    const card = document.getElementById(`rec-${first.id}`);
    card?.scrollIntoView({ block: "nearest" });
    card?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
  };

  return (
    <div className="flex h-full flex-col">
      <a href="#decisions" className="skip-link">
        Skip to decisions
      </a>
      <Header connected={state.connected} source={state.source} counts={counts} now={now} soundOn={soundOn} onToggleSound={toggleSound} />
      <DecisionBanner open={open} now={now} raisedAgain={open[0] ? raisedAgain(state, open[0]) : null} seen={open[0] ? isSeen(state, open[0].id) : false} onReview={review} />

      {!state.connected && (
        <div role="alert" className="flex items-center gap-2 border-b border-bad/50 bg-bad/10 px-4 py-2 text-sm text-bad">
          <WifiOff className="size-4" aria-hidden /> Connection to the backend was lost. Showing the last known state and retrying...
        </div>
      )}

      <main className="grid min-h-0 flex-1 xl:grid-cols-[380px_minmax(0,1fr)_400px]">
        {/* fleet */}
        <section className="flex min-h-0 flex-col overflow-y-auto border-r border-line bg-panel" aria-label="Fleet">
          <h2 className="label sticky top-0 z-10 flex items-baseline justify-between border-b border-line bg-panel px-4 py-2.5">
            Fleet
            <span className="font-mono text-[11px] font-normal text-faint">strips show the last 2 min</span>
          </h2>
          {vehicleIds.length === 0 && (
            <div className="px-4 py-5 text-sm text-muted">Waiting for vehicles to report their navigation trust...</div>
          )}
          {vehicleIds.map((id) => (
            <VehicleRow
              key={id}
              vehicleId={id}
              trust={state.vehicles[id]!}
              since={state.stateSince[id]}
              now={now}
              sectors={state.fleet[id] ?? []}
              doneSectors={state.doneSectors}
              history={state.history[id] ?? []}
              calibration={state.calibration}
              link={state.links[id]}
              onFocus={() => setFocus((f) => ({ vehicleId: id, n: (f?.n ?? 0) + 1 }))}
            />
          ))}
        </section>

        {/* map */}
        <section className="min-h-[420px] p-3" aria-label="Map">
          <MapView state={state} now={now} focus={focus} />
        </section>

        {/* decisions */}
        <section id="decisions" tabIndex={-1} className="flex min-h-0 flex-col gap-5 overflow-y-auto border-l border-line bg-panel p-4 focus:outline-none" aria-label="Decisions">
          <div>
            <h2 className="label flex items-center gap-2">
              Decisions
              {open.length > 0 && (
                <span className="rounded-[2px] bg-bad px-1.5 py-px font-mono text-[11px] font-semibold text-[#1c0808]">{open.length}</span>
              )}
            </h2>

            {open.length === 0 && (
              <p className="mt-3 border border-line-soft px-3 py-3 text-sm text-muted">No action needs your decision.</p>
            )}
            <div aria-live="polite" className="mt-3 flex flex-col gap-3">
              {pinnedExpired(state).map(({ rec, decision }) => (
                <ExpiredNotice
                  key={`expired-${rec.id}`}
                  rec={rec}
                  decision={decision}
                  trustNow={state.vehicles[rec.vehicle_id]}
                  noLink={expiredWithoutLink(state, rec.id)}
                  onSeen={() => dispatch({ type: "seen", id: rec.id })}
                />
              ))}
              {open.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  rec={rec}
                  now={now}
                  raisedAgain={raisedAgain(state, rec)}
                  disabled={busy}
                  noLink={isNoLink(state, rec.vehicle_id)}
                  seen={isSeen(state, rec.id)}
                  onSeen={() => dispatch({ type: "seen", id: rec.id })}
                  onApprove={() => setConfirming(rec)}
                  onDeny={() => void decide(rec, "DENIED")}
                />
              ))}
            </div>
          </div>

          {decided.length > 0 && (
            <div>
              <h2 className="label">Recently decided</h2>
              <ul className="mt-2">
                {decided.map(({ rec, decision }) => (
                  <DecidedRow key={rec.id} rec={rec} decision={decision} />
                ))}
              </ul>
            </div>
          )}

          <div>
            <h2 className="label">Activity</h2>
            <div className="mt-2">
              <ActivityLog entries={state.log} />
            </div>
          </div>
        </section>
      </main>

      {confirming && (
        <ConfirmDialog
          rec={confirming}
          operator={operator}
          demo={demo}
          busy={busy}
          noLink={isNoLink(state, confirming.vehicle_id)}
          onOperatorChange={changeOperator}
          onCancel={() => setConfirming(null)}
          onConfirm={() => void decide(confirming, "APPROVED")}
        />
      )}

      {toast && (
        <div
          role="status"
          className={`fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-[3px] border px-5 py-3 text-sm ${
            toast.tone === "good" ? "border-ok/50 bg-[#10231b] text-ok" : "border-bad/50 bg-[#2a1214] text-bad"
          }`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
