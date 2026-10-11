import { CheckCircle2, ListChecks, Satellite, WifiOff } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { DecisionError, postDecision } from "./api";
import { ActivityLog } from "./components/ActivityLog";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { Header } from "./components/Header";
import { MapView } from "./components/MapView";
import { DecidedRow, RecommendationCard } from "./components/RecommendationCard";
import { VehicleCard } from "./components/VehicleCard";
import { useConsole, useServerNow } from "./hooks";
import { decidedRecommendations, openRecommendations } from "./store";
import type { Recommendation, TrustState } from "./types";

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
  const { state, dispatch } = useConsole();
  const now = useServerNow(state);
  const [operator, setOperator] = useState(storedOperator);
  const [confirming, setConfirming] = useState<Recommendation | null>(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [focus, setFocus] = useState<{ vehicleId: string; n: number } | null>(null);

  const open = openRecommendations(state);
  const decided = decidedRecommendations(state).slice(0, 4);
  const vehicleIds = Object.keys(state.vehicles).sort();
  const demo = state.source !== "live";

  const counts = useMemo(() => {
    const c: Record<TrustState, number> = { GREEN: 0, AMBER: 0, RED: 0 };
    for (const t of Object.values(state.vehicles)) c[t.state] += 1;
    return c;
  }, [state.vehicles]);

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

  return (
    <div className="flex h-full flex-col bg-[radial-gradient(1200px_600px_at_70%_-10%,#13203d,transparent)]">
      <Header connected={state.connected} source={state.source} counts={counts} now={now} />

      {!state.connected && (
        <div role="alert" className="mx-5 mb-2 flex items-center gap-2 rounded-lg border border-bad/40 bg-bad/10 px-4 py-2 text-sm text-bad">
          <WifiOff className="size-4" aria-hidden /> Connection to the backend was lost. Showing the last known state and retrying...
        </div>
      )}

      <main className="grid min-h-0 flex-1 gap-4 px-5 pb-5 xl:grid-cols-[360px_minmax(0,1fr)_400px]">
        {/* fleet */}
        <section className="flex min-h-0 flex-col gap-3 overflow-y-auto" aria-label="Fleet">
          <div className="label flex items-center gap-2 px-1">
            <Satellite className="size-3.5" aria-hidden /> Fleet
          </div>
          {vehicleIds.length === 0 && (
            <div className="panel p-5 text-sm text-muted">Waiting for vehicles to report their navigation trust...</div>
          )}
          {vehicleIds.map((id) => (
            <VehicleCard
              key={id}
              vehicleId={id}
              trust={state.vehicles[id]!}
              since={state.stateSince[id]}
              now={now}
              sectors={state.fleet[id] ?? []}
              doneSectors={state.doneSectors}
              history={state.history[id] ?? []}
              calibration={state.calibration}
              onFocus={() => setFocus((f) => ({ vehicleId: id, n: (f?.n ?? 0) + 1 }))}
            />
          ))}
        </section>

        {/* map */}
        <section className="min-h-[420px]" aria-label="Map">
          <MapView state={state} focus={focus} />
        </section>

        {/* decisions */}
        <section className="flex min-h-0 flex-col gap-3 overflow-y-auto" aria-label="Decisions">
          <div className="label flex items-center gap-2 px-1">
            <ListChecks className="size-3.5" aria-hidden /> Decisions
            {open.length > 0 && (
              <span className="rounded-full bg-bad px-1.5 py-px text-[10px] font-bold text-[#1a0606]">{open.length}</span>
            )}
          </div>

          {open.length === 0 && (
            <div className="panel flex items-center gap-3 p-4 text-sm text-muted">
              <CheckCircle2 className="size-5 shrink-0 text-ok" aria-hidden />
              No action needs your decision.
            </div>
          )}
          <div aria-live="polite" className="flex flex-col gap-3">
            {open.map((rec) => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                now={now}
                disabled={busy}
                onApprove={() => setConfirming(rec)}
                onDeny={() => void decide(rec, "DENIED")}
              />
            ))}
          </div>

          {decided.length > 0 && (
            <>
              <div className="label mt-2 px-1">Recently decided</div>
              <ul className="space-y-2">
                {decided.map(({ rec, decision }) => (
                  <DecidedRow key={rec.id} rec={rec} decision={decision} />
                ))}
              </ul>
            </>
          )}

          <div className="label mt-2 px-1">Activity</div>
          <div className="panel p-4">
            <ActivityLog entries={state.log} />
          </div>
        </section>
      </main>

      {confirming && (
        <ConfirmDialog
          rec={confirming}
          operator={operator}
          demo={demo}
          busy={busy}
          onOperatorChange={changeOperator}
          onCancel={() => setConfirming(null)}
          onConfirm={() => void decide(confirming, "APPROVED")}
        />
      )}

      {toast && (
        <div
          role="status"
          className={`fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-xl border px-5 py-3 text-sm shadow-xl shadow-black/50 ${
            toast.tone === "good" ? "border-ok/40 bg-[#0c2a22] text-ok" : "border-bad/40 bg-[#2a1010] text-bad"
          }`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
