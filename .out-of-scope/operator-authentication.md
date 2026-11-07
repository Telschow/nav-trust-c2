# Operator authentication

This project does not authenticate operators. The name typed when deciding is recorded as given
and is not proof of who decided (GLOSSARY: Operator name).

## Why this is out of scope

The backend is a simulation tool that binds to loopback by default. A login or identity provider
would be a heavy new dependency and an ICD change for a deployment the project does not claim:
no real aircraft, no multi-user operations room. What the audit proves is that an approval row
exists for each command, not who the person was; `c2/audit_verify.py` and the README say so. The
Host and Origin checks stop other web pages from calling the API; they are not identity.

Do not describe approvals as "verified", "authenticated" or "signed" anywhere. If the project
ever serves more than one operator on a network, delete this file and open a new issue.

## Prior requests

- The post-remediation audit of November 2026 (finding NTC-01).
