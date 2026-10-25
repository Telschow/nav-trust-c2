import { describe, expect, it } from "vitest";
import { coveredByVehicleTag, overlaps } from "./labelPlacement";

const box = (left: number, top: number, right: number, bottom: number) => ({ left, top, right, bottom });

describe("map label placement (issue 130)", () => {
  it("hides a sector label that a vehicle tag would partly cover", () => {
    const sector = box(0, 0, 100, 20);
    const vehicle = box(90, 10, 200, 50); // clips the label's corner
    expect(coveredByVehicleTag([sector], [vehicle])).toEqual([true]);
  });

  it("keeps a sector label that no vehicle tag touches", () => {
    expect(coveredByVehicleTag([box(0, 0, 100, 20)], [box(0, 40, 100, 80)])).toEqual([false]);
  });

  it("decides each label on its own", () => {
    const labels = [box(0, 0, 100, 20), box(0, 100, 100, 120)];
    expect(coveredByVehicleTag(labels, [box(50, 10, 150, 30)])).toEqual([true, false]);
  });

  it("is covered by any one of several tags", () => {
    const tags = [box(500, 500, 600, 600), box(10, 5, 20, 15)];
    expect(coveredByVehicleTag([box(0, 0, 100, 20)], tags)).toEqual([true]);
  });

  it("boxes that only touch do not overlap", () => {
    expect(overlaps(box(0, 0, 10, 10), box(10, 0, 20, 10))).toBe(false);
  });

  it("with no vehicle tags nothing is hidden", () => {
    expect(coveredByVehicleTag([box(0, 0, 100, 20)], [])).toEqual([false]);
  });
});
