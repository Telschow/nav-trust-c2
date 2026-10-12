# Security

This is a simulation-only research prototype. It has no authentication: the backend
(`c2/server.py`) takes the operator's name from whatever the client sends and must only be bound
to localhost. It is not designed to command real vehicles.

Binding to localhost does not stop a web page in the operator's browser from reaching the
backend. The backend therefore refuses browser requests from other origins and Host names a page
could rebind to this machine, on HTTP and on the WebSocket (`cross_site_reason` in
`c2/server.py`, tests in `tests/test_server_same_origin.py`).

Report a vulnerability privately through GitHub: Security tab, "Report a vulnerability". Please do
not open a public issue for it. This is a one-person project, so expect an answer within a week
or two, not hours.

In scope: the code in this repository (trust engine, backend, console, evaluation tools).
Out of scope: PX4, Gazebo, MAVSDK, OpenStreetMap and other upstream projects (report to them),
and anything that needs a real vehicle.
