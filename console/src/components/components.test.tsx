// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { DecisionBanner } from "./DecisionBanner";
import { titleOf } from "../language";
import { RecommendationCard } from "./RecommendationCard";
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

describe("VehicleRow with no link (issue 73: a trust state is never shown as current)", () => {
  const green = {
    vehicle_id: "uav1", stamp_s: 1, state: "GREEN" as const, reason: null,
    horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9,
  };
  const props = { vehicleId: "uav1", since: 0, now: 30, sectors: [], doneSectors: [], history: [], calibration: null, onFocus: vi.fn() };
  const noLink = { state: "NO_LINK" as const, lastHeard_s: 18 };

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

  it("claims no position error and no margin to alert while there is no link", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.queryByText("within 3 m")).toBeNull();
    expect(screen.queryByText(/of reports/)).toBeNull();
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.queryByText(/Comfortable/)).toBeNull();
    expect(screen.getAllByText(/not current/).length).toBeGreaterThanOrEqual(2);
  });

  it("tells a screen reader, in the row's name, that there is no link", () => {
    render(<VehicleRow {...props} trust={green} link={noLink} />);
    expect(screen.getByRole("button", { name: /no link/i })).toBeTruthy();
  });

  it("looks as before when the link is up or nothing is known about it", () => {
    for (const link of [undefined, { state: "LINK_OK" as const, lastHeard_s: 29 }]) {
      cleanup();
      render(<VehicleRow {...props} trust={green} link={link} />);
      expect(screen.queryByText("No link")).toBeNull();
      expect(screen.queryByText("Last known")).toBeNull();
      expect(screen.getByText("within 3 m")).toBeTruthy();
      expect(screen.getByRole("meter")).toBeTruthy();
    }
  });
});
