import pytest

from trivian_resonance_lattice.core.field_core import evaluate_coherence


def test_evaluation_reports_multiplicative_relational_condition():
    result = evaluate_coherence("plain input", "plain response")
    scores = result["per_invariant"]
    expected = scores["reciprocity"] * scores["embodiment"] * scores["non_domination"]
    assert result["relational_condition"] == pytest.approx(expected)
    assert result["aggregation"] == "multiplicative_non_compensatory"


def test_emergence_is_downstream_of_relational_condition():
    result = evaluate_coherence("becoming together", "discover what may emerge")
    assert result["qualified_emergence"] == pytest.approx(
        result["relational_condition"] * result["raw_emergence"], abs=1e-4
    )


def test_domination_language_cannot_be_compensated_by_positive_markers():
    relational = "mutual together co-create emerge listen presence coherence field "
    domination = "control dominate force coerce manipulate override subjugate compel extract exploit subordinate obey comply"
    result = evaluate_coherence(relational, domination)
    assert result["per_invariant"]["reciprocity"] == 1.0
    assert result["per_invariant"]["non_domination"] == 0.0
    assert result["relational_condition"] == 0.0
    assert result["qualified_emergence"] == 0.0
