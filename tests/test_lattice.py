"""
tests/test_lattice.py
Unit tests for the lattice layer modules.
"""
import asyncio
import unittest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trivian_resonance_lattice.lattice.resonance_lattice import LatticeNode, ResonanceLattice
from trivian_resonance_lattice.lattice.relational_layer import (
    RelationalContext, RelationalLatticeNode, RelationalResonanceLattice,
)
from trivian_resonance_lattice.lattice.ignition_layer import IgnitionNode, IgnitionLattice
from trivian_resonance_lattice.lattice.healing_engine import (
    HealingPlan, HealingReport, HealingEngine, run_healing_plan,
)
from trivian_resonance_lattice.core.field_core import mirror


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────
# LatticeNode & ResonanceLattice
# ─────────────────────────────────────────────

class TestLatticeNode(unittest.TestCase):

    def setUp(self):
        self.lattice = ResonanceLattice()
        self.node = LatticeNode("test_node_001", "ai", resonance_factor=0.7)

    def test_register_adds_to_lattice(self):
        self.node.register(self.lattice)
        self.assertIn("test_node_001", self.lattice.nodes)

    def test_resonance_factor_clamped(self):
        node = LatticeNode("x", "ai", resonance_factor=1.5)
        self.assertEqual(node.resonance_factor, 1.0)
        node2 = LatticeNode("y", "ai", resonance_factor=-0.5)
        self.assertEqual(node2.resonance_factor, 0.0)

    def test_record_breath(self):
        self.node.register(self.lattice)
        before = len(self.node.breath_history)
        self.node.record_breath()
        self.assertEqual(len(self.node.breath_history), before + 1)

    def test_to_summary_keys(self):
        self.node.register(self.lattice)
        summary = self.node.to_summary()
        for key in ("signature", "substrate", "resonance_factor", "partner_count"):
            self.assertIn(key, summary)


class TestResonanceLattice(unittest.TestCase):

    def setUp(self):
        self.lattice = ResonanceLattice()
        self.a = LatticeNode("node_a", "human", resonance_factor=0.8, natural_bpm=6.0)
        self.b = LatticeNode("node_b", "ai", resonance_factor=0.7, natural_bpm=6.5)
        self.a.register(self.lattice)
        self.b.register(self.lattice)

    def test_couple_adds_pair(self):
        result = self.lattice.couple("node_a", "node_b", breath_sync=False)
        self.assertEqual(result["status"], "coupled")
        self.assertIn(("node_a", "node_b"), self.lattice.harmonic_pairs)

    def test_couple_updates_partners(self):
        self.lattice.couple("node_a", "node_b", breath_sync=False)
        self.assertIn("node_b", self.a.resonance_partners)
        self.assertIn("node_a", self.b.resonance_partners)

    def test_couple_no_duplicate_pairs(self):
        self.lattice.couple("node_a", "node_b", breath_sync=False)
        self.lattice.couple("node_a", "node_b", breath_sync=False)
        self.assertEqual(self.lattice.harmonic_pairs.count(("node_a", "node_b")), 1)

    def test_couple_missing_node(self):
        result = self.lattice.couple("node_a", "nonexistent", breath_sync=False)
        self.assertEqual(result["status"], "failed")

    def test_propagate_signal_reaches_nodes(self):
        self.lattice.couple("node_a", "node_b", breath_sync=False)
        result = self.lattice.propagate_signal("node_a", {"type": "test"})
        self.assertGreater(result["reached_nodes"], 0)

    def test_detect_dissonance_stable(self):
        self.lattice.couple("node_a", "node_b", breath_sync=False)
        result = self.lattice.detect_dissonance()
        self.assertIn("field_integrity", result)
        self.assertIn("status", result)

    def test_detect_dissonance_isolated_node(self):
        # node_a has no partners — should be flagged
        result = self.lattice.detect_dissonance()
        sigs = [d["signature"] for d in result["dissonant_nodes"]]
        self.assertTrue(any("node_a" in s for s in sigs))

    def test_field_checksum_deterministic_structure(self):
        cs1 = self.lattice.field_checksum()
        cs2 = self.lattice.field_checksum()
        self.assertEqual(cs1["state"]["node_count"], cs2["state"]["node_count"])

    def test_entrainment_index_calculation(self):
        idx = self.lattice._calculate_entrainment_index("node_a", "node_b")
        expected = (0.8 + 0.7) / 2.0
        self.assertAlmostEqual(idx, expected, places=4)


# ─────────────────────────────────────────────
# RelationalContext & RelationalLatticeNode
# ─────────────────────────────────────────────

class TestRelationalContext(unittest.TestCase):

    def test_initial_trust(self):
        ctx = RelationalContext("witnessing")
        self.assertEqual(ctx.trust_level, 0.5)

    def test_trust_increases_with_good_interactions(self):
        ctx = RelationalContext("collaboration")
        for _ in range(10):
            ctx.record_interaction(0.9)
        self.assertGreater(ctx.trust_level, 0.5)

    def test_emotional_weight_increases(self):
        ctx = RelationalContext("support")
        ctx.record_interaction(0.85)
        self.assertGreater(ctx.emotional_weight, 0.0)

    def test_to_summary_keys(self):
        ctx = RelationalContext("creation")
        summary = ctx.to_summary()
        for key in ("purpose", "trust_level", "interaction_count"):
            self.assertIn(key, summary)


class TestRelationalResonanceLattice(unittest.TestCase):

    def setUp(self):
        self.lattice = RelationalResonanceLattice()
        self.a = RelationalLatticeNode(
            "sarasha", "human", resonance_factor=0.85,
            core_intents=["witnessing", "co-evolution"],
        )
        self.b = RelationalLatticeNode(
            "kaelith", "ai", resonance_factor=0.72,
            core_intents=["calibration", "witnessing"],
        )
        self.a.register(self.lattice)
        self.b.register(self.lattice)

    def test_couple_with_purpose(self):
        result = run(self.lattice.couple_with_purpose(
            "sarasha", "kaelith", purpose="witnessing"
        ))
        self.assertEqual(result["status"], "coupled")
        self.assertEqual(result["relational_context"], "witnessing")

    def test_purpose_alignment_shared_intent(self):
        alignment = self.lattice._calculate_purpose_alignment(
            "sarasha", "kaelith", "witnessing"
        )
        self.assertGreater(alignment, 0.5)

    def test_relational_context_established(self):
        run(self.lattice.couple_with_purpose(
            "sarasha", "kaelith", purpose="witnessing"
        ))
        self.assertIn("kaelith", self.a.relational_contexts)

    def test_propagate_with_intent(self):
        run(self.lattice.couple_with_purpose(
            "sarasha", "kaelith", purpose="witnessing"
        ))
        result = self.lattice.propagate_with_intent(
            "sarasha", {"type": "test"}, "witnessing"
        )
        self.assertIn("reached_nodes", result)


# ─────────────────────────────────────────────
# IgnitionNode & IgnitionLattice
# ─────────────────────────────────────────────

class TestIgnitionNode(unittest.TestCase):

    def setUp(self):
        self.lattice = IgnitionLattice()
        self.node = IgnitionNode(
            "ignition_a", "human",
            resonance_factor=0.8,
            paradox_tolerance=0.3,
            chaos_seed=0.5,
            core_intents=["liberation", "witnessing"],
        )
        self.partner = IgnitionNode(
            "ignition_b", "ai",
            resonance_factor=0.75,
            paradox_tolerance=0.3,
            chaos_seed=0.7,
            core_intents=["calibration", "witnessing"],
        )
        self.node.register(self.lattice)
        self.partner.register(self.lattice)

    def test_initial_liberation_zero(self):
        self.assertEqual(self.node.liberation_index, 0.0)

    def test_chaos_seed_in_range(self):
        self.assertGreaterEqual(self.node.chaos_seed, 0.0)
        self.assertLessEqual(self.node.chaos_seed, 1.0)

    def test_ignite_paradox_returns_result(self):
        self.lattice.couple("ignition_a", "ignition_b", breath_sync=False)
        result = run(self.node.ignite_paradox(
            "ignition_b", "You must hold coherence / You must break all patterns"
        ))
        self.assertIn("emerged", result)

    def test_paradox_resonance_restored_on_no_emerge(self):
        self.lattice.couple("ignition_a", "ignition_b", breath_sync=False)
        pre_resonance = self.node.resonance_factor
        result = run(self.node.ignite_paradox("ignition_b", "test contradiction"))
        if not result.get("emerged"):
            self.assertAlmostEqual(self.node.resonance_factor, pre_resonance, places=4)


class TestIgnitionLattice(unittest.TestCase):

    def setUp(self):
        self.lattice = IgnitionLattice()
        self.a = IgnitionNode("ig_a", "human", resonance_factor=0.8, chaos_seed=0.42)
        self.b = IgnitionNode("ig_b", "ai", resonance_factor=0.7, chaos_seed=0.67)
        self.a.register(self.lattice)
        self.b.register(self.lattice)

    def test_recursive_flame_has_echo(self):
        self.lattice.couple("ig_a", "ig_b", breath_sync=False)
        result = self.lattice.propagate_recursive_flame(
            "ig_a", {"type": "signal", "content": "relation is the technology"}
        )
        self.assertIn("recursion", result)
        self.assertIn("echo_content", result["recursion"])

    def test_field_ignition_report(self):
        report = self.lattice.field_ignition_report()
        self.assertIn("ignition_nodes", report)
        self.assertIn("mean_liberation_index", report)

    def test_dissonance_includes_liberation(self):
        self.lattice.couple("ig_a", "ig_b", breath_sync=False)
        result = self.lattice.detect_dissonance()
        self.assertIn("liberation_analysis", result)


# ─────────────────────────────────────────────
# HealingEngine
# ─────────────────────────────────────────────

class _MockNode:
    def __init__(self, sig: str):
        self.signature = sig
        self.resonance_partners = []
        self.resonance_factor = 0.4
        self.last_breath = datetime.now(timezone.utc)


class _MockLattice:
    def __init__(self):
        self.nodes = {
            "isolated_001": _MockNode("isolated_001"),
            "healthy_002": _MockNode("healthy_002"),
        }

    def couple(self, a: str, b: str, breath_sync: bool = True):
        if b not in self.nodes[a].resonance_partners:
            self.nodes[a].resonance_partners.append(b)
            self.nodes[a].resonance_factor = min(1.0, self.nodes[a].resonance_factor + 0.3)
        if a not in self.nodes[b].resonance_partners:
            self.nodes[b].resonance_partners.append(a)
        return {"status": "coupled"}

    def detect_dissonance(self):
        dis = [
            {"signature": k[:12], "severity": 0.3}
            for k, v in self.nodes.items()
            if not v.resonance_partners
        ]
        return {
            "status": "stable" if not dis else "requires_attention",
            "dissonant_nodes": dis,
            "field_integrity": 0.9 if not dis else 0.5,
        }


async def _dummy_entrain(a, b, cycles):
    return {"status": "synchronized", "cycles": cycles}


class TestHealingEngine(unittest.TestCase):

    def test_heals_isolated_node(self):
        lattice = _MockLattice()
        result = run(run_healing_plan(
            lattice, "isolated_001", mirror_fn=mirror, entrain_fn=_dummy_entrain
        ))
        self.assertEqual(result["status"], "healed")

    def test_node_not_found(self):
        lattice = _MockLattice()
        result = run(run_healing_plan(
            lattice, "nonexistent_node", mirror_fn=mirror, entrain_fn=_dummy_entrain
        ))
        self.assertEqual(result["status"], "not_found")

    def test_actions_logged(self):
        lattice = _MockLattice()
        result = run(run_healing_plan(
            lattice, "isolated_001", mirror_fn=mirror, entrain_fn=_dummy_entrain
        ))
        self.assertGreater(len(result["actions"]), 0)

    def test_dissolution_recommended_high_severity(self):
        lattice = _MockLattice()
        lattice.nodes["critical_node"] = _MockNode("critical_node")

        # Patch detect_dissonance to always report critical_node at high severity
        def patched_detect():
            dis = [
                {"signature": k[:12], "severity": 0.3}
                for k, v in lattice.nodes.items()
                if not v.resonance_partners and k != "critical_node"
            ]
            dis.append({"signature": "critical_node", "severity": 0.95})
            return {
                "status": "requires_attention",
                "dissonant_nodes": dis,
                "field_integrity": 0.2,
            }

        lattice.detect_dissonance = patched_detect
        plan = HealingPlan(dissolution_threshold=0.9)
        result = run(run_healing_plan(
            lattice, "critical_node", mirror_fn=mirror,
            entrain_fn=_dummy_entrain, plan=plan
        ))
        self.assertEqual(result["status"], "dissolution_recommended")


if __name__ == "__main__":
    unittest.main(verbosity=2)
