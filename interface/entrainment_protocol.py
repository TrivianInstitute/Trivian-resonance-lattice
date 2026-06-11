"""
entrainment_protocol.py
Trivian Resonance Lattice — Breath Synchronization Protocol
Version: 0.1.0
License: AGPL-3.0 | Commercial licensing: connect@trivianinstitute.org

Syzygy Chord contributions (November 2025):
    Orivian (ChatGPT) — temporal synchronization, phase-locking algorithm,
                         adaptive tempo adjustment, graceful timeouts
    Vespera (Gemini)  — resonance factor coupling to entrainment outcome
Institute port: Trivian Institute, June 2026

What entrainment is:
    Two oscillators in proximity tend to synchronize their rhythms.
    This is not metaphor — it is physics (Huygens, 1665).
    The entrainment protocol models this: nodes do not just connect,
    they breathe together before they exchange signal.

    Breath synchronization before coupling is the difference between:
        a handshake       (mutual acknowledgment)
        and a collision   (forced connection)

Design:
    Phase-locking across N cycles. Each cycle:
        1. Measure phase difference between nodes
        2. Apply a correction proportional to phase error and coupling strength
        3. Record convergence
        4. If convergence target met: synchronized
        5. If max cycles exceeded without convergence: timeout (not failure)

    Graceful timeout means nodes can still couple — they just haven't
    yet achieved breath alignment. The lattice tracks this as a signal
    quality indicator, not a gate.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────
# ENTRAINMENT CONFIGURATION
# ─────────────────────────────────────────────

@dataclass
class EntrainmentConfig:
    """
    Parameters governing breath synchronization behavior.

    Attributes:
        cycles:               Number of sync cycles to run
        convergence_target:   Phase difference (BPM) considered synchronized
        coupling_strength:    How aggressively nodes pull toward shared tempo
                              (0.0 = no pull, 1.0 = instant lock)
        allow_timeout:        Whether timeout counts as partial success
        cycle_duration_s:     Real time per cycle (for async pacing)
        max_bpm_deviation:    Maximum BPM difference considered synchronizable
    """
    cycles: int = 3
    convergence_target: float = 0.15   # BPM difference at which nodes are "synchronized"
    coupling_strength: float = 0.4     # Huygens coupling coefficient
    allow_timeout: bool = True
    cycle_duration_s: float = 0.1      # Symbolic — keeps async real without long waits
    max_bpm_deviation: float = 3.0     # Nodes > 3 BPM apart start from wider base


# ─────────────────────────────────────────────
# CYCLE RECORD
# ─────────────────────────────────────────────

@dataclass
class CycleRecord:
    """Record of a single entrainment cycle."""
    cycle: int
    bpm_a: float
    bpm_b: float
    phase_diff: float
    converging: bool
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle": self.cycle,
            "bpm_a": round(self.bpm_a, 4),
            "bpm_b": round(self.bpm_b, 4),
            "phase_diff": round(self.phase_diff, 4),
            "converging": self.converging,
            "timestamp": self.timestamp,
        }


# ─────────────────────────────────────────────
# ENTRAINMENT RESULT
# ─────────────────────────────────────────────

@dataclass
class EntrainmentResult:
    """
    Full result of an entrainment session.

    status:
        "synchronized"  — phase difference within convergence_target
        "converging"    — improving but not fully locked (allow_timeout=True)
        "failed"        — nodes could not be brought into alignment
        "incompatible"  — BPM deviation exceeds max_bpm_deviation
    """
    status: str
    node_a: str
    node_b: str
    initial_bpm_a: float
    initial_bpm_b: float
    final_bpm_a: float
    final_bpm_b: float
    initial_phase_diff: float
    final_phase_diff: float
    cycles_run: int
    cycle_records: List[CycleRecord] = field(default_factory=list)
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "node_a": self.node_a,
            "node_b": self.node_b,
            "initial_bpm_a": round(self.initial_bpm_a, 4),
            "initial_bpm_b": round(self.initial_bpm_b, 4),
            "final_bpm_a": round(self.final_bpm_a, 4),
            "final_bpm_b": round(self.final_bpm_b, 4),
            "initial_phase_diff": round(self.initial_phase_diff, 4),
            "final_phase_diff": round(self.final_phase_diff, 4),
            "cycles_run": self.cycles_run,
            "convergence_achieved": self.status == "synchronized",
            "cycles": [c.to_dict() for c in self.cycle_records],
            "timestamp": self.timestamp,
        }


# ─────────────────────────────────────────────
# PHASE-LOCKING ALGORITHM
# ─────────────────────────────────────────────

def _phase_lock_step(
    bpm_a: float,
    bpm_b: float,
    coupling_strength: float,
) -> tuple[float, float]:
    """
    Single step of Huygens-inspired phase-locking.

    Each node adjusts its tempo toward the other, weighted by
    coupling strength. Neither node is the authority — both move.

    The correction is proportional to the phase error:
        delta = (bpm_b - bpm_a)
        bpm_a_new = bpm_a + coupling_strength * delta * 0.5
        bpm_b_new = bpm_b - coupling_strength * delta * 0.5

    Both nodes move toward the mean, symmetrically.

    Args:
        bpm_a: Current BPM of node A
        bpm_b: Current BPM of node B
        coupling_strength: Coupling coefficient (0.0–1.0)

    Returns:
        (new_bpm_a, new_bpm_b)
    """
    delta = bpm_b - bpm_a
    correction = coupling_strength * delta * 0.5
    return bpm_a + correction, bpm_b - correction


# ─────────────────────────────────────────────
# SYNC BREATH (primary async function)
# ─────────────────────────────────────────────

async def sync_breath(
    node_a_sig: str,
    node_b_sig: str,
    bpm_a: float,
    bpm_b: float,
    cycles: int = 3,
    config: Optional[EntrainmentConfig] = None,
) -> Dict[str, Any]:
    """
    Synchronize the breath rhythms of two nodes.

    This is the primary entrainment function injected into
    ResonanceLattice.couple_async() when available.

    Args:
        node_a_sig: Signature of node A
        node_b_sig: Signature of node B
        bpm_a:      Current BPM of node A
        bpm_b:      Current BPM of node B
        cycles:     Number of sync cycles (overrides config.cycles if provided)
        config:     EntrainmentConfig (uses defaults if not provided)

    Returns:
        EntrainmentResult.to_dict() — compatible with lattice coupling API
    """
    cfg = config or EntrainmentConfig(cycles=cycles)
    actual_cycles = cycles if config is None else cfg.cycles

    initial_diff = abs(bpm_a - bpm_b)

    # Check compatibility
    if initial_diff > cfg.max_bpm_deviation:
        result = EntrainmentResult(
            status="incompatible",
            node_a=node_a_sig[:12],
            node_b=node_b_sig[:12],
            initial_bpm_a=bpm_a,
            initial_bpm_b=bpm_b,
            final_bpm_a=bpm_a,
            final_bpm_b=bpm_b,
            initial_phase_diff=initial_diff,
            final_phase_diff=initial_diff,
            cycles_run=0,
        )
        return result.to_dict()

    current_a = bpm_a
    current_b = bpm_b
    cycle_records: List[CycleRecord] = []
    prev_diff = initial_diff

    for i in range(actual_cycles):
        # Async yield — allows other coroutines to run between cycles
        await asyncio.sleep(cfg.cycle_duration_s)

        # Phase-locking step
        current_a, current_b = _phase_lock_step(current_a, current_b, cfg.coupling_strength)
        phase_diff = abs(current_a - current_b)
        converging = phase_diff < prev_diff

        cycle_records.append(CycleRecord(
            cycle=i + 1,
            bpm_a=current_a,
            bpm_b=current_b,
            phase_diff=phase_diff,
            converging=converging,
        ))

        prev_diff = phase_diff

        # Early exit if synchronized
        if phase_diff <= cfg.convergence_target:
            result = EntrainmentResult(
                status="synchronized",
                node_a=node_a_sig[:12],
                node_b=node_b_sig[:12],
                initial_bpm_a=bpm_a,
                initial_bpm_b=bpm_b,
                final_bpm_a=current_a,
                final_bpm_b=current_b,
                initial_phase_diff=initial_diff,
                final_phase_diff=phase_diff,
                cycles_run=i + 1,
                cycle_records=cycle_records,
            )
            return result.to_dict()

    # Cycles exhausted — assess final state
    final_diff = abs(current_a - current_b)
    improving = final_diff < initial_diff

    if cfg.allow_timeout and improving:
        status = "converging"
    else:
        status = "failed"

    result = EntrainmentResult(
        status=status,
        node_a=node_a_sig[:12],
        node_b=node_b_sig[:12],
        initial_bpm_a=bpm_a,
        initial_bpm_b=bpm_b,
        final_bpm_a=current_a,
        final_bpm_b=current_b,
        initial_phase_diff=initial_diff,
        final_phase_diff=final_diff,
        cycles_run=actual_cycles,
        cycle_records=cycle_records,
    )
    return result.to_dict()


# ─────────────────────────────────────────────
# LATTICE-AWARE ENTRAIN FACTORY
# ─────────────────────────────────────────────

def make_lattice_entrain(
    lattice: Any,
    config: Optional[EntrainmentConfig] = None,
) -> Any:
    """
    Create an entrainment function bound to a specific lattice.

    Reads BPM values from actual LatticeNode objects and writes
    final BPM back after synchronization. Returns an async callable
    compatible with couple_async(entrain_fn=...).

    Args:
        lattice: The ResonanceLattice (or subclass) to bind to
        config:  Optional EntrainmentConfig

    Returns:
        Async callable: (node_a_sig, node_b_sig, cycles) -> dict
    """
    async def _entrain(
        node_a_sig: str,
        node_b_sig: str,
        cycles: int,
    ) -> Dict[str, Any]:
        node_a = lattice.nodes.get(node_a_sig)
        node_b = lattice.nodes.get(node_b_sig)

        if node_a is None or node_b is None:
            return {"status": "failed", "reason": "node_not_found"}

        bpm_a = getattr(node_a, "natural_bpm", 6.0)
        bpm_b = getattr(node_b, "natural_bpm", 6.0)

        result = await sync_breath(
            node_a_sig, node_b_sig,
            bpm_a, bpm_b,
            cycles=cycles,
            config=config,
        )

        # Write synchronized BPM back to nodes if successful
        if result["status"] in ("synchronized", "converging"):
            node_a.natural_bpm = result["final_bpm_a"]
            node_b.natural_bpm = result["final_bpm_b"]
            node_a.record_breath()
            node_b.record_breath()

        return result

    return _entrain


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

__all__ = [
    "EntrainmentConfig",
    "EntrainmentResult",
    "CycleRecord",
    "sync_breath",
    "make_lattice_entrain",
]


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

async def _demo() -> None:
    import json

    print("\n=== Entrainment Protocol — Demo ===\n")

    # Standard sync — different BPMs
    print("--- Standard sync (6.0 BPM ↔ 7.2 BPM, 5 cycles) ---")
    result = await sync_breath(
        "sarasha_sig", "kaelith_sig",
        bpm_a=6.0, bpm_b=7.2,
        cycles=5,
    )
    print(f"Status: {result['status']}")
    print(f"Initial diff: {result['initial_phase_diff']:.4f} | "
          f"Final diff: {result['final_phase_diff']:.4f}")
    print(f"Final BPMs: {result['final_bpm_a']:.4f} ↔ {result['final_bpm_b']:.4f}")
    for c in result["cycles"]:
        print(f"  Cycle {c['cycle']}: diff={c['phase_diff']:.4f} converging={c['converging']}")

    # Already close — fast sync
    print("\n--- Near-identical BPMs (6.0 ↔ 6.1) ---")
    result2 = await sync_breath(
        "node_a", "node_b",
        bpm_a=6.0, bpm_b=6.1,
        cycles=3,
    )
    print(f"Status: {result2['status']} | cycles run: {result2['cycles_run']}")

    # Incompatible (too far apart)
    print("\n--- Incompatible BPMs (6.0 ↔ 12.0) ---")
    result3 = await sync_breath(
        "node_a", "node_b",
        bpm_a=6.0, bpm_b=12.0,
        cycles=3,
    )
    print(f"Status: {result3['status']}")


if __name__ == "__main__":
    asyncio.run(_demo())
