// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { RecommendationCard } from "./RecommendationCard";
import { StateChip } from "./StateChip";
import { VehicleCard } from "./VehicleCard";
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

describe("VehicleCard", () => {
  const green = {
    vehicle_id: "uav1", stamp_s: 1, state: "GREEN" as const, reason: null,
    horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9,
  };
  const props = { vehicleId: "uav1", since: 0, now: 10, sectors: [], history: [], calibration: null, onFocus: vi.fn() };

  it("shows the calibrated bound with its coverage, and the margin to alert", () => {
    render(<VehicleCard {...props} trust={green} />);
    expect(screen.getByText("within 3 m")).toBeTruthy();
    expect(screen.getByText("99% of reports")).toBeTruthy();
    expect(screen.getByText(/Comfortable \(90%\)/)).toBeTruthy();
    expect((screen.getByRole("meter") as HTMLElement).getAttribute("aria-valuenow")).toBe("90");
  });

  it("warns in words when the margin is nearly gone", () => {
    render(<VehicleCard {...props} trust={{ ...green, headroom: 0.1 }} />);
    expect(screen.getByText(/Close to an alert \(10%\)/)).toBeTruthy();
  });

  it("claims no bound and no margin outside GREEN", () => {
    const red = { ...green, state: "RED" as const, reason: "STALE" as const, horizontal_bound_m: null, confidence: 0, headroom: 0 };
    render(<VehicleCard {...props} trust={red} />);
    expect(screen.getByText("unknown")).toBeTruthy();
    expect(screen.getByText(/none, already flagged/)).toBeTruthy();
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.queryByText(/of reports/)).toBeNull();
  });
});
