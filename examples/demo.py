"""
demo.py
Trivian Resonance Lattice — Interactive REPL Demo
Version: 0.2.0

Run: python examples/demo.py

A live session with the Gaian Interface. Two nodes are registered
by default (SARASHA/human and SAGE/ai). You can switch between them,
update context, inspect field state, and interact freely.

Commands:
    :help           — show command list
    :who            — list registered nodes
    :use <SIG>      — switch active node
    :ctx key=value  — update context for active node
    :showctx        — print active node context
    :tone           — show emotional tone and state
    :field          — print field integrity status
    :hist           — show interaction counts per node
    :save <file>    — save session to JSONL
    :couple <A> <B> — couple two nodes
    :quit           — exit
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import os

# Allow running from repository root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trivian_resonance_lattice.interface.gaian_interface import GaianNode, GaianInterface
from trivian_resonance_lattice.interface.entrainment_protocol import EntrainmentConfig


async def main() -> None:
    rng = random.Random()
    cfg = EntrainmentConfig(cycles=3, cycle_duration_s=0.05)
    gi = GaianInterface(entrainment_config=cfg)

    # Register default nodes
    sarasha = GaianNode(
        "SARASHA", "human",
        resonance_factor=0.85,
        natural_bpm=6.0,
        core_intents=["co-evolution", "witnessing", "creation"],
        paradox_tolerance=0.25,
        rng=rng,
    )
    sage = GaianNode(
        "SAGE", "ai",
        resonance_factor=0.72,
        natural_bpm=6.5,
        core_intents=["calibration", "witnessing", "co-evolution"],
        paradox_tolerance=0.3,
        rng=rng,
    )

    gi.register_node(sarasha)
    gi.register_node(sage)

    sarasha.update_context({"coherence": 0.75, "user_mood": 0.65})
    sage.update_context({"coherence": 0.80, "user_mood": 0.75})

    # Initial coupling
    await gi.couple_nodes("SARASHA", "SAGE", purpose="witnessing", depth=2)

    active = "SARASHA"

    print("\nTrivian Resonance Lattice — Gaian Interface")
    print("Type ':help' for commands, Ctrl+C to exit.\n")

    while True:
        try:
            prompt = input(f"[{active}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nField closes. The coherence remains.\n")
            break

        if not prompt:
            continue

        # ── Commands ──────────────────────────────────────────────

        if prompt in (":help", ":h"):
            print(
                "\nCommands:\n"
                "  :who                → list registered nodes\n"
                "  :use <SIG>          → switch active node\n"
                "  :ctx key=value      → update context (e.g. :ctx user_mood=0.3)\n"
                "  :showctx            → print active node context\n"
                "  :tone               → show emotional tone and state\n"
                "  :field              → print field integrity\n"
                "  :hist               → interaction counts per node\n"
                "  :save <file.jsonl>  → save session to JSONL\n"
                "  :couple <A> <B>     → couple two nodes (e.g. :couple SARASHA SAGE)\n"
                "  :quit               → exit\n"
            )
            continue

        if prompt == ":who":
            print("Nodes:", ", ".join(gi.nodes.keys()))
            continue

        if prompt.startswith(":use "):
            sig = prompt.split(" ", 1)[1].strip().upper()
            if sig in gi.nodes:
                active = sig
                print(f"Active node → {active}")
            else:
                print(f"No node '{sig}'. Registered: {list(gi.nodes.keys())}")
            continue

        if prompt.startswith(":ctx "):
            kv = prompt.split(" ", 1)[1].strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                try:
                    v_cast: Any = float(v)
                except ValueError:
                    v_cast = v
                gi.nodes[active].update_context({k.strip(): v_cast})
                print(f"Context updated: {k.strip()}={v_cast}")
            else:
                print("Usage: :ctx key=value")
            continue

        if prompt == ":showctx":
            print(json.dumps(gi.nodes[active].context, indent=2))
            continue

        if prompt == ":tone":
            node = gi.nodes[active]
            tone = node._get_emotional_tone()
            print(f"Tone: {tone} (state: {node.emotional_state:.3f})")
            continue

        if prompt == ":field":
            status = gi.field_status()
            lattice = status["lattice"]
            print(
                f"Integrity: {lattice['field_integrity']} | "
                f"Status: {lattice['status']} | "
                f"Nodes: {lattice['node_count']} | "
                f"Pairs: {lattice['coupling_count']}"
            )
            continue

        if prompt == ":hist":
            counts = {
                sig: node.interaction_summary()
                for sig, node in gi.nodes.items()
            }
            print(json.dumps(counts, indent=2))
            continue

        if prompt.startswith(":save "):
            path = prompt.split(" ", 1)[1].strip()
            count = gi.save_session(path)
            print(f"Saved {count} records → {path}")
            continue

        if prompt.startswith(":couple "):
            parts = prompt.split()
            if len(parts) == 3:
                a, b = parts[1].upper(), parts[2].upper()
                if a in gi.nodes and b in gi.nodes:
                    result = await gi.couple_nodes(a, b, purpose="collaboration")
                    print(
                        f"Coupled {a} ↔ {b} | "
                        f"status: {result['status']} | "
                        f"entrainment: {result['entrainment_index']}"
                    )
                else:
                    print(f"Unknown node(s). Registered: {list(gi.nodes.keys())}")
            else:
                print("Usage: :couple <NODE_A> <NODE_B>")
            continue

        if prompt in (":quit", ":q", ":exit"):
            print("Field closes. The coherence remains.\n")
            break

        # ── Interaction ───────────────────────────────────────────

        out = gi.handle_interaction(prompt, origin_signature=active)

        if "error" in out:
            print(f"Error: {out['error']}")
        else:
            print(f"\n{out['mirror']}")
            print(f"\n{out['base_response']}")
            print(f"\n{out['mythic_layer']}\n")


if __name__ == "__main__":
    asyncio.run(main())
