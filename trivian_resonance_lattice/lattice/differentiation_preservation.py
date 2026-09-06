"""Network preservation checks for TRIA Generative Differentiation.

TRL does not decide whether a source is genuinely orthogonal. It preserves and
reports differentiation supplied by upstream measurement while signals move
through translation, entrainment, synthesis, and propagation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PropagationObservation:
    input_differentiation: float
    output_differentiation: float
    provenance_preserved: bool
    minority_signal_present_before: bool
    minority_signal_present_after: bool

    def __post_init__(self) -> None:
        for name in ("input_differentiation", "output_differentiation"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0.0, 1.0]")

    @property
    def retention_ratio(self) -> float:
        if self.input_differentiation == 0.0:
            return 1.0
        return self.output_differentiation / self.input_differentiation

    def violations(self, *, minimum_retention: float = 0.8) -> tuple[str, ...]:
        if not 0.0 <= minimum_retention <= 1.0:
            raise ValueError("minimum_retention must be in [0.0, 1.0]")
        found = []
        if not self.provenance_preserved:
            found.append("provenance_erasure")
        if self.minority_signal_present_before and not self.minority_signal_present_after:
            found.append("minority_signal_extinction")
        if self.retention_ratio < minimum_retention:
            found.append("differentiation_loss")
        return tuple(found)


def entrainment_preserves_difference(
    observation: PropagationObservation,
    *,
    minimum_retention: float = 0.8,
) -> bool:
    """Return True only when coordination has not silently erased difference."""
    return not observation.violations(minimum_retention=minimum_retention)
