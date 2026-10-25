// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog, HOLD_TO_CONFIRM_MS } from "./ConfirmDialog";
import { DecisionBanner } from "./DecisionBanner";
import { ordinal, titleOf } from "../language";
import { RecommendationCard } from "./RecommendationCard";
import { Header } from "./Header";
import { ExpiredNotice } from "./RecommendationCard";
import { StateChip } from "./StateChip";
import { VehicleRow } from "./VehicleRow";
import type { Recommendation } from "../types";

afterEach(cleanup);

const rec: Recommendation = {
  id: "r1", vehicle_id: "uav2", created_s: 100, expires_s: 160, reason: "INCONSISTENT_INNOVATION",
  command: "HOLD", sector_moves: [{ sector_id: "S2", to_vehicle: "uav3" }], rationale: "x",
};

describe("RecommendationCard (C2-03: every alert shows a reason an operator can act on)", () => {
  it("states what approving will do, the reason and the time left", () => {
    render(<RecommendationCard rec={rec} now={130} disabled={false} onApprove={vi.fn()} onDeny={vi.fn()} />);
    expect(screen.getByText("Hold uav2 in place")).toBeTruthy();
    expect(screen.getByText("Move sector S2 from uav2 to uav3")).toBeTruthy();
    expect(screen.getByText(/disagrees with the vehicle's own sensors/)).toBeTruthy();
    expect(screen.getByText("Expires in 0:30")).toBeTruthy();
  });

  it("cannot be approved or denied once expired", () => {
    const approve = vi.fn();
    render(<RecommendationCard rec={rec} now={161} disabled={false} onApprove={approve} onDeny={vi.fn()} />);
    expect(screen.getByText(/Expired/)).toBeTruthy();
    const button = screen.getByRole("button", { name: /Approve/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(approve).not.toHaveBeenCalled();
  });

  it("routes the two buttons to the right handlers", () => {
    const approve = vi.fn();
    const deny = vi.fn();
    render(<RecommendationCard rec={rec} now={110} disabled={false} onApprove={approve} onDeny={deny} />);
    fireEvent.click(screen.getByRole("button", { name: /Deny/ }));
    fireEvent.click(screen.getByRole("button", { name: /Approve/ }));
    expect(deny).toHaveBeenCalledTimes(1);
    expect(approve).toHaveBeenCalledTimes(1);
  });
});

describe("ConfirmDialog", () => {
  const base = { rec, operator: "daniel", busy: false, onOperatorChange: vi.fn(), onCancel: vi.fn(), onConfirm: vi.fn() };

  it("says plainly when no command will be sent (demo) and when it will (live)", () => {
    render(<ConfirmDialog {...base} demo />);
    expect(screen.getByText(/no command is sent to any vehicle/)).toBeTruthy();
    cleanup();
    render(<ConfirmDialog {...base} demo={false} />);
    expect(screen.getByText(/commands are sent to the vehicles/)).toBeTruthy();
  });

  it("will not confirm without an operator name, and Escape cancels", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...base} demo={false} operator="  " onCancel={onCancel} />);
    expect((screen.getByRole("button", { name: "Confirm approval" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onCancel).toHaveBeenCalled();
  });

  it("keeps focus in the name field while the console re-renders", () => {
    // The console re-renders on every keystroke and every live update, with a new onCancel each
    // time. Focus used to jump back to "Confirm approval" on each render, so the next space or
    // Enter while typing a name approved the command with a half-typed name.
    const onConfirm = vi.fn();
    const { rerender } = render(<ConfirmDialog {...base} demo={false} onConfirm={onConfirm} />);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Confirm approval" }));
    const name = screen.getByRole("textbox");
    name.focus();
    rerender(<ConfirmDialog {...base} demo={false} operator="d" onCancel={vi.fn()} onConfirm={onConfirm} />);
    rerender(<ConfirmDialog {...base} demo={false} operator="du" onCancel={vi.fn()} onConfirm={onConfirm} />);
    expect(document.activeElement).toBe(name);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Escape cancels with the latest handler after a re-render", () => {
    const first = vi.fn();
    const latest = vi.fn();
    const { rerender } = render(<ConfirmDialog {...base} demo={false} onCancel={first} />);
    rerender(<ConfirmDialog {...base} demo={false} onCancel={latest} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(latest).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();
  });
});

describe("StateChip", () => {
  it("shows words as well as colour for every state", () => {
    const { container } = render(
      <>
        <StateChip state="GREEN" />
        <StateChip state="AMBER" />
        <StateChip state="RED" />
      </>,
    );
    const text = container.textContent ?? "";
    for (const w of ["Trusted", "Degraded", "Not trusted", "GREEN", "AMBER", "RED"]) expect(text).toContain(w);
  });
});

describe("VehicleRow", () => {
  const green = {
    vehicle_id: "uav1", stamp_s: 1, state: "GREEN" as const, reason: null,
    horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9,
  };
  const props = { vehicleId: "uav1", since: 0, now: 10, sectors: [], doneSectors: [], history: [], calibration: null, onFocus: vi.fn() };

  it("shows the calibrated bound with its coverage, and the margin to alert", () => {
    render(<VehicleRow {...props} trust={green} />);
    expect(screen.getByText("within 3 m")).toBeTruthy();
    expect(screen.getByText("99% of reports")).toBeTruthy();
    expect(screen.getByText(/Comfortable \(90%\)/)).toBeTruthy();
    expect((screen.getByRole("meter") as HTMLElement).getAttribute("aria-valuenow")).toBe("90");
  });

  it("warns in words when the margin is nearly gone", () => {
    render(<VehicleRow {...props} trust={{ ...green, headroom: 0.1 }} />);
    expect(screen.getByText(/Close to an alert \(10%\)/)).toBeTruthy();
  });

  it("claims no bound and no margin outside GREEN", () => {
    const red = { ...green, state: "RED" as const, reason: "STALE" as const, horizontal_bound_m: null, confidence: 0, headroom: 0 };
    render(<VehicleRow {...props} trust={red} />);
    expect(screen.getByText("unknown")).toBeTruthy();
    expect(screen.getByText(/none, already flagged/)).toBeTruthy();
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.queryByText(/of reports/)).toBeNull();
  });
});

describe("VehicleRow sectors", () => {
  const green = {
    vehicle_id: "uav1", stamp_s: 1, state: "GREEN" as const, reason: null,
    horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9,
  };
  const sector = (id: string) => ({ id, west: 0, south: 0, east: 1, north: 1 });
  const base = { vehicleId: "uav1", since: 0, now: 10, history: [], calibration: null, onFocus: vi.fn(), trust: green };

  it("marks a flown sector with a check and leaves the others plain", () => {
    render(<VehicleRow {...base} sectors={[sector("S1"), sector("S2")]} doneSectors={["S1"]} />);
    expect(screen.getByText("S1 ✓ S2")).toBeTruthy();
  });
});

describe("DecisionBanner (a waiting decision must not be missable)", () => {
  it("renders nothing when no decision waits", () => {
    const { container } = render(<DecisionBanner open={[]} now={10} onReview={vi.fn()} />);
    expect(container.textContent).toBe("");
  });

  it("names the most urgent decision, the time left and how many more wait", () => {
    const onReview = vi.fn();
    render(<DecisionBanner open={[rec, { ...rec, id: "r2" }]} now={130} onReview={onReview} />);
    expect(screen.getByRole("alert").textContent).toContain("Decision required");
    expect(screen.getByRole("alert").textContent).toContain(titleOf(rec));
    expect(screen.getByText(/1 more waiting/)).toBeTruthy();
    expect(screen.getByText("expires in 0:30")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(onReview).toHaveBeenCalledTimes(1);
  });
});

describe("VehicleRow AMBER", () => {
  it("says that no action is expected unless it turns RED", () => {
    const amber = {
      vehicle_id: "uav1", stamp_s: 1, state: "AMBER" as const, reason: "GNSS_LOSS" as const,
      horizontal_bound_m: null, confidence: 0, headroom: 0,
    };
    render(<VehicleRow vehicleId="uav1" trust={amber} since={0} now={5} sectors={[]} doneSectors={[]} history={[]} calibration={null} onFocus={vi.fn()} />);
    expect(screen.getByText(/No action is recommended unless it turns RED/)).toBeTruthy();
  });
});

describe("VehicleRow with no link (LL-01, issue 73: a trust state is never shown as current)", () => {
  const green = {
    vehicle_id: "uav1", stamp_s: 1, state: "GREEN" as const, reason: null,
    horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9,
  };
  const props = { vehicleId: "uav1", since: 0, now: 30, sectors: [], doneSectors: [], history: [], calibration: null, onFocus: vi.fn() };
  const noLink = { state: "NO_LINK" as const, lastHeardAt_s: 18 };

  it("says there is no link and how long ago the vehicle was last heard", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.getByText("No link")).toBeTruthy();
    expect(screen.getByText("Last heard 0:12 ago")).toBeTruthy();
  });

  it("shows the trust state as the last one known, not as current", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.getByText("Last known")).toBeTruthy();
    expect(screen.getByText("Trusted")).toBeTruthy(); // still readable, but marked
  });

  it("claims no position error, no time in state and no margin to alert while there is no link", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.queryByText("within 3 m")).toBeNull();
    expect(screen.queryByText(/of reports/)).toBeNull();
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.queryByText(/Comfortable/)).toBeNull();
    // the position error and the time in state both read "not current"
    expect(screen.getAllByText("not current")).toHaveLength(2);
    expect(screen.getByText("Margin to alert: not current, no link.")).toBeTruthy();
  });

  it("marks the reason as the last one known", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.getByText("Last known: Navigation consistent")).toBeTruthy();
  });

  it("tells a screen reader, in the row's name, that the state is last known and there is no link", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.getByRole("button", { name: "uav1, GREEN (last known), no link. Show on map" })).toBeTruthy();
  });

  it("does not guess how long ago it was heard before the server clock is known", () => {
    render(<VehicleRow {...props} now={null} trust={green} link={noLink} />);
    expect(screen.getByText("Last heard: unknown")).toBeTruthy();
  });

  describe("the red row tint, which says 'not trusted now'", () => {
    const red = { ...green, state: "RED" as const, reason: "INCONSISTENT_INNOVATION" as const, horizontal_bound_m: null, confidence: 0, headroom: 0 };
    const tinted = () => screen.getByRole("button").className.includes("bg-bad/10");

    it("is shown for a RED vehicle that can be heard", () => {
      render(<VehicleRow {...props} trust={red} link={{ state: "LINK_OK", lastHeardAt_s: 29 }} />);
      expect(tinted()).toBe(true);
    });

    it("is not shown when there is no link, because the state is only the last known", () => {
      render(<VehicleRow {...props} trust={red} link={noLink} />);
      expect(tinted()).toBe(false);
      expect(screen.getByText("Last known")).toBeTruthy(); // the dashed chip still says what it was
    });
  });

  it.each([
    ["nothing known about the link", undefined],
    ["the link up", { state: "LINK_OK" as const, lastHeardAt_s: 29 }],
  ])("looks as before with %s", (_, link) => {
    render(<VehicleRow {...props} trust={green} link={link} />);
    expect(screen.queryByText("No link")).toBeNull();
    expect(screen.queryByText("Last known")).toBeNull();
    expect(screen.getByText("within 3 m")).toBeTruthy();
    expect(screen.getByRole("meter")).toBeTruthy();
    expect(screen.getByRole("button", { name: "uav1, GREEN. Show on map" })).toBeTruthy();
  });
});

describe("Header counts (LL-01, issue 73: a state last known is not counted as current)", () => {
  it("counts a vehicle with no link separately, not as trusted", () => {
    render(<Header connected source="live" now={10} counts={{ GREEN: 1, AMBER: 0, RED: 0, noLink: 1 }} />);
    expect(screen.getByText("2 vehicles")).toBeTruthy();
    expect(screen.getByText("1 trusted")).toBeTruthy();
    expect(screen.getByText("1 no link")).toBeTruthy();
  });

  it("shows no link count when every vehicle is heard", () => {
    render(<Header connected source="live" now={10} counts={{ GREEN: 2, AMBER: 0, RED: 0, noLink: 0 }} />);
    expect(screen.queryByText(/no link/)).toBeNull();
  });
});

describe("a decision raised again (issue 111)", () => {
  const again = { nth: 2, previousExpiredAt_s: 160 };

  it("the band says it was raised again, and how many times", () => {
    render(<DecisionBanner open={[rec]} now={130} raisedAgain={again} onReview={vi.fn()} />);
    expect(screen.getByText("Raised again (2nd time)")).toBeTruthy();
  });

  it("the card says when the previous one expired unanswered", () => {
    render(<RecommendationCard rec={rec} now={130} raisedAgain={again} disabled={false} onApprove={vi.fn()} onDeny={vi.fn()} />);
    expect(screen.getByText("Raised again, 2nd time. The previous one expired unanswered at T+2:40.")).toBeTruthy();
  });

  it("a first-time decision shows no such wording", () => {
    render(<DecisionBanner open={[rec]} now={130} raisedAgain={null} onReview={vi.fn()} />);
    render(<RecommendationCard rec={rec} now={130} raisedAgain={null} disabled={false} onApprove={vi.fn()} onDeny={vi.fn()} />);
    expect(screen.queryByText(/Raised again/)).toBeNull();
  });

  it("counts up the ordinals", () => {
    expect([1, 2, 3, 4, 11, 12, 21, 22].map(ordinal)).toEqual(["1st", "2nd", "3rd", "4th", "11th", "12th", "21st", "22nd"]);
  });
});

describe("ExpiredNotice (issue 112)", () => {
  const expiredRec = { ...rec, vehicle_id: "uav2", command: "LAND" as const };
  const decision = { recommendation_id: "r1", outcome: "EXPIRED" as const, decided_s: 160, operator: "system", note: "" };
  const redNow = { vehicle_id: "uav2", stamp_s: 1, state: "RED" as const, reason: "INCONSISTENT_INNOVATION" as const, horizontal_bound_m: null, confidence: 0, headroom: 0 };

  it("says nobody answered, that nothing was sent, and what the vehicle's state is now", () => {
    render(<ExpiredNotice rec={expiredRec} decision={decision} trustNow={redNow} onSeen={vi.fn()} />);
    expect(screen.getByText("Expired, nobody answered")).toBeTruthy();
    expect(screen.getByText(/Nothing was sent to the vehicle/)).toBeTruthy();
    expect(screen.getByText(/uav2 is now Not trusted/)).toBeTruthy();
    expect(screen.queryByText(/denied/i)).toBeNull();
  });

  it("has a Seen control that works", () => {
    const seen = vi.fn();
    render(<ExpiredNotice rec={expiredRec} decision={decision} trustNow={redNow} onSeen={seen} />);
    fireEvent.click(screen.getByRole("button", { name: "Seen" }));
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it("with no link, the vehicle's state is only the last known one and says so", () => {
    render(<ExpiredNotice rec={expiredRec} decision={decision} trustNow={redNow} noLink onSeen={vi.fn()} />);
    expect(screen.getByText(/uav2 had no link; its last known state was Not trusted/)).toBeTruthy();
    expect(screen.queryByText(/is now/)).toBeNull();
  });

  it("does not claim a state it does not know", () => {
    render(<ExpiredNotice rec={expiredRec} decision={decision} trustNow={undefined} onSeen={vi.fn()} />);
    expect(screen.getByText(/uav2: state not known/)).toBeTruthy();
  });
});

describe("a decision for a vehicle with no link (issue 128)", () => {
  const land: Recommendation = { ...rec, command: "LAND" };
  const base = { operator: "daniel", demo: false, busy: false, onOperatorChange: vi.fn(), onCancel: vi.fn(), onConfirm: vi.fn() };
  const warning = /uav2 has no link\. This command may not reach it\./;

  it("the confirmation says the command may not reach the vehicle, and can still be answered", () => {
    render(<ConfirmDialog {...base} rec={land} noLink />);
    expect(screen.getByText(warning)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Hold to confirm landing/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Cancel/ })).toBeTruthy();
  });

  it("shows no warning for a vehicle that can be heard", () => {
    render(<ConfirmDialog {...base} rec={land} />);
    expect(screen.queryByText(/no link/)).toBeNull();
  });

  it("the warning follows the link while the dialog is open", () => {
    const { rerender } = render(<ConfirmDialog {...base} rec={land} />);
    expect(screen.queryByText(warning)).toBeNull();
    rerender(<ConfirmDialog {...base} rec={land} noLink />);
    expect(screen.getByText(warning)).toBeTruthy();
    rerender(<ConfirmDialog {...base} rec={land} />);
    expect(screen.queryByText(warning)).toBeNull();
  });

  it("the open decision carries a short note too", () => {
    render(<RecommendationCard rec={land} now={130} disabled={false} noLink onApprove={vi.fn()} onDeny={vi.fn()} />);
    expect(screen.getByText(/uav2 has no link/)).toBeTruthy();
    expect((screen.getByRole("button", { name: /Approve/ }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("ConfirmDialog: landing needs a deliberate hold (issue 113)", () => {
  const land: Recommendation = { ...rec, command: "LAND" };
  const retask: Recommendation = { ...rec, command: null };
  const base = { operator: "daniel", demo: false, busy: false, onOperatorChange: vi.fn(), onCancel: vi.fn() };
  const holdButton = () => screen.getByRole("button", { name: /Hold to confirm landing|Keep holding/ });

  afterEach(() => vi.useRealTimers());

  it("confirms only after the full hold", () => {
    vi.useFakeTimers();
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...base} rec={land} onConfirm={onConfirm} />);
    fireEvent.pointerDown(holdButton());
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS - 1);
    expect(onConfirm).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("releasing early cancels the hold and leaves the dialog open", () => {
    vi.useFakeTimers();
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...base} rec={land} onConfirm={onConfirm} />);
    fireEvent.pointerDown(holdButton());
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS - 500);
    fireEvent.pointerUp(holdButton());
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS * 2);
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("a plain click does not confirm a landing", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...base} rec={land} onConfirm={onConfirm} />);
    fireEvent.click(holdButton());
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("holding Space on the keyboard works the same way, and releasing early cancels", () => {
    vi.useFakeTimers();
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...base} rec={land} onConfirm={onConfirm} />);
    fireEvent.keyDown(holdButton(), { key: " " });
    vi.advanceTimersByTime(500);
    fireEvent.keyUp(holdButton(), { key: " " });
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS * 2);
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.keyDown(holdButton(), { key: " " });
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("shows that the hold is in progress", () => {
    vi.useFakeTimers();
    render(<ConfirmDialog {...base} rec={land} onConfirm={vi.fn()} />);
    expect(screen.queryByText("Keep holding...")).toBeNull();
    fireEvent.pointerDown(holdButton());
    expect(screen.getByText("Keep holding...")).toBeTruthy();
    fireEvent.pointerUp(holdButton());
    expect(screen.queryByText("Keep holding...")).toBeNull();
  });

  it("does not open with the confirm control focused", () => {
    render(<ConfirmDialog {...base} rec={land} onConfirm={vi.fn()} />);
    expect(document.activeElement).not.toBe(holdButton());
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cancel" }));
  });

  it("tells assistive technology that the hold started, and that releasing cancelled it", () => {
    vi.useFakeTimers();
    render(<ConfirmDialog {...base} rec={land} onConfirm={vi.fn()} />);
    expect(screen.getByRole("status").textContent).toBe("");
    fireEvent.pointerDown(holdButton());
    expect(screen.getByRole("status").textContent).toMatch(/Holding/);
    fireEvent.pointerUp(holdButton());
    expect(screen.getByRole("status").textContent).toMatch(/Released. Nothing was approved/);
  });

  it("links the instruction to the button", () => {
    render(<ConfirmDialog {...base} rec={land} onConfirm={vi.fn()} />);
    const hint = document.getElementById(holdButton().getAttribute("aria-describedby") ?? "");
    expect(hint?.textContent).toMatch(/Landing cannot be undone/);
  });

  it("clearing the operator name during a hold stops it from confirming", () => {
    vi.useFakeTimers();
    const onConfirm = vi.fn();
    const { rerender } = render(<ConfirmDialog {...base} rec={land} onConfirm={onConfirm} />);
    fireEvent.pointerDown(holdButton());
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS - 100);
    rerender(<ConfirmDialog {...base} rec={land} operator="  " onConfirm={onConfirm} />);
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("a blank operator name disables the hold", () => {
    vi.useFakeTimers();
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...base} rec={land} operator="  " onConfirm={onConfirm} />);
    fireEvent.pointerDown(holdButton());
    vi.advanceTimersByTime(HOLD_TO_CONFIRM_MS * 2);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("a re-task with no vehicle command still confirms with one click and opens on Confirm", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...base} rec={retask} onConfirm={onConfirm} />);
    const confirm = screen.getByRole("button", { name: "Confirm approval" });
    expect(document.activeElement).toBe(confirm);
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("an open decision marked seen (issue 115)", () => {
  it("has a Seen control that works from the keyboard", () => {
    const onSeen = vi.fn();
    render(<RecommendationCard rec={rec} now={130} disabled={false} onApprove={vi.fn()} onDeny={vi.fn()} onSeen={onSeen} />);
    const button = screen.getByRole("button", { name: "Seen" });
    expect(button.tagName).toBe("BUTTON");
    fireEvent.click(button);
    expect(onSeen).toHaveBeenCalledTimes(1);
  });

  it("once seen, says so in words, still counts down and can still be approved", () => {
    render(<RecommendationCard rec={rec} now={130} disabled={false} seen onApprove={vi.fn()} onDeny={vi.fn()} onSeen={vi.fn()} />);
    expect(screen.getByText(/Seen, waiting for decision/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Seen" })).toBeNull();
    expect(screen.getByText("Expires in 0:30")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Approve/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("the band reads 'Seen, waiting for decision' and keeps its countdown", () => {
    render(<DecisionBanner open={[rec]} now={130} seen onReview={vi.fn()} />);
    expect(screen.getByText("Seen, waiting for decision")).toBeTruthy();
    expect(screen.getByText(/expires in 0:30/)).toBeTruthy();
  });

  it("the band is unchanged while unseen", () => {
    render(<DecisionBanner open={[rec]} now={130} onReview={vi.fn()} />);
    expect(screen.getByText("Decision required")).toBeTruthy();
    expect(screen.queryByText(/Seen, waiting/)).toBeNull();
  });
});

describe("a re-task for a vehicle with no link (issue 134)", () => {
  const retask: Recommendation = { ...rec, command: null, sector_moves: [{ sector_id: "S2", to_vehicle: "uav3" }, { sector_id: "S4", to_vehicle: "uav1" }] };
  const base = { operator: "daniel", demo: false, busy: false, onOperatorChange: vi.fn(), onCancel: vi.fn(), onConfirm: vi.fn() };
  const warning = /uav2 has no link and may keep flying S2, S4/;

  it("the confirmation names the sectors the vehicle may keep flying", () => {
    render(<ConfirmDialog {...base} rec={retask} noLink />);
    expect(screen.getByText(warning)).toBeTruthy();
    expect(screen.queryByText(/This command may not reach it/)).toBeNull();
  });

  it("the open decision carries the same warning, and can still be approved", () => {
    render(<RecommendationCard rec={retask} now={130} disabled={false} noLink onApprove={vi.fn()} onDeny={vi.fn()} />);
    expect(screen.getByText(warning)).toBeTruthy();
    expect((screen.getByRole("button", { name: /Approve/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("a vehicle that can be heard shows no warning", () => {
    render(<ConfirmDialog {...base} rec={retask} />);
    expect(screen.queryByText(/no link/)).toBeNull();
  });

  it("a command keeps its own wording", () => {
    render(<ConfirmDialog {...base} rec={{ ...retask, command: "LAND" }} noLink />);
    expect(screen.getByText(/uav2 has no link\. This command may not reach it\./)).toBeTruthy();
  });
});

describe("the sound control in the header (issue 116)", () => {
  const counts = { GREEN: 1, AMBER: 0, RED: 0, noLink: 0 };

  it("always shows whether sound is on, and says off in words", () => {
    render(<Header connected source="live" counts={counts} now={10} soundOn={false} onToggleSound={vi.fn()} />);
    const button = screen.getByRole("button", { name: /Sound off/ });
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("shows on, and toggles", () => {
    const toggle = vi.fn();
    render(<Header connected source="live" counts={counts} now={10} soundOn onToggleSound={toggle} />);
    const button = screen.getByRole("button", { name: /Sound on/ });
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(button);
    expect(toggle).toHaveBeenCalledTimes(1);
  });
});

describe("while the backend is lost (issue 120)", () => {
  const green = {
    vehicle_id: "uav1", stamp_s: 1, state: "GREEN" as const, reason: null,
    horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9,
  };
  const props = { vehicleId: "uav1", trust: green, since: 0, now: 30, sectors: [], doneSectors: [], history: [], calibration: null, onFocus: vi.fn() };
  const noLink = { state: "NO_LINK" as const, lastHeardAt_s: 18 };
  const redTrust = { ...green, state: "RED" as const, reason: "INCONSISTENT_INNOVATION" as const, horizontal_bound_m: null, confidence: 0, headroom: 0 };
  const lost = { backendLost: true, backendLastHeardAt_s: 100 };

  it("a row presents nothing as current", () => {
    render(<VehicleRow {...props} {...lost} now={160} />);
    expect(screen.getByText("Last known")).toBeTruthy();
    expect(screen.getAllByText("not current")).toHaveLength(2); // position error and time in state
    expect(screen.getByText(/Margin to alert: not current/)).toBeTruthy();
    expect(screen.queryByText(/within 3 m/)).toBeNull();
    expect(screen.queryByText(/Comfortable/)).toBeNull();
    expect(screen.getByText(/Connection to the backend was lost. Last heard from it at T\+1:40/)).toBeTruthy();
  });

  it("a RED row loses its red tint", () => {
    render(<VehicleRow {...props} {...lost} trust={redTrust} now={160} />);
    expect(screen.getByRole("button").className.includes("bg-bad/10")).toBe(false);
  });

  it("a vehicle with no link keeps its own wording, and is still told apart", () => {
    render(<VehicleRow {...props} {...lost} link={noLink} now={160} />);
    expect(screen.getByText("No link")).toBeTruthy();
    expect(screen.getByText(/Last heard .* ago/)).toBeTruthy();
  });

  it("the header does not present the fleet's states as current", () => {
    render(<Header connected={false} source="live" counts={{ GREEN: 2, AMBER: 0, RED: 1, noLink: 0 }} now={160} backendLost />);
    expect(screen.getByText(/3 vehicles, last known/)).toBeTruthy();
    expect(screen.queryByText(/not trusted/)).toBeNull();
  });

  it("Approve, Deny and Seen are disabled and say why", () => {
    render(<RecommendationCard rec={rec} now={130} disabled={false} backendLost onApprove={vi.fn()} onDeny={vi.fn()} onSeen={vi.fn()} />);
    for (const name of [/Approve/, /Deny/, "Seen"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(screen.getByText(/no connection to the backend/i)).toBeTruthy();
    expect(screen.getByText("Expires in 0:30")).toBeTruthy(); // the countdown keeps counting
  });

  it("an expired notice cannot be marked seen either, and says why", () => {
    const decision = { recommendation_id: "r1", outcome: "EXPIRED" as const, decided_s: 160, operator: "system", note: "" };
    render(<ExpiredNotice rec={rec} decision={decision} trustNow={undefined} backendLost onSeen={vi.fn()} />);
    expect((screen.getByRole("button", { name: "Seen" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("an open confirmation cannot be confirmed", () => {
    render(<ConfirmDialog operator="daniel" demo={false} busy={false} backendLost onOperatorChange={vi.fn()} onCancel={vi.fn()} onConfirm={vi.fn()} rec={{ ...rec, command: "LAND" }} />);
    expect((screen.getByRole("button", { name: /Hold to confirm landing/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/no connection to the backend/i)).toBeTruthy();
  });

  it("is back to normal when the backend is not lost", () => {
    render(<VehicleRow {...props} now={160} />);
    expect(screen.queryByText("Last known")).toBeNull();
  });
});
