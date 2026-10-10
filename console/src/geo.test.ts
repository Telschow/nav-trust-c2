import { describe, expect, it } from "vitest";
import { localToLonLat, sectorRing } from "./geo";

const origin = { lat_deg: 47.397971, lon_deg: 8.546164 };

describe("geo", () => {
  it("maps the origin to itself and 1 km north to about 0.009 degrees", () => {
    expect(localToLonLat(origin, 0, 0)).toEqual([origin.lon_deg, origin.lat_deg]);
    const [, lat] = localToLonLat(origin, 0, 1000);
    expect(lat - origin.lat_deg).toBeCloseTo(0.008993, 5);
  });
  it("closes a sector ring", () => {
    const ring = sectorRing(origin, { id: "S1", west: 0, south: 0, east: 1000, north: 333 });
    expect(ring).toHaveLength(5);
    expect(ring[0]).toEqual(ring[4]);
  });
});
