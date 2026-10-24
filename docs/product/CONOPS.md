# Concept of operations (unclassified, simulation only)

This version deliberately differs from the spec's first idea where the evidence did; see the last section.

## Setting

A 1 x 1 km search-and-rescue survey area is split into three sectors, one per vehicle. Three small
multicopters fly lawnmower patterns, one sector each, at different altitudes. One operator
supervises them on the console. GNSS can degrade in part of the area. The operator approves or
denies every action the system recommends; the system sends nothing to a vehicle otherwise. The
vehicles' own PX4 failsafes act on their own and are not commands from the console.

## Roles

| Role | Does |
|---|---|
| Operator | Watches the console, approves or denies recommendations |
| Vehicles (PX4) | Fly the missions; run their own failsafes |
| Trust engine | Per vehicle: GREEN, AMBER or RED, with a reason and a bound |
| Recommender | Turns RED into a proposed action; never executes |
| Policy gate | Runs a command only after a recorded approval |

## Normal flight

All vehicles GREEN. Each vehicle row shows "within 3 m" (the calibrated bound) and a margin to alert. The
operator has nothing to decide.

## Vignette A: a long GNSS outage on one vehicle

1. Vehicle 3 flies into an interference zone and its receiver loses the fix.
2. The row goes AMBER about 1.2 s later ("GNSS signal lost or degraded"), then RED about 6.3 s
   after the loss. The position bound becomes "unknown".
3. PX4 lets the vehicle dead-reckon, then raises its own blind-land failsafe and lands it inside
   the zone (it does so several seconds after the loss; the timing was not measured exactly).
4. The recommender raises one recommendation: move sector 3 to a trusted vehicle. There is no
   vehicle command to recommend, because PX4 is already landing it.
5. The operator reads what approving will do, approves, and the sector moves. The recommendation
   expires after 60 s if nobody answers and is raised again while the vehicle is still RED.

## Vignette B: a frozen position (the dangerous one)

1. The receiver keeps reporting a good fix, but its position stops changing.
2. The vehicle believes it has not moved, so it keeps pushing toward its next waypoint and
   accelerates. **No PX4 failsafe fires** and nothing in its own estimate shows it.
3. The consistency detector flags it 3.0 to 4.5 s after the freeze, while the vehicle is still
   within a few metres of where it thinks it is. The row goes RED, "GNSS position disagrees with
   the vehicle's own sensors", with an urgent warning.
4. The recommendation is **LAND**, plus moving the vehicle's sector. Without an action the vehicle
   was about 1.4 km from its start 60 s after the fault and 5.3 km after 220 s, in the recorded
   experiment.
5. Approved 15 s after the fault, LAND put the vehicle on the ground within 9 s, 450 m from its
   start. HOLD and RTL, tried the same way, ended in fast uncontrolled descents hundreds of metres
   away (one run each).

## Vignette C: a frozen position while the link is down (proposed, not built)

Proposed for M5 and pending ADR 0004. Nothing here has been measured.

1. Before the mission the operator approves a contingency policy: if a vehicle's position is
   inconsistent and the link has been down for longer than the policy's wait time, it lands.
   The approval is recorded in the audit log.
2. A vehicle's receiver freezes while its link to the backend is down. No PX4 failsafe fires for
   the frozen position, and the backend cannot recommend anything because it cannot reach the
   vehicle.
3. The console shows the vehicle as NO LINK with its last trust state marked as last known.
4. The vehicle's onboard trust monitor sees the position inconsistency and, because it matches
   the approved policy, lands the vehicle.
5. When the link returns, the vehicle reports what it did and under which approval, and the
   console shows it. No decision made before the outage is replayed.

## What happens when things go wrong

| Situation | Behaviour |
|---|---|
| Operator does not answer | The recommendation expires after 60 s and is raised again while the vehicle stays RED. PX4's failsafes still act. |
| Data stops arriving | The vehicle goes AMBER (stale) after 3 s and RED after 5 more |
| Link lost, vehicle still reporting nothing (proposed, M5) | NO LINK after the link timeout, last trust state shown as last known with its age; no command is proposed to that vehicle, but its sector can be re-assigned |
| Backend down | The console shows DISCONNECTED and the last known state. Vehicles keep flying on their own. Not tested beyond that |
| Link between console and vehicle lost | **Not modelled in v1.** Proposed for M5, see vignette C |
| Approved command fails | The failure is audited, the sector assignment is restored, the approval is spent |

## What the operator decides, and what they cannot

They decide whether to land a vehicle and whether to hand its sector to another. They cannot make
a vehicle fly somewhere, change a mission by hand, or bypass the gate. v1 does not offer HOLD or RTL as alternatives for the frozen case; the evidence says they are worse.

## Assumptions and limits

Simulation only (PX4 SITL in Gazebo, one vehicle model, 5 to 12 m/s). The faults are PX4's own
GPS failure injection. The timings above are from a handful of runs (2 to 4 per scenario). The
operator is assumed to be present and able to act within about a minute.

## What changed from the first CONOPS

The spec's first version had the drifting vehicle recommended to "RTL via a dead-reckoning
corridor". Ground truth showed that for a frozen position RTL does not work; only LAND stopped the
vehicle safely (ADR 0003). A fault that makes a vehicle fly away is also faster and more dangerous
than the spec assumed, which is why the queue puts it first and the card says so.
