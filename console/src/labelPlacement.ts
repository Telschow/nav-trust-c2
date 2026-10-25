export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Whether two boxes share any area. Boxes that only touch do not overlap. */
export function overlaps(a: Box, b: Box): boolean {
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/** Which sector labels a vehicle tag would partly cover. A vehicle tag always stays whole; a
 * covered sector label is hidden entirely instead of being left clipped. Index-for-index with
 * `sectorLabels`. */
export function coveredByVehicleTag(sectorLabels: Box[], vehicleTags: Box[]): boolean[] {
  return sectorLabels.map((label) => vehicleTags.some((tag) => overlaps(label, tag)));
}
