"""Feed a recording through a detector. Pure Python; used by the replay tests."""

from __future__ import annotations

from navtrust.availability import AvailabilityDetector, AvailabilityReport
from navtrust.recording import Recording


def replay_availability(
    recording: Recording, detector: AvailabilityDetector, step_s: float = 0.5
) -> list[AvailabilityReport]:
    """Run the detector over the recording, producing a report every step_s seconds."""
    reports: list[AvailabilityReport] = []
    records = [r for r in recording.records if r["event"] in ("gps_info", "estimator_status")]
    end_s = recording.records[-1]["t_s"]
    next_report_s = 0.0
    i = 0
    while next_report_s <= end_s:
        while i < len(records) and records[i]["t_s"] <= next_report_s:
            rec = records[i]
            if rec["event"] == "gps_info":
                detector.update_fix(rec["t_s"], rec["fix_type"])
            else:
                detector.update_estimator(rec["t_s"], rec.get("pos_horiz_accuracy"))
            i += 1
        reports.append(detector.report(next_report_s))
        next_report_s += step_s
    return reports
