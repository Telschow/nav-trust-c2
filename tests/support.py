"""Helpers the tests share."""


class Clock:
    """A settable clock: assign `t`, call it for the time."""

    t = 100.0

    def __call__(self) -> float:
        return self.t
