# nav-trust-c2

Human-on-the-loop supervision of a small simulated drone fleet. The system judges how far each vehicle's navigation can be trusted, recommends actions, and runs nothing without a recorded operator decision.

## Language

### Judging a vehicle

**Navigation integrity**:
Whether a vehicle's reported position, and the bound on its error, can be trusted. One of three independent dimensions per vehicle.
_Avoid_: GPS health, nav status

**Link health**:
Whether a vehicle's reports are reaching the backend, and how fresh they are. One of three independent dimensions per vehicle.
_Avoid_: connectivity, signal quality

**Operator availability**:
Whether a decision can be made in time. One of three independent dimensions per vehicle.
_Avoid_: operator state

**Trust state**:
The navigation-integrity verdict for one vehicle: GREEN, AMBER or RED.
_Avoid_: health, status, alert level

**Reason code**:
The named cause behind an AMBER or RED trust state.
_Avoid_: error code, alert type

**Position bound**:
The distance within which a GREEN vehicle's true position is claimed to lie, calibrated against ground truth and shown with its measured coverage. Unknown outside GREEN.
_Avoid_: uncertainty, error bound, confidence radius

**Position inconsistency**:
The engine's finding that the reported position disagrees with the vehicle's other sensors. It cannot tell a frozen position from a spoofed one.
_Avoid_: drift, spoofing detected

**Frozen position**:
An injected fault in which the receiver keeps reporting a good fix while the position stops changing. Triggers position inconsistency.
_Avoid_: stuck GPS (except as PX4's injection name)

**Wrong fix**:
An injected fault in which the receiver reports a confident but incorrect position. Triggers position inconsistency.
_Avoid_: spoofing (the simulator does not model spoofing)

**Stale**:
The engine's own input has gone silent. A navigation-integrity condition, separate from a lost link.
_Avoid_: timeout

### The link

**Telemetry link**:
The path by which a vehicle's reports reach the backend. Modelled as symmetric in the simulator; an asymmetric link is out of scope.
_Avoid_: datalink, connection, comms

**No link**:
The backend has not heard from a vehicle within the link timeout. Says nothing about the vehicle's navigation; the last trust state is shown as last known, with its age.
_Avoid_: disconnected (reserved for the console losing the backend), offline

**Outage**:
One stretch of a vehicle having no link, from the last report heard to the first trust report after it. When it ends the backend says how long it was, what changed, and closes what it made stale.
_Avoid_: disconnection

### Authority

**Recommendation**:
A proposed action, raised by the recommender, awaiting an operator decision. Never executes by itself.
_Avoid_: suggestion, alert, command

**Superseded**:
A recommendation the backend closed because the vehicle's trust state or reason changed during an outage, so the operator is not asked to approve something about a situation that no longer holds. A new one is raised if the vehicle still needs it.
_Avoid_: cancelled, withdrawn

**Acknowledged**:
A command the vehicle answered. A re-task is a separate command to each vehicle it changes, each with its own answer. A command with no answer in time is audited as not acknowledged and never resent. Not acknowledged means the outcome is unknown, not that the command did not happen: it may still have reached the vehicle.
_Avoid_: delivered, confirmed

**Executed**:
A command whose executor call returned without error. It says nothing about what the vehicle then did: an executed LAND is not a landing.
_Avoid_: completed, done, landed

**Operator name**:
The label an operator types when deciding, recorded as given. It is not authenticated and does not prove who decided.
_Avoid_: operator identity, user, login

**Mission**:
One supervised run of the fleet, named by an id the operator sets when approving contingencies. A contingency covers the vehicles and the mission it names, and nothing else.
_Avoid_: flight, sortie, session (a Session is a backend run)

**Session**:
One run of the backend, marked in the audit log by a `session_started` row. Its id is in every recommendation id and every command row cites the decision that authorised it, so the log proves which approval authorised which command even after a restart.
_Avoid_: boot, process

**Approval**:
A recorded operator decision to allow a recommendation. Spent once used.
_Avoid_: confirmation, sign-off

**Contingency**:
A fault-and-link condition paired with an action, approved by the operator before the mission so a vehicle may carry it out onboard while the link is down. The only action allowed in v1 is LAND.
_Avoid_: autonomous action, onboard autonomy, failsafe (reserved for PX4)

**PX4 failsafe**:
An action PX4 takes on its own, such as landing after a long GNSS outage. Not a command from the console.
_Avoid_: contingency

**Authority**:
What a vehicle action ran under: a live approval, a contingency, or a PX4 failsafe. Every action traces to a recorded approval or to PX4.
_Avoid_: permission, mode
