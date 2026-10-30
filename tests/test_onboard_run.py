"""The glue around the onboard monitor that needs no simulator (issue 76)."""

import asyncio
import json
from typing import Any

import pytest

from c2.contingency import policy_sha256
from sim.onboard_monitor import OnboardAction
from sim.onboard_policy import load_policy
from sim.onboard_run import action_report, experiment_approval

ACTION = OnboardAction("uav1", 59.0, "LAND", "INCONSISTENT_INNOVATION", 5.2, 7, "ab" * 32)


def test_an_experiment_approval_loads_and_says_what_it_is() -> None:
    approval = experiment_approval(wait_s=5.0)
    assert approval["audit_id"] == 0  # not an operator approval: a recorded experiment's own
    assert approval["sha256"] == policy_sha256(approval["policy"])
    policy = load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)
    assert policy.wait_s == 5.0 and policy.matches("INCONSISTENT_INNOVATION", "NO_LINK")


def test_a_wait_the_vehicle_would_refuse_cannot_make_an_experiment_policy() -> None:
    approval = experiment_approval(wait_s=12.0)
    with pytest.raises(Exception, match="wait"):
        load_policy(approval, now_s=approval["approved_s"], max_age_s=3600.0)


def test_the_report_to_the_backend_carries_the_action_and_its_policy_reference() -> None:
    assert action_report(ACTION) == {
        "vehicle_id": "uav1", "t_s": 59.0, "action": "LAND",
        "reason": "INCONSISTENT_INNOVATION", "link_down_s": 5.2,
        "policy_audit_id": 7, "policy_sha256": "ab" * 32,
    }  # fmt: skip


def test_unreported_actions_are_posted_once_to_the_backend() -> None:
    httpx = pytest.importorskip("httpx")
    from sim.onboard_run import report_actions

    seen: list[dict[str, Any]] = []

    def handler(request: Any) -> Any:
        seen.append(json.loads(request.content))
        return httpx.Response(204)

    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await report_actions(client, "http://backend", [ACTION])

    asyncio.run(go())
    assert seen == [action_report(ACTION)]
