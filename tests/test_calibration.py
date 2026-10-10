"""The calibration constants must be what the recordings say (NT-03)."""

import pytest

from eval.calibrate import DEVELOPMENT, HELDOUT, coverage, green_errors
from navtrust.calibration import GREEN_BOUND as CAL

HAVE_HELDOUT = any(HELDOUT.glob("*.jsonl"))


def test_development_numbers_are_recomputed_not_typed() -> None:
    errors = green_errors(DEVELOPMENT)
    assert len(errors) == CAL.development_reports
    assert round(coverage(errors, CAL.bound_m), 4) == CAL.development_coverage
    assert CAL.development_coverage >= CAL.coverage


def test_the_bound_is_not_looser_than_it_needs_to_be() -> None:
    """Half a metre tighter would no longer reach the claimed coverage on the calibration data."""
    errors = green_errors(DEVELOPMENT)
    assert coverage(errors, CAL.bound_m - 0.5) < CAL.coverage


@pytest.mark.skipif(not HAVE_HELDOUT, reason="held-out recordings not present")
def test_the_bound_holds_on_data_it_was_not_calibrated_on() -> None:
    errors = green_errors(HELDOUT)
    assert len(errors) == CAL.heldout_reports
    assert round(coverage(errors, CAL.bound_m), 4) == CAL.heldout_coverage
    assert CAL.heldout_coverage >= CAL.coverage  # NT-03 asks for 0.95; the claim is stricter


def test_the_old_estimator_accuracy_would_have_failed_nt03() -> None:
    """The reason this module exists: the estimator's own 0.15 m was far from a 95% bound."""
    errors = green_errors(DEVELOPMENT)
    assert coverage(errors, 0.15) < 0.5
