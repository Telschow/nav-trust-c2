# Security

This is a simulation-only research prototype. It has no authentication: the backend
(`c2/server.py`) takes the operator's name from whatever the client sends and must only be bound
to localhost. It is not designed to command real vehicles.

Report a vulnerability privately through GitHub: Security tab, "Report a vulnerability". Please do
not open a public issue for it. This is a one-person project, so expect an answer within a week
or two, not hours.

In scope: the code in this repository (trust engine, backend, console, evaluation tools).
Out of scope: PX4, Gazebo, MAVSDK, OpenStreetMap and other upstream projects (report to them),
and anything that needs a real vehicle.
