import pytest

from trivian_resonance_lattice.lattice.differentiation_preservation import (
    PropagationObservation,
    entrainment_preserves_difference,
)


def observation(**overrides):
    values = dict(
        input_differentiation=0.8,
        output_differentiation=0.72,
        provenance_preserved=True,
        minority_signal_present_before=True,
        minority_signal_present_after=True,
    )
    values.update(overrides)
    return PropagationObservation(**values)


def test_retention_ratio_tracks_difference_survival():
    assert observation().retention_ratio == pytest.approx(0.9)


def test_provenance_erasure_is_a_violation():
    obs = observation(provenance_preserved=False)
    assert "provenance_erasure" in obs.violations()


def test_minority_signal_extinction_is_a_violation():
    obs = observation(minority_signal_present_after=False)
    assert "minority_signal_extinction" in obs.violations()


def test_excessive_differentiation_loss_is_a_violation():
    obs = observation(output_differentiation=0.3)
    assert "differentiation_loss" in obs.violations(minimum_retention=0.8)


def test_entrainment_can_coordinate_without_erasing_difference():
    assert entrainment_preserves_difference(observation(), minimum_retention=0.8)


def test_zero_input_differentiation_does_not_create_division_failure():
    obs = observation(input_differentiation=0.0, output_differentiation=0.0)
    assert obs.retention_ratio == 1.0


def test_invalid_retention_threshold_rejected():
    with pytest.raises(ValueError):
        observation().violations(minimum_retention=1.1)
