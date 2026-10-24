"""Set PX4's data-link-loss failsafe on a simulated vehicle and read it back.

At the pinned PX4 commit the x500 airframe already sets NAV_DLL_ACT to Return and the global
COM_DL_LOSS_T is 10 s (docs/validation/px4-lost-link-parameters.md). Setting them here, and
recording what the vehicle reports, makes the setting evidence in each recording and not an
assumption about the airframe file. Values are proposals until ADR 0004 is implemented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the simulator stack is optional; this module only needs a duck-typed drone
    from mavsdk_grpc import System

NAV_DLL_ACT_RETURN = 2  # proposal (ADR 0004); failsafe.h: Disabled 0, Hold 1, Return 2, Land 3
COM_DL_LOSS_T_S = 10  # proposal: PX4's default; seconds without a ground station before the
# failsafe is entered. A contingency's wait time (issue 76) must stay below this plus the hold.


async def apply_failsafe_params(drone: System) -> dict[str, float]:
    """Write NAV_DLL_ACT and COM_DL_LOSS_T, read back those and COM_FAIL_ACT_T, and return them.

    Raises if a written value did not stick, so a recording never claims a setting it lacks.
    """
    await drone.param.set_param_int("NAV_DLL_ACT", NAV_DLL_ACT_RETURN)
    await drone.param.set_param_int("COM_DL_LOSS_T", COM_DL_LOSS_T_S)
    held: dict[str, float] = {
        "NAV_DLL_ACT": await drone.param.get_param_int("NAV_DLL_ACT"),
        "COM_DL_LOSS_T": await drone.param.get_param_int("COM_DL_LOSS_T"),
        "COM_FAIL_ACT_T": await drone.param.get_param_float("COM_FAIL_ACT_T"),
    }
    for name, wanted in (("NAV_DLL_ACT", NAV_DLL_ACT_RETURN), ("COM_DL_LOSS_T", COM_DL_LOSS_T_S)):
        if held[name] != wanted:
            raise RuntimeError(f"{name} is {held[name]} after setting it to {wanted}")
    return held
