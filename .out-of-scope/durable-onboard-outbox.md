# Durable onboard report outbox

The onboard monitor keeps its unsent action reports in memory. This project does not write them
to disk.

## Why this is out of scope

A report is retried with its id until the backend answers, so a network failure loses nothing and
a retry never records twice. What is lost is a report still queued when the onboard process
itself is killed between `take_unreported` and the backend's answer. The simulated vehicle
process is not expected to restart mid-landing, and a disk outbox adds a file format, cleanup and
restart tests for a case the project does not claim. The loss window is stated in ADR 0004
(point 4).

If the onboard process is ever run on something that restarts independently of the vehicle,
delete this file and open a new issue.

## Prior requests

- The post-remediation audit of November 2026 (finding NTC-06).
