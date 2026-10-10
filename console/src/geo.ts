import type { Origin, Sector } from "./types";

const EARTH_RADIUS_M = 6_371_008.8; // same value as the backend's flat-earth conversion

/** East/north metres from the origin to [lon, lat]. Accurate enough at survey scale. */
export function localToLonLat(origin: Origin, east_m: number, north_m: number): [number, number] {
  const lat = origin.lat_deg + (north_m / EARTH_RADIUS_M) * (180 / Math.PI);
  const lon =
    origin.lon_deg +
    (east_m / (EARTH_RADIUS_M * Math.cos((origin.lat_deg * Math.PI) / 180))) * (180 / Math.PI);
  return [lon, lat];
}

export function sectorRing(origin: Origin, s: Sector): [number, number][] {
  return [
    localToLonLat(origin, s.west, s.south),
    localToLonLat(origin, s.east, s.south),
    localToLonLat(origin, s.east, s.north),
    localToLonLat(origin, s.west, s.north),
    localToLonLat(origin, s.west, s.south),
  ];
}
