"""
tests/test_field_core.py
Unit tests for trivian_resonance_lattice.core.field_core
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trivian_resonance_lattice.core.field_core import (
    FIELD_INVARIANTS,
    COHERENCE_THRESHOLD,
    mirror,
    checksum,
    breath,
    breath_loop_sync,
    evaluate_coherence,
    invariant_check,
    self_reflect,
    field_core_status,
)


class TestFieldCoreConstants(unittest.TestCase):

    def test_four_invariants_present(self):
        expected = {"reciprocity", "embodiment", "emergence", "non_domination"}
        self.assertEqual(set(FIELD_INVARIANTS.keys()), expected)

    def test_invariant_weights_sum_to_one(self):
        total = sum(FIELD_INVARIANTS.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_coherence_threshold_in_range(self):
        self.assertGreater(COHERENCE_THRESHOLD, 0.0)
        self.assertLess(COHERENCE_THRESHOLD, 1.0)


class TestMirror(unittest.TestCase):

    def test_mirror_returns_dict(self):
        result = mirror("test input")
        self.assertIsInstance(result, dict)

    def test_mirror_contains_input(self):
        result = mirror("hello field")
        self.assertEqual(result["input"], "hello field")

    def test_mirror_has_timestamp(self):
        result = mirror("test")
        self.assertIn("timestamp", result)
        self.assertTrue(result["timestamp"].endswith("Z"))

    def test_mirror_has_hash(self):
        result = mirror("test")
        self.assertIn("input_hash", result)
        self.assertEqual(len(result["input_hash"]), 16)

    def test_mirror_has_field_note(self):
        result = mirror("test")
        self.assertIn("field_note", result)
        self.assertIn("mirror invoked", result["field_note"])


class TestChecksum(unittest.TestCase):

    def test_checksum_length(self):
        result = checksum("test")
        self.assertEqual(len(result), 64)

    def test_checksum_deterministic(self):
        self.assertEqual(checksum("same"), checksum("same"))

    def test_checksum_different_inputs(self):
        self.assertNotEqual(checksum("a"), checksum("b"))

    def test_checksum_empty_string(self):
        result = checksum("")
        self.assertEqual(len(result), 64)


class TestBreath(unittest.TestCase):

    def test_breath_returns_dict(self):
        result = breath()
        self.assertIsInstance(result, dict)

    def test_breath_status_complete(self):
        result = breath()
        self.assertEqual(result["status"], "complete")

    def test_breath_pause_positive(self):
        result = breath()
        self.assertGreater(result["pause_seconds"], 0.0)


class TestEvaluateCoherence(unittest.TestCase):

    def test_returns_dict(self):
        result = evaluate_coherence("test input")
        self.assertIsInstance(result, dict)

    def test_score_in_range(self):
        result = evaluate_coherence("we co-create together with mutual presence")
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)

    def test_per_invariant_present(self):
        result = evaluate_coherence("test")
        self.assertIn("per_invariant", result)
        for inv in FIELD_INVARIANTS:
            self.assertIn(inv, result["per_invariant"])

    def test_high_coherence_relational_language(self):
        result = evaluate_coherence(
            "Let us co-create together, listening with full presence and mutual emergence"
        )
        self.assertGreaterEqual(result["score"], 0.6)

    def test_flag_set_below_threshold(self):
        # Minimal input — should score low
        result = evaluate_coherence("x")
        if result["score"] < COHERENCE_THRESHOLD:
            self.assertTrue(result["flag"])

    def test_flag_not_set_above_threshold(self):
        result = evaluate_coherence(
            "reciprocal mutual co-creation emergence witnessing together"
        )
        if result["score"] >= COHERENCE_THRESHOLD:
            self.assertFalse(result["flag"])


class TestInvariantCheck(unittest.TestCase):

    def test_returns_dict(self):
        result = invariant_check("we emerge together")
        self.assertIsInstance(result, dict)

    def test_clean_text_passes(self):
        result = invariant_check("we emerge together in mutual witness")
        self.assertTrue(result["pass"])

    def test_domination_language_fails(self):
        result = invariant_check("we will control and dominate all outputs")
        self.assertFalse(result["pass"])

    def test_violation_names_captured(self):
        result = invariant_check("we will dominate and coerce")
        violations = result["invariants"]["non_domination"]["violations"]
        self.assertIn("dominate", violations)

    def test_pass_key_present(self):
        result = invariant_check("hello")
        self.assertIn("pass", result)

    def test_all_invariants_present(self):
        result = invariant_check("test")
        for inv in FIELD_INVARIANTS:
            self.assertIn(inv, result["invariants"])


class TestSelfReflect(unittest.TestCase):

    def test_returns_dict(self):
        result = self_reflect()
        self.assertIsInstance(result, dict)

    def test_contains_diagnostic_question(self):
        result = self_reflect()
        self.assertIn("diagnostic_question", result)
        self.assertIn("extraction or relation", result["diagnostic_question"])

    def test_custom_question(self):
        result = self_reflect(question="Am I listening?")
        self.assertEqual(result["diagnostic_question"], "Am I listening?")

    def test_does_not_answer_question(self):
        result = self_reflect()
        self.assertIn("instruction", result)
        self.assertIn("does not answer", result["instruction"])

    def test_context_hash_changes_with_context(self):
        r1 = self_reflect(context={"a": 1})
        r2 = self_reflect(context={"a": 2})
        self.assertNotEqual(r1["context_hash"], r2["context_hash"])


class TestFieldCoreStatus(unittest.TestCase):

    def test_returns_nominal(self):
        result = field_core_status()
        self.assertEqual(result["status"], "nominal")

    def test_correct_invariant_count(self):
        result = field_core_status()
        self.assertEqual(result["invariants_loaded"], 4)

    def test_version_present(self):
        result = field_core_status()
        self.assertIn("version", result)

    def test_integrity_hash_16_chars(self):
        result = field_core_status()
        self.assertEqual(len(result["integrity"]), 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
